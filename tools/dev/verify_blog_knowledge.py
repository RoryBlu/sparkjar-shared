#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Verify the blog writing knowledge stored for synth_class 24.
"""
import os
import sys
from pathlib import Path
from uuid import UUID
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

# Add parent directory to Python path

# Load environment variables
load_dotenv()

from sparkjar_crew.shared.config.config import DATABASE_URL_DIRECT

# Create synchronous engine
engine = create_engine(DATABASE_URL_DIRECT.replace('postgresql+asyncpg', 'postgresql'))

def verify_blog_knowledge():
    """Verify the blog writing knowledge for synth_class 24"""
    
    logger.info("🔍 Verifying blog writing knowledge for synth_class 24\n")
    
    ACTOR_ID = UUID('00000000-0000-0000-0000-000000000024')
    
    with engine.connect() as conn:
        # Get all entities
        result = conn.execute(text("""
            SELECT id, entity_name, entity_type, metadata
            FROM memory_entities
            WHERE actor_type = 'synth_class'
            AND actor_id = :actor_id
            ORDER BY created_at
        """), {"actor_id": ACTOR_ID})
        
        entities = result.fetchall()
        logger.info(f"📋 Found {len(entities)} entities:")
        entity_map = {}
        
        for entity in entities:
            entity_map[entity[0]] = entity[1]
            logger.info(f"\n✅ {entity[1]}")
            logger.info(f"   Type: {entity[2]}")
            metadata = entity[3]
            if metadata:
                if 'version' in metadata:
                    logger.info(f"   Version: {metadata['version']}")
                if 'phases' in metadata:
                    logger.info(f"   Phases: {len(metadata['phases'])}")
                if 'categories' in metadata:
                    logger.info(f"   Categories: {len(metadata['categories'])}")
        
        # Get observations
        logger.info(f"\n📋 Checking observations:")
        result = conn.execute(text("""
            SELECT me.entity_name, mo.observation_type, mo.source, 
                   jsonb_array_length(COALESCE((mo.observation_value->'steps')::jsonb, '[]'::jsonb)) as steps
            FROM memory_observations mo
            JOIN memory_entities me ON mo.entity_id = me.id
            WHERE me.actor_type = 'synth_class'
            AND me.actor_id = :actor_id
            ORDER BY me.entity_name, mo.observation_type
        """), {"actor_id": ACTOR_ID})
        
        observations = result.fetchall()
        current_entity = None
        for obs in observations:
            if obs[0] != current_entity:
                current_entity = obs[0]
                logger.info(f"\n   {current_entity}:")
            logger.info(f"      - {obs[1]} (source: {obs[2]})")
            if obs[3] and obs[3] > 0:
                logger.info(f"        Steps: {obs[3]}")
        
        # Get relationships
        logger.info(f"\n📋 Checking relationships:")
        result = conn.execute(text("""
            SELECT 
                me1.entity_name as from_entity,
                mr.relation_type,
                me2.entity_name as to_entity,
                mr.metadata
            FROM memory_relations mr
            JOIN memory_entities me1 ON mr.from_entity_id = me1.id
            JOIN memory_entities me2 ON mr.to_entity_id = me2.id
            WHERE me1.actor_type = 'synth_class'
            AND me1.actor_id = :actor_id
            ORDER BY mr.relation_type, me1.entity_name
        """), {"actor_id": ACTOR_ID})
        
        relationships = result.fetchall()
        for rel in relationships:
            logger.info(f"\n   {rel[0]}")
            logger.info(f"      {rel[1]} → {rel[2]}")
            if rel[3]:
                if 'value' in rel[3]:
                    logger.info(f"      Value: {rel[3]['value']}")
                if 'criticality' in rel[3]:
                    logger.info(f"      Criticality: {rel[3]['criticality']}")
        
        # Summary
        logger.info(f"\n📊 Summary:")
        logger.info(f"   - Total entities: {len(entities)}")
        logger.info(f"   - Total observations: {len(observations)}")
        logger.info(f"   - Total relationships: {len(relationships)}")
        logger.info(f"   - All stored with actor_id: {ACTOR_ID}")
        
        # Test a specific query
        logger.info(f"\n🧪 Testing specific query for Blog SOP:")
        result = conn.execute(text("""
            SELECT entity_name, metadata->>'version' as version,
                   metadata->'phases' as phases
            FROM memory_entities
            WHERE actor_type = 'synth_class'
            AND actor_id = :actor_id
            AND entity_type = 'procedure_template'
            AND entity_name LIKE '%Blog Writing%SOP%'
        """), {"actor_id": ACTOR_ID})
        
        sop = result.fetchone()
        if sop:
            logger.info(f"   ✅ Found: {sop[0]}")
            logger.info(f"   Version: {sop[1]}")
            logger.info(f"   Phases: {len(sop[2]) if sop[2] else 0}")

if __name__ == "__main__":
    verify_blog_knowledge()