#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Quick database schema inspection - shows all tables and their columns.
"""
import asyncio
import sys
import os

# Add src to path

from services.crew_api.src.database.connection import get_direct_session
from sqlalchemy import text

async def inspect_database():
    """Inspect database schema."""
    logger.info("🔍 Inspecting Database Schema")
    logger.info("=" * 50)
    
    async with get_direct_session() as session:
        # Get all tables
        result = await session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """))
        tables = result.fetchall()
        
        logger.info(f"📊 Found {len(tables)} tables:")
        for table in tables:
            logger.info(f"  - {table[0]}")
        
        logger.info("\n" + "=" * 50)
        
        # Inspect each table structure
        for table in tables:
            table_name = table[0]
            logger.info(f"\n📋 Table: {table_name}")
            logger.info("-" * 30)
            
            result = await session.execute(text(f"""
                SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                col_type = col[1]
                if col[4]:  # character_maximum_length
                    col_type += f"({col[4]})"
                default = f" DEFAULT {col[3]}" if col[3] else ""
                logger.info(f"  {col[0]}: {col_type} {nullable}{default}")

if __name__ == "__main__":
    asyncio.run(inspect_database())