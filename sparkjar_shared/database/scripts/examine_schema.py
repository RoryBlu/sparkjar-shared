#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Examine the actual schema details.
"""
import asyncio
import sys
import os
import json

# Add src to path

from services.crew_api.src.services.json_validator import validator

async def examine_schema():
    """Examine the crew_research_sj_websearch schema in detail."""
    logger.info("=== Schema Detail Examination ===")
    
    try:
        # Get the specific schema
        schema_data = await validator.get_schema_by_name('crew_research_sj_websearch')
        
        if schema_data:
            logger.info(f"✅ Found schema: {schema_data['name']}")
            logger.info(f"📝 Description: {schema_data['description']}")
            logger.info(f"🏷️  Type: {schema_data['object_type']}")
            
            schema = schema_data['schema']
            logger.info(f"\n📋 Schema structure:")
            logger.info(f"   Type: {schema.get('type', 'not specified')}")
            logger.info(f"   Title: {schema.get('title', 'not specified')}")
            
            if 'required' in schema:
                logger.info(f"\n✅ Required fields:")
                for field in schema['required']:
                    logger.info(f"   - {field}")
            
            if 'properties' in schema:
                logger.info(f"\n📄 All properties:")
                for prop, details in schema['properties'].items():
                    prop_type = details.get('type', 'unknown')
                    description = details.get('description', 'no description')
                    logger.info(f"   - {prop} ({prop_type}): {description}")
            
            logger.info(f"\n🔍 Full schema JSON:")
            logger.info(json.dumps(schema, indent=2))
        else:
            logger.info("❌ Schema not found")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(examine_schema())