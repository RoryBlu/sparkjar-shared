#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Migration script to add pgvector support for crew logs
Adds vector column and creates embeddings using OpenAI
"""

import os
import sys
import json
import time
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
import openai
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# Configuration
# Try pooled connection first, fallback to direct
DATABASE_URL = os.getenv("DATABASE_URL_POOLED") or os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL or not OPENAI_API_KEY:
    logger.error("ERROR: Missing DATABASE_URL or OPENAI_API_KEY in environment")
    sys.exit(1)

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Remove asyncpg from URL for psycopg2
db_url = DATABASE_URL.replace("+asyncpg", "")

def create_pgvector_extension(conn):
    """Enable pgvector extension if not already enabled"""
    logger.info("Enabling pgvector extension...")
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        logger.info("✅ pgvector extension enabled")
    except Exception as e:
        logger.error(f"❌ Error enabling pgvector: {e}")
        raise
    finally:
        cur.close()

def add_vector_column(conn):
    """Add embedding column to crew_job_event table"""
    logger.info("\nAdding vector column to crew_job_event...")
    cur = conn.cursor()
    try:
        # Check if column already exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='crew_job_event' 
            AND column_name='embedding'
        """)
        
        if cur.fetchone():
            logger.info("⚠️  Embedding column already exists")
        else:
            # Add the column
            cur.execute("""
                ALTER TABLE crew_job_event 
                ADD COLUMN embedding vector(1536)
            """)
            conn.commit()
            logger.info("✅ Added embedding column (vector(1536))")
        
        # Create index for similarity search
        cur.execute("""
            CREATE INDEX IF NOT EXISTS crew_job_event_embedding_idx 
            ON crew_job_event 
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        conn.commit()
        logger.info("✅ Created/verified vector index")
        
    except Exception as e:
        logger.error(f"❌ Error adding vector column: {e}")
        raise
    finally:
        cur.close()

def prepare_text_for_embedding(event: Dict[str, Any]) -> str:
    """Prepare event text for embedding"""
    parts = []
    
    # Add event type
    parts.append(f"Event Type: {event['event_type']}")
    
    # Add timestamp
    if event['event_time']:
        parts.append(f"Time: {event['event_time']}")
    
    # Process event data
    if isinstance(event['event_data'], dict):
        data = event['event_data']
        
        # Extract key information
        if 'message' in data:
            parts.append(f"Message: {str(data['message'])[:500]}")
        if 'thought' in data:
            parts.append(f"Thought: {str(data['thought'])[:500]}")
        if 'action' in data:
            parts.append(f"Action: {data['action']}")
        if 'tool' in data:
            parts.append(f"Tool: {data['tool']}")
        if 'error' in data:
            parts.append(f"Error: {str(data['error'])[:300]}")
        if 'observation' in data:
            parts.append(f"Observation: {str(data['observation'])[:300]}")
        if 'result' in data:
            parts.append(f"Result: {str(data['result'])[:300]}")
        
        # For raw logs, extract key content
        if event['event_type'] == 'raw_log' and 'message' in data:
            msg = str(data['message'])
            if 'I tried reusing the same input' in msg:
                parts.append("RETRY PATTERN: Agent retrying with same input")
            if 'tool failed' in msg.lower() or 'error' in msg.lower():
                parts.append("TOOL FAILURE detected")
    else:
        # Handle non-dict event data
        parts.append(f"Data: {str(event['event_data'])[:500]}")
    
    return " | ".join(parts)

def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Get embeddings for a batch of texts using OpenAI"""
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"❌ Error getting embeddings: {e}")
        # Return zero vectors on error
        return [[0.0] * 1536 for _ in texts]

