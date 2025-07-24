#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Create the document_vectors table in Supabase for generic vector storage
"""
import os
import sys
import psycopg2
from pathlib import Path

# Add parent directory to path

from dotenv import load_dotenv
load_dotenv()

def main():
    """Create the document_vectors table"""
    # Get database URL - use pooled connection
    DATABASE_URL = os.getenv("DATABASE_URL_POOLED") or os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        logger.error("ERROR: DATABASE_URL not found in environment")
        return
    
    # Remove asyncpg for psycopg2
    db_url = DATABASE_URL.replace("+asyncpg", "")
    
    logger.info("🚀 Creating document_vectors table")
    logger.info("="*60)
    
    try:
        # Connect to database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        logger.info("✅ Connected to PostgreSQL")
        
        # Read and execute SQL file
        sql_file = Path(__file__).parent / "create_document_vectors_table.sql"
        logger.info(f"Reading SQL from {sql_file}")
        
        with open(sql_file, 'r') as f:
            sql = f.read()
        
        logger.info("Executing SQL...")
        cur.execute(sql)
        conn.commit()
        
        logger.info("✅ Table created successfully!")
        
        # Verify table exists
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'document_vectors'
            ORDER BY ordinal_position;
        """)
        
        logger.info("\nTable structure:")
        logger.info("-" * 40)
        for col_name, data_type in cur.fetchall():
            logger.info(f"  {col_name:<20} {data_type}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == "__main__":
    main()