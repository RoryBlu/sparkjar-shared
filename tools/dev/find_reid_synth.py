#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Find Reid the synth actor
"""

import sys
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def main():
    # Get database URL and convert to sync
    database_url = os.getenv('DATABASE_URL_DIRECT')
    if not database_url:
        logger.info("❌ DATABASE_URL_DIRECT not found in environment")
        return
    
    # Convert asyncpg URL to psycopg2 for sync operations
    database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    # Create engine and session
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # First check synths table structure
        query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'synths'
        """)
        
        columns = session.execute(query).fetchall()
        logger.info("Synths table columns:", [col[0] for col in columns])
        
        # Find Reid
        query = text("""
            SELECT id, first_name, last_name, preferred_name, role_code
            FROM synths 
            WHERE LOWER(first_name) LIKE '%reid%' 
               OR LOWER(last_name) LIKE '%reid%'
               OR LOWER(preferred_name) LIKE '%reid%'
        """)
        
        results = session.execute(query).fetchall()
        
        if results:
            logger.info("🤖 Found Reid:")
            for synth in results:
                logger.info(f"\nID: {synth.id}")
                logger.info(f"Name: {synth.preferred_name or f'{synth.first_name} {synth.last_name}'}")
                logger.info(f"Role: {synth.role_code}")
        else:
            # Try finding any synth
            query = text("""
                SELECT id, first_name, last_name, preferred_name, role_code
                FROM synths 
                LIMIT 10
            """)
            
            results = session.execute(query).fetchall()
            logger.info("\n🤖 Available synths:")
            for synth in results:
                logger.info(f"\nID: {synth.id}")
                logger.info(f"Name: {synth.preferred_name or f'{synth.first_name} {synth.last_name}'}")
                logger.info(f"Role: {synth.role_code}")
                
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()