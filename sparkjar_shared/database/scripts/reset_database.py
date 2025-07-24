#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Drop all existing tables and recreate them.
"""
import asyncio
import sys
import os

# Add src to path

from services.crew_api.src.database.connection import drop_tables, create_tables, check_database_connection
from services.crew_api.src.config import validate_config

async def main():
    """Drop and recreate all database tables."""
    logger.info("=== SparkJAR Crew Database Reset ===")
    
    try:
        # Validate configuration
        logger.info("1. Validating configuration...")
        validate_config()
        logger.info(f"   ✅ Configuration valid")
        
        # Test connection
        logger.info("\n2. Testing database connection...")
        connection_ok = await check_database_connection()
        if not connection_ok:
            logger.error("   ❌ Database connection failed")
            return False
        logger.info("   ✅ Database connection successful")
        
        # Drop existing tables
        logger.info("\n3. Dropping existing tables...")
        try:
            await drop_tables()
            logger.info("   ✅ Existing tables dropped")
        except Exception as e:
            logger.warning(f"   ⚠️ Warning: Could not drop tables (they may not exist): {e}")
        
        # Create new tables
        logger.info("\n4. Creating fresh database tables...")
        await create_tables()
        logger.info("   ✅ Fresh database tables created")
        
        logger.info("\n🎉 Database reset completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)