#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Migration script to create proper chunked embeddings for crew logs
Creates a separate embeddings table with intelligent chunking
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

import psycopg2
import tiktoken
from psycopg2.extras import RealDictCursor, execute_batch

from services.crew_api.src.utils.embedding_client import get_embedding_client

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(REPO_ROOT, ".env"))

# Initialize embedding client
embedding_client = get_embedding_client()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("ERROR: Missing DATABASE_URL in environment")
    sys.exit(1)

# Remove asyncpg from URL for psycopg2
db_url = DATABASE_URL.replace("+asyncpg", "")

# Token counter
encoding = tiktoken.encoding_for_model("text-embedding-3-small")

def count_tokens(text: str) -> int:
    """Count tokens in text"""
    return len(encoding.encode(text))

def create_embeddings_table(conn):
    """Create the chunked embeddings table"""
    logger.info("Creating crew_job_event_embeddings table...")
    cur = conn.cursor()

    try:
        # Drop if exists for clean migration
        cur.execute("DROP TABLE IF EXISTS crew_job_event_embeddings CASCADE")

        # Create new table
        cur.execute(
            """
            CREATE TABLE crew_job_event_embeddings (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES crew_job_event(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_tokens INTEGER NOT NULL,
                embedding vector(768),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(event_id, chunk_index)
            )
        """
        )

        # Create indexes
        cur.execute(
            """
            CREATE INDEX crew_job_event_embeddings_event_id_idx 
            ON crew_job_event_embeddings(event_id)
        """
        )

        cur.execute(
            """
            CREATE INDEX crew_job_event_embeddings_embedding_idx 
            ON crew_job_event_embeddings 
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """
        )

        conn.commit()
        logger.info("✅ Created embeddings table with indexes")

    except Exception as e:
        logger.error(f"❌ Error creating table: {e}")
        raise
    finally:
        cur.close()

def prepare_event_text(event: Dict[str, Any]) -> str:
    """Prepare event for embedding - full context"""
    parts = []

    # Event metadata
    parts.append(f"Event Type: {event['event_type']}")
    parts.append(f"Time: {event['event_time']}")
    parts.append(f"Job ID: {event['job_id']}")

    # Event data
    if isinstance(event["event_data"], dict):
        parts.append(f"Event Data: {json.dumps(event['event_data'], indent=2)}")
    else:
        parts.append(f"Event Data: {str(event['event_data'])}")

    return "\n".join(parts)

