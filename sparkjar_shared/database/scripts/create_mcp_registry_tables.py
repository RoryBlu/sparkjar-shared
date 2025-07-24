#!/usr/bin/env python3
"""
Create MCP Registry Tables

This script creates the MCP Registry tables in the database.
It can be run safely multiple times - it will only create tables that don't exist.
"""

import sys
import os
import asyncio

# Add parent directory to path to import src modules

from sqlalchemy import inspect, text
from services.crew_api.src.database.connection import direct_engine
from services.crew_api.src.database.models import Base
from services.crew_api.src.database.mcp_registry_models import (
    MCPService, MCPServiceTool, MCPServiceHealth, 
    MCPServiceDiscoveryCache, MCPServiceEvent
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def table_exists(engine, table_name):
    """Check if a table exists in the database"""
    async with engine.connect() as conn:
        result = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        return table_name in result

async def create_mcp_registry_tables():
    """Create MCP Registry tables if they don't exist"""
    engine = direct_engine
    
    # List of MCP Registry tables
    mcp_tables = [
        ('mcp_services', MCPService),
        ('mcp_service_tools', MCPServiceTool),
        ('mcp_service_health', MCPServiceHealth),
        ('mcp_service_discovery_cache', MCPServiceDiscoveryCache),
        ('mcp_service_events', MCPServiceEvent)
    ]
    
    logger.info("Starting MCP Registry table creation...")
    
    # Check which tables need to be created
    tables_to_create = []
    for table_name, model_class in mcp_tables:
        if await table_exists(engine, table_name):
            logger.info(f"Table '{table_name}' already exists - skipping")
        else:
            tables_to_create.append((table_name, model_class))
            logger.info(f"Table '{table_name}' will be created")
    
    if not tables_to_create:
        logger.info("All MCP Registry tables already exist")
        return
    
    # Create only the tables that don't exist
    logger.info(f"Creating {len(tables_to_create)} new tables...")
    
    # Create tables
    async with engine.begin() as conn:
        for table_name, model_class in tables_to_create:
            try:
                await conn.run_sync(model_class.__table__.create)
                logger.info(f"✓ Created table '{table_name}'")
            except Exception as e:
                logger.error(f"✗ Failed to create table '{table_name}': {e}")
                raise
    
    # Verify all tables were created successfully
    logger.info("\nVerifying table creation...")
    all_created = True
    for table_name, _ in mcp_tables:
        if await table_exists(engine, table_name):
            logger.info(f"✓ Table '{table_name}' exists")
        else:
            logger.error(f"✗ Table '{table_name}' was not created")
            all_created = False
    
    if all_created:
        logger.info("\n✅ All MCP Registry tables created successfully!")
    else:
        logger.error("\n❌ Some tables failed to create")
        sys.exit(1)

async def show_table_info():
    """Display information about the created tables"""
    engine = direct_engine
    
    logger.info("\nMCP Registry Table Information:")
    logger.info("=" * 50)
    
    mcp_tables = [
        'mcp_services',
        'mcp_service_tools', 
        'mcp_service_health',
        'mcp_service_discovery_cache',
        'mcp_service_events'
    ]
    
    async with engine.connect() as conn:
        inspector = await conn.run_sync(lambda sync_conn: inspect(sync_conn))
        
        for table_name in mcp_tables:
            if await table_exists(engine, table_name):
                columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns(table_name))
                logger.info(f"\nTable: {table_name}")
                logger.info(f"Columns: {len(columns)}")
                for col in columns:
                    nullable = "NULL" if col['nullable'] else "NOT NULL"
                    logger.info(f"  - {col['name']}: {col['type']} {nullable}")

async def main():
    """Main function to run the migration"""
    try:
        await create_mcp_registry_tables()
        await show_table_info()
    except Exception as e:
        logger.error(f"Failed to create MCP Registry tables: {e}")
        sys.exit(1)
    finally:
        # Clean up the engine
        await direct_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())