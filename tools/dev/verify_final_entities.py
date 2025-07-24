#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Final verification of memory entities after fixes
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add parent directory to Python path

# Load environment variables
load_dotenv()

from sparkjar_crew.shared.config.config import DATABASE_URL_DIRECT

# Create synchronous engine
engine = create_engine(DATABASE_URL_DIRECT.replace('postgresql+asyncpg', 'postgresql'))

def verify_entities():
    """Verify all entities are properly fixed"""
    
    logger.info("✅ FINAL MEMORY ENTITIES VERIFICATION")
    logger.info("="*80)
    
    with engine.connect() as conn:
        # Get all synth_class 24 and client entities
        result = conn.execute(text("""
            SELECT 
                me.actor_type,
                me.actor_id,
                me.entity_name,
                me.entity_type,
                jsonb_pretty(me.metadata) as metadata,
                COUNT(mo.id) as observation_count,
                COUNT(DISTINCT mo.observation_type) as observation_types
            FROM memory_entities me
            LEFT JOIN memory_observations mo ON mo.entity_id = me.id
            WHERE me.actor_type IN ('synth_class', 'client')
            AND (me.actor_id = '24' OR me.actor_id = '2b4ccc56-cfe9-42d0-8378-1805db211446')
            GROUP BY me.id, me.actor_type, me.actor_id, me.entity_name, me.entity_type, me.metadata
            ORDER BY me.actor_type DESC, me.entity_name
        """))
        
        entities = result.fetchall()
        
        logger.info(f"\n📊 Total Entities: {len(entities)}")
        logger.info("\n" + "-"*80)
        
        current_actor = None
        for entity in entities:
            actor_key = f"{entity[0]} (ID: {entity[1]})"
            if current_actor != actor_key:
                current_actor = actor_key
                logger.info(f"\n🏢 {actor_key}")
                logger.info("-"*40)
            
            logger.info(f"\n📁 {entity[2]}")
            logger.info(f"   Type: {entity[3]}")
            logger.info(f"   Observations: {entity[5]} ({entity[6]} types)")
            
            # Show key metadata fields
            if entity[4]:
                metadata_lines = entity[4].split('\n')
                logger.info("   Metadata:")
                for line in metadata_lines[:3]:  # First 3 lines
                    logger.info(f"     {line}")
                if len(metadata_lines) > 3:
                    logger.info("     ...")
        
        # Verify no long names
        logger.info("\n" + "="*80)
        logger.info("🔍 VALIDATION CHECKS")
        logger.info("-"*80)
        
        # Check entity name lengths
        long_names = conn.execute(text("""
            SELECT entity_name, LENGTH(entity_name) as len
            FROM memory_entities
            WHERE actor_type IN ('synth_class', 'client')
            AND (actor_id = '24' OR actor_id = '2b4ccc56-cfe9-42d0-8378-1805db211446')
            AND LENGTH(entity_name) > 30
        """)).fetchall()
        
        if long_names:
            logger.info("\n⚠️  Entity names > 30 chars:")
            for name, length in long_names:
                logger.info(f"   - {name} ({length} chars)")
        else:
            logger.info("\n✅ All entity names are concise keys (<= 30 chars)")
        
        # Check for 'template' in types
        template_types = conn.execute(text("""
            SELECT DISTINCT entity_type
            FROM memory_entities
            WHERE actor_type IN ('synth_class', 'client')
            AND (actor_id = '24' OR actor_id = '2b4ccc56-cfe9-42d0-8378-1805db211446')
            AND entity_type LIKE '%template%'
        """)).fetchall()
        
        if template_types:
            logger.info("\n⚠️  Entity types containing 'template':")
            for type_name in template_types:
                logger.info(f"   - {type_name[0]}")
        else:
            logger.info("✅ No entity types contain 'template'")
        
        # Check for duplicates
        duplicates = conn.execute(text("""
            SELECT actor_type, actor_id, entity_name, COUNT(*) as count
            FROM memory_entities
            WHERE actor_type IN ('synth_class', 'client')
            AND (actor_id = '24' OR actor_id = '2b4ccc56-cfe9-42d0-8378-1805db211446')
            GROUP BY actor_type, actor_id, entity_name
            HAVING COUNT(*) > 1
        """)).fetchall()
        
        if duplicates:
            logger.info("\n⚠️  Duplicate entity names:")
            for dup in duplicates:
                logger.info(f"   - {dup[0]}:{dup[1]} - {dup[2]} ({dup[3]} instances)")
        else:
            logger.info("✅ No duplicate entity names")
        
        # Summary of entity types
        logger.info("\n📋 Entity Type Distribution:")
        type_dist = conn.execute(text("""
            SELECT entity_type, COUNT(*) as count
            FROM memory_entities
            WHERE actor_type IN ('synth_class', 'client')
            AND (actor_id = '24' OR actor_id = '2b4ccc56-cfe9-42d0-8378-1805db211446')
            GROUP BY entity_type
            ORDER BY count DESC
        """)).fetchall()
        
        for entity_type, count in type_dist:
            logger.info(f"   - {entity_type}: {count}")
        
        logger.info("\n" + "="*80)
        logger.info("✅ VERIFICATION COMPLETE")

if __name__ == "__main__":
    verify_entities()