def smart_chunk_event(
    event: Dict[str, Any], max_tokens: int = 2000
) -> List[Tuple[str, Dict]]:
    """
    Intelligently chunk events based on their structure
    Returns list of (chunk_text, metadata) tuples
    """
    chunks = []
    event_data = event["event_data"]

    # For raw_log events with OpenAI API calls
    if event["event_type"] == "raw_log" and isinstance(event_data, dict):
        if "message" in event_data and "Request options:" in str(
            event_data.get("message", "")
        ):
            # This is an OpenAI API call log
            try:
                msg = event_data["message"]
                # Extract the JSON data from the message
                json_match = re.search(r'json_data[\'"]:\s*({.*?})\s*}', msg, re.DOTALL)
                if json_match:
                    json_data = json.loads(json_match.group(1))

                    # Chunk by messages in the conversation
                    if "messages" in json_data:
                        messages = json_data["messages"]

                        # Add context chunk
                        context = (
                            f"Event: {event['event_type']} at {event['event_time']}\n"
                        )
                        context += f"API Call with {len(messages)} messages\n"
                        chunks.append((context, {"chunk_type": "context"}))

                        # Chunk each message
                        for i, msg in enumerate(messages):
                            role = msg.get("role", "unknown")
                            content = msg.get("content", "")

                            chunk_text = f"Message {i+1}/{len(messages)}\n"
                            chunk_text += f"Role: {role}\n"
                            chunk_text += f"Content: {content}"

                            # If message is too long, split it
                            if count_tokens(chunk_text) > max_tokens:
                                # Split by paragraphs or sentences
                                content_parts = content.split("\n\n")
                                current_chunk = f"Message {i+1} Part 1\nRole: {role}\n"
                                part_num = 1

                                for part in content_parts:
                                    if count_tokens(current_chunk + part) > max_tokens:
                                        chunks.append(
                                            (
                                                current_chunk,
                                                {
                                                    "chunk_type": "message",
                                                    "message_index": i,
                                                    "message_role": role,
                                                    "part": part_num,
                                                },
                                            )
                                        )
                                        part_num += 1
                                        current_chunk = (
                                            f"Message {i+1} Part {part_num}\n{part}\n"
                                        )
                                    else:
                                        current_chunk += part + "\n\n"

                                if current_chunk.strip():
                                    chunks.append(
                                        (
                                            current_chunk,
                                            {
                                                "chunk_type": "message",
                                                "message_index": i,
                                                "message_role": role,
                                                "part": part_num,
                                            },
                                        )
                                    )
                            else:
                                chunks.append(
                                    (
                                        chunk_text,
                                        {
                                            "chunk_type": "message",
                                            "message_index": i,
                                            "message_role": role,
                                        },
                                    )
                                )
            except Exception as e:
                # Fallback to simple chunking
                pass

    # For agent thoughts/actions with structured data
    elif event["event_type"] in ["agent_thought", "agent_action", "observation"]:
        if isinstance(event_data, dict):
            # Create a structured summary
            summary = f"Event: {event['event_type']} at {event['event_time']}\n"

            # Add key fields
            for key in ["thought", "action", "tool", "observation", "error", "message"]:
                if key in event_data:
                    value = str(event_data[key])
                    if len(value) > 500:
                        value = value[:500] + "..."
                    summary += f"{key.title()}: {value}\n"

            chunks.append((summary, {"chunk_type": event["event_type"]}))

            # If there's a large 'result' or 'data' field, chunk it separately
            for key in ["result", "data", "output"]:
                if key in event_data and isinstance(event_data[key], (dict, list)):
                    data_str = json.dumps(event_data[key], indent=2)
                    if count_tokens(data_str) > 500:
                        chunk_text = f"Event {event['event_type']} - {key}:\n{data_str}"
                        chunks.append(
                            (
                                chunk_text,
                                {
                                    "chunk_type": f"{event['event_type']}_{key}",
                                    "data_key": key,
                                },
                            )
                        )

    # For retry attempts - extract the key retry pattern
    elif event["event_type"] == "retry_attempt":
        summary = f"Retry at {event['event_time']}\n"
        if isinstance(event_data, dict):
            if "message" in event_data:
                # Extract the retry pattern
                msg = str(event_data["message"])
                if "I tried reusing the same input" in msg:
                    summary += "Pattern: Agent retrying with same input\n"
                    # Extract what was being retried
                    tool_match = re.search(r"Tool (\w+) accepts", msg)
                    if tool_match:
                        summary += f"Tool: {tool_match.group(1)}\n"

            # Add error details
            if "error" in event_data:
                summary += f"Error: {str(event_data['error'])[:300]}\n"

        chunks.append((summary, {"chunk_type": "retry_pattern"}))

    # If no chunks created or text is small, create a single chunk
    if not chunks:
        full_text = prepare_event_text(event)
        if count_tokens(full_text) <= max_tokens:
            chunks.append((full_text, {"chunk_type": "full_event"}))
        else:
            # Simple chunking with overlap
            text_parts = []
            current_part = ""

            lines = full_text.split("\n")
            for line in lines:
                if count_tokens(current_part + line) > max_tokens:
                    text_parts.append(current_part)
                    current_part = line + "\n"
                else:
                    current_part += line + "\n"

            if current_part:
                text_parts.append(current_part)

            for i, part in enumerate(text_parts):
                chunks.append(
                    (
                        part,
                        {
                            "chunk_type": "partial_event",
                            "part": i + 1,
                            "total_parts": len(text_parts),
                        },
                    )
                )

    return chunks

