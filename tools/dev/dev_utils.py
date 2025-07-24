
import logging
logger = logging.getLogger(__name__)

"""
Development utilities for testing and debugging.
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path

from services.crew_api.src.api.auth import create_dev_token, create_internal_token
from services.crew_api.src.crews import CREW_REGISTRY
from services.crew_api.src.database.connection import check_database_connection, create_tables

from services.crew_api.src.utils.chroma_client import test_chroma_connection

async def test_connections():
    """Test all external connections."""
    logger.info("=== Connection Tests ===")

    # Test ChromaDB
    logger.info("\n1. Testing ChromaDB connection...")
    chroma_result = test_chroma_connection()
    if chroma_result["status"] == "success":
        print(
            f"✅ ChromaDB connected: {chroma_result['total_collections']} collections"
        )
        for collection in chroma_result["collections"]:
            logger.info(f"   - {collection}")
    else:
        logger.error(f"❌ ChromaDB failed: {chroma_result.get('error', 'Unknown error')}")

    # Test Database
    logger.info("\n2. Testing database connection...")
    db_result = await check_database_connection()
    if db_result:
        logger.info("✅ Database connected")
    else:
        logger.error("❌ Database connection failed")

    logger.info("\n=== Connection Tests Complete ===")

def test_auth():
    """Test authentication functionality."""
    logger.info("\n=== Authentication Tests ===")

    # Create development token
    dev_token = create_dev_token()
    logger.info(f"Development token: {dev_token}")

    # Create internal token
    internal_token = create_internal_token()
    logger.info(f"Internal token: {internal_token}")

    logger.info("✅ Authentication tokens created")

def test_crew_registry():
    """Test crew registry."""
    logger.info("\n=== Crew Registry Tests ===")

    job_keys = list(CREW_REGISTRY.keys())

    logger.info(f"Available job keys: {job_keys}")

    for job_key, handler in CREW_REGISTRY.items():
        logger.info(f"  {job_key}: {handler.__name__}")

    logger.info("✅ Crew registry tested")

async def setup_database():
    """Set up database tables."""
    logger.info("\n=== Database Setup ===")

    try:
        await create_tables()
        logger.info("✅ Database tables created")
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")

async def main():
    """Run all development tests."""
    logger.info("SparkJAR COS Development Utilities")
    logger.info("==================================")

    await test_connections()
    test_auth()
    test_crew_registry()
    await setup_database()

    logger.info("\n=== All Tests Complete ===")

if __name__ == "__main__":
    asyncio.run(main())