def embed_job_events(conn, job_id: str = None, batch_size: int = 100):
    """Create embeddings for crew job events"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Build query
        if job_id:
            logger.info(f"\nProcessing events for job: {job_id}")
            query = """
                SELECT id, event_type, event_data, event_time
                FROM crew_job_event
                WHERE job_id = %s AND embedding IS NULL
                ORDER BY event_time
            """
            params = (job_id,)
        else:
            logger.info("\nProcessing all events without embeddings...")
            query = """
                SELECT id, event_type, event_data, event_time
                FROM crew_job_event
                WHERE embedding IS NULL
                ORDER BY created_at DESC
                LIMIT 5000
            """
            params = None
        
        cur.execute(query, params)
        events = cur.fetchall()
        total = len(events)
        logger.info(f"Found {total} events to process")
        
        if total == 0:
            logger.info("✅ No events need embedding")
            return
        
        # Process in batches
        for i in range(0, total, batch_size):
            batch = events[i:i + batch_size]
            batch_texts = []
            batch_ids = []
            
            # Prepare texts
            for event in batch:
                text = prepare_text_for_embedding(event)
                batch_texts.append(text)
                batch_ids.append(event['id'])
            
            # Get embeddings
            logger.info(f"\nBatch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
            logger.info(f"  Getting embeddings for {len(batch_texts)} events...")
            
            start_time = time.time()
            embeddings = get_embeddings_batch(batch_texts)
            elapsed = time.time() - start_time
            
            logger.info(f"  Got embeddings in {elapsed:.1f}s")
            
            # Update database
            update_cur = conn.cursor()
            update_data = [
                (embedding, event_id) 
                for embedding, event_id in zip(embeddings, batch_ids)
            ]
            
            execute_batch(
                update_cur,
                "UPDATE crew_job_event SET embedding = %s WHERE id = %s",
                update_data,
                page_size=100
            )
            conn.commit()
            update_cur.close()
            
            logger.info(f"  ✅ Updated {len(batch)} events")
            
            # Rate limit (3 RPM for tier 1)
            if i + batch_size < total:
                time.sleep(20)  # Wait 20s between batches
        
        logger.info(f"\n✅ Successfully embedded {total} events")
        
    except Exception as e:
        logger.error(f"❌ Error embedding events: {e}")
        raise
    finally:
        cur.close()

def test_vector_search(conn, job_id: str, query: str):
    """Test vector similarity search"""
    logger.info(f"\n🔍 Testing vector search for: '{query}'")
    
    # Get embedding for query
    query_embedding = get_embeddings_batch([query])[0]
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Search using cosine similarity
        cur.execute("""
            SELECT 
                id,
                event_type,
                event_data,
                event_time,
                1 - (embedding <=> %s::vector) as similarity
            FROM crew_job_event
            WHERE job_id = %s
                AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT 5
        """, (query_embedding, job_id, query_embedding))
        
        results = cur.fetchall()
        
        logger.info(f"\nTop {len(results)} results:")
        for i, result in enumerate(results, 1):
            logger.info(f"\n{i}. {result['event_type']} (similarity: {result['similarity']:.3f})")
            logger.info(f"   Time: {result['event_time']}")
            
            # Show relevant content
            if isinstance(result['event_data'], dict):
                data = result['event_data']
                if 'message' in data:
                    logger.info(f"   Message: {str(data['message'])[:150]}...")
                elif 'error' in data:
                    logger.error(f"   Error: {str(data['error'])[:150]}...")
                elif 'thought' in data:
                    logger.info(f"   Thought: {str(data['thought'])[:150]}...")
    
    finally:
        cur.close()

def main():
    """Run the migration"""
    logger.info("🚀 pgvector Migration Script")
    logger.info("="*60)
    
    # Connect to database
    logger.info(f"Connecting to database...")
    conn = psycopg2.connect(db_url)
    logger.info("✅ Connected to PostgreSQL")
    
    try:
        # Step 1: Enable pgvector
        create_pgvector_extension(conn)
        
        # Step 2: Add vector column
        add_vector_column(conn)
        
        # Step 3: Embed events for specific job
        job_id = "111c213e-a1a2-445a-bcb5-8ee11822a80f"  # Railway entity research job
        embed_job_events(conn, job_id)
        
        # Step 4: Test search
        test_queries = [
            "I tried reusing the same input retry pattern",
            "tool failed error",
            "sj_memory create entity",
            "sj_sequential_thinking session",
            "document save"
        ]
        
        for query in test_queries:
            test_vector_search(conn, job_id, query)
        
        logger.info("\n✅ Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()