def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Get embeddings for a batch of texts using the embedding service"""
    if not texts:
        return []

    try:
        # Filter out texts that are too long
        valid_texts = []
        valid_indices = []

        for i, text in enumerate(texts):
            tokens = count_tokens(text)
            if tokens <= 8000:  # Leave some buffer
                valid_texts.append(text)
                valid_indices.append(i)
            else:
                logger.info(f"  ⚠️  Skipping text {i+1} with {tokens} tokens")

        if not valid_texts:
            return [[0.0] * 768 for _ in texts]

        # Get embeddings for valid texts via the embedding client
        embeddings = embedding_client.get_embeddings_sync(valid_texts)

        embeddings_dict = {valid_indices[i]: emb for i, emb in enumerate(embeddings)}

        # Build result list with zero vectors for skipped texts
        result = []
        for i in range(len(texts)):
            if i in embeddings_dict:
                result.append(embeddings_dict[i])
            else:
                result.append([0.0] * 768)

        return result

    except Exception as e:
        logger.error(f"❌ Error getting embeddings: {e}")
        return [[0.0] * 768 for _ in texts]

def embed_job_events_chunked(conn, job_id: str, batch_size: int = 50):
    """Create chunked embeddings for crew job events"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Fetch all events for the job
        logger.info(f"\nFetching events for job {job_id}...")
        cur.execute(
            """
            SELECT id, job_id, event_type, event_data, event_time
            FROM crew_job_event
            WHERE job_id = %s
            ORDER BY event_time
        """,
            (job_id,),
        )

        events = cur.fetchall()
        logger.info(f"Found {len(events)} events")

        # Process each event
        total_chunks = 0
        batch_data = []

        for event_idx, event in enumerate(events):
            print(
                f"\nProcessing event {event_idx + 1}/{len(events)}: {event['event_type']}"
            )

            # Create chunks for this event
            chunks = smart_chunk_event(event)
            logger.info(f"  Created {len(chunks)} chunks")

            for chunk_idx, (chunk_text, chunk_meta) in enumerate(chunks):
                tokens = count_tokens(chunk_text)

                # Prepare record
                record = {
                    "event_id": event["id"],
                    "chunk_index": chunk_idx,
                    "chunk_text": chunk_text,
                    "chunk_tokens": tokens,
                    "metadata": json.dumps(
                        {
                            **chunk_meta,
                            "event_type": event["event_type"],
                            "event_time": (
                                event["event_time"].isoformat()
                                if event["event_time"]
                                else None
                            ),
                        }
                    ),
                }

                batch_data.append(record)
                total_chunks += 1

                # Process batch when full
                if len(batch_data) >= batch_size:
                    process_embedding_batch(conn, batch_data)
                    batch_data = []

        # Process remaining batch
        if batch_data:
            process_embedding_batch(conn, batch_data)

        print(
            f"\n✅ Successfully created {total_chunks} chunks from {len(events)} events"
        )

    except Exception as e:
        logger.error(f"❌ Error processing events: {e}")
        raise
    finally:
        cur.close()

