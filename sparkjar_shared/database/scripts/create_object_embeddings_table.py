#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Script to create object_embeddings table in Supabase.
"""

import os
import asyncio
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_object_embeddings_table():
    """Connect to Supabase and create the object_embeddings table."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL_DIRECT")
    if not database_url:
        raise ValueError("DATABASE_URL_DIRECT not found in environment")
    
    # Convert asyncpg URL format for direct connection
    if "postgresql+asyncpg://" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    logger.info(f"Connecting to Supabase...")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        
        logger.info("✅ Connected to Supabase successfully")
        
        # Read the SQL file
        sql_file_path = "/Users/r.t.rawlings/sparkjar-crew/sql/create_object_embeddings_table.sql"
        with open(sql_file_path, 'r') as f:
            sql_content = f.read()
        
        logger.info("📄 Executing SQL to create object_embeddings table...")
        
        # Execute the SQL
        await conn.execute(sql_content)
        
        logger.info("✅ object_embeddings table created successfully!")
        
        # Verify table was created
        result = await conn.fetch("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'object_embeddings'
            ORDER BY ordinal_position;
        """)
        
        if result:
            logger.info(f"📋 Table structure verified ({len(result)} columns):")
            for row in result:
                logger.info(f"  - {row['column_name']}: {row['data_type']}")
        else:
            logger.warning("⚠️  Warning: Could not verify table structure")
        
        # Check for vector extension
        vector_check = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            );
        """)
        
        if vector_check:
            logger.info("✅ pgvector extension is available")
        else:
            logger.warning("⚠️  Warning: pgvector extension not found")
        
    except Exception as e:
        logger.error(f"❌ Error creating table: {e}")
        raise
    finally:
        if 'conn' in locals():
            await conn.close()
            logger.info("🔒 Database connection closed")

if __name__ == "__main__":
    asyncio.run(create_object_embeddings_table())