def process_embedding_batch(conn, batch_data: List[Dict]):
    """Process a batch of chunks and create embeddings"""
    if not batch_data:
        return

    logger.info(f"\n  Processing batch of {len(batch_data)} chunks...")

    # Extract texts for embedding
    texts = [record["chunk_text"] for record in batch_data]

    # Get embeddings
    start_time = time.time()
    embeddings = get_embeddings_batch(texts)
    elapsed = time.time() - start_time
    logger.info(f"  Got embeddings in {elapsed:.1f}s")

    # Insert into database
    cur = conn.cursor()

    try:
        # Prepare data for insertion
        insert_data = []
        for record, embedding in zip(batch_data, embeddings):
            insert_data.append(
                (
                    record["event_id"],
                    record["chunk_index"],
                    record["chunk_text"],
                    record["chunk_tokens"],
                    embedding,
                    record["metadata"],
                )
            )

        # Batch insert
        execute_batch(
            cur,
            """
            INSERT INTO crew_job_event_embeddings 
            (event_id, chunk_index, chunk_text, chunk_tokens, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id, chunk_index) DO UPDATE
            SET chunk_text = EXCLUDED.chunk_text,
                chunk_tokens = EXCLUDED.chunk_tokens,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata
            """,
            insert_data,
            page_size=100,
        )

        conn.commit()
        logger.info(f"  ✅ Inserted {len(insert_data)} chunks")

    except Exception as e:
        logger.error(f"  ❌ Error inserting batch: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()

def test_chunked_search(conn, job_id: str):
    """Test the chunked vector search"""
    logger.info("\n🔍 Testing chunked vector search")
    logger.info("=" * 60)

    embeddings = embedding_client

    test_queries = [
        "Arguments validation failed query field required tool expects JSON string",
        "I tried reusing the same input retry pattern",
        "create_session sequential thinking Research Plan Michael Williams",
        "tool execution failed error message",
        "agent thought reasoning about research strategy",
    ]

    cur = conn.cursor(cursor_factory=RealDictCursor)

    for query in test_queries:
        logger.info(f"\n📍 Query: '{query}'")
        logger.info("-" * 40)

        # Get query embedding
        query_embedding = embeddings.get_embeddings_sync(query)[0]

        # Search across chunks
        cur.execute(
            """
            SELECT 
                e.event_id,
                e.chunk_index,
                e.chunk_tokens,
                e.metadata,
                ev.event_type,
                ev.event_time,
                1 - (e.embedding <=> %s::vector) as similarity,
                SUBSTRING(e.chunk_text, 1, 200) as preview
            FROM crew_job_event_embeddings e
            JOIN crew_job_event ev ON e.event_id = ev.id
            WHERE ev.job_id = %s
                AND e.embedding IS NOT NULL
                AND 1 - (e.embedding <=> %s::vector) > 0.3
            ORDER BY e.embedding <=> %s::vector
            LIMIT 5
        """,
            (query_embedding, job_id, query_embedding, query_embedding),
        )

        results = cur.fetchall()

        if results:
            logger.info(f"Found {len(results)} relevant chunks:\n")
            for i, result in enumerate(results, 1):
                meta = (
                    result["metadata"]
                    if isinstance(result["metadata"], dict)
                    else json.loads(result["metadata"] or "{}")
                )
                print(
                    f"{i}. Event {result['event_type']} - Chunk {result['chunk_index']} ({result['chunk_tokens']} tokens)"
                )
                logger.info(f"   Similarity: {result['similarity']:.3f}")
                logger.info(f"   Type: {meta.get('chunk_type', 'unknown')}")
                logger.info(f"   Preview: {result['preview']}...")
        else:
            logger.info("No results found")

    cur.close()

def analyze_chunk_distribution(conn, job_id: str):
    """Analyze how events were chunked"""
    logger.info("\n📊 Chunk Distribution Analysis")
    logger.info("=" * 60)

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get chunk statistics
    cur.execute(
        """
        SELECT 
            ev.event_type,
            COUNT(DISTINCT ev.id) as event_count,
            COUNT(e.id) as chunk_count,
            AVG(e.chunk_tokens) as avg_tokens,
            MAX(e.chunk_tokens) as max_tokens,
            SUM(CASE WHEN e.embedding IS NULL THEN 1 ELSE 0 END) as failed_embeddings
        FROM crew_job_event ev
        LEFT JOIN crew_job_event_embeddings e ON ev.id = e.event_id
        WHERE ev.job_id = %s
        GROUP BY ev.event_type
        ORDER BY chunk_count DESC
    """,
        (job_id,),
    )

    results = cur.fetchall()

    print(
        f"{'Event Type':<20} {'Events':>8} {'Chunks':>8} {'Avg Tokens':>12} {'Max Tokens':>12} {'Failed':>8}"
    )
    logger.info("-" * 80)

    total_events = 0
    total_chunks = 0
    total_failed = 0

    for row in results:
        print(
            f"{row['event_type']:<20} {row['event_count']:>8} {row['chunk_count']:>8} "
            f"{row['avg_tokens']:>12.0f} {row['max_tokens']:>12} {row['failed_embeddings']:>8}"
        )
        total_events += row["event_count"]
        total_chunks += row["chunk_count"]
        total_failed += row["failed_embeddings"]

    logger.info("-" * 80)
    print(
        f"{'TOTAL':<20} {total_events:>8} {total_chunks:>8} {'':>12} {'':>12} {total_failed:>8}"
    )

    cur.close()

def main():
    """Run the chunked embedding migration"""
    logger.info("🚀 Chunked Embeddings Migration")
    logger.info("=" * 60)

    # Connect to database
    logger.info("Connecting to database...")
    conn = psycopg2.connect(db_url)
    logger.info("✅ Connected to PostgreSQL")

    try:
        # Step 1: Create embeddings table
        create_embeddings_table(conn)

        # Step 2: Process events with chunking
        job_id = "f53fddbb-ff4a-4982-b127-3ce0b8f176ce"
        embed_job_events_chunked(conn, job_id, batch_size=30)

        # Step 3: Analyze results
        analyze_chunk_distribution(conn, job_id)

        # Step 4: Test search
        test_chunked_search(conn, job_id)

        logger.info("\n✅ Migration completed successfully!")

    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()