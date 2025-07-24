#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Create client-level policy entity that overrides synth_class blog procedures.
Demonstrates the 4-layer hierarchy where client policies have ultimate authority.
"""
import os
import sys
from uuid import UUID, uuid4
from datetime import datetime
from pathlib import Path

# Add parent directory to Python path
# Add crew-api path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from crew-api models
from services.crew_api.src.database.models import MemoryEntities, MemoryObservations, MemoryRelations
from sparkjar_crew.shared.config.config import DATABASE_URL_DIRECT

# Create synchronous engine for this script
engine = create_engine(DATABASE_URL_DIRECT.replace('postgresql+asyncpg', 'postgresql'))
SessionLocal = sessionmaker(bind=engine)

def create_client_policy_override():
    """Create client-specific blog policies that override synth_class procedures"""
    
    logger.info("🏢 Creating Client-Level Policy Override Example")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # First, get a client that has synths in class 24
        result = db.execute(text("""
            SELECT DISTINCT c.id, c.legal_name, c.client_key
            FROM clients c
            JOIN synths s ON s.client_id = c.id
            JOIN synth_classes sc ON s.synth_classes_id = sc.id
            WHERE sc.id = 24
            LIMIT 1
        """))
        
        client = result.fetchone()
        if not client:
            logger.info("❌ No client found with synths in class 24")
            return
        
        client_id = str(client[0])
        client_name = client[1]
        client_key = client[2]
        
        logger.info(f"✅ Using client: {client_name} (ID: {client_id})")
        logger.info(f"   Client key: {client_key}")
        
        # Create client blog policy entity
        ACTOR_TYPE = 'client'
        ACTOR_ID = client_id
        
        client_policy = MemoryEntities(
            id=uuid4(),
            actor_type=ACTOR_TYPE,
            actor_id=ACTOR_ID,
            entity_name=f'{client_name} Blog Content Policy Override',
            entity_type='policy_override',
            metadata={
                'policy_version': '2.0',
                'effective_date': '2024-01-15',
                'supersedes': 'synth_class_24_blog_sop_v4',
                'approval_chain': ['Marketing Director', 'Legal Team', 'CEO'],
                'review_cycle': 'quarterly',
                'enforcement': 'mandatory'
            }
        )
        
        db.add(client_policy)
        db.flush()
        
        logger.info(f"\n📋 Created policy entity: {client_policy.entity_name}")
        
        # Add company-specific content restrictions
        content_restrictions = MemoryObservations(
            id=uuid4(),
            entity_id=client_policy.id,
            observation_type='policy_rule',
            observation_value={
                'rule_type': 'Content Restrictions',
                'priority': 'OVERRIDE_ALL',
                'overrides': ['synth_class_24.content_guidelines'],
                'restrictions': {
                    'prohibited_topics': [
                        'Competitor comparisons without legal review',
                        'Financial projections or guarantees',
                        'Medical or health advice',
                        'Political opinions or endorsements',
                        'Unverified customer testimonials'
                    ],
                    'required_disclaimers': {
                        'financial_content': 'Past performance does not guarantee future results.',
                        'product_mentions': 'Features subject to change without notice.',
                        'third_party_tools': 'We are not affiliated with mentioned brands.'
                    },
                    'word_blacklist': [
                        'guarantee', 'assured returns', 'risk-free',
                        'cure', 'prevent disease', 'FDA approved'
                    ]
                },
                'enforcement': 'Pre-publish review required',
                'violation_action': 'Block publication, escalate to legal'
            },
            source='company_legal_policy_2024'
        )
        
        # Override SEO practices with brand-first approach
        seo_override = MemoryObservations(
            id=uuid4(),
            entity_id=client_policy.id,
            observation_type='policy_rule',
            observation_value={
                'rule_type': 'SEO Strategy Override',
                'priority': 'OVERRIDE',
                'overrides': ['synth_class_24.seo_techniques.keyword_density'],
                'brand_first_seo': {
                    'principle': 'Brand integrity over keyword optimization',
                    'keyword_density': {
                        'maximum': '0.5%',  # Much lower than class default of 1-2%
                        'rationale': 'Natural language takes precedence'
                    },
                    'title_format': '[Brand] | [Value Prop] - [Topic]',
                    'meta_descriptions': 'Focus on value, not keywords',
                    'link_building': {
                        'approved_sites_only': True,
                        'requires_approval': ['Guest posts', 'Partnerships'],
                        'prohibited': ['Link exchanges', 'PBNs', 'Paid links']
                    }
                },
                'measurement': 'Brand lift > Traffic volume'
            },
            source='brand_guidelines_v3'
        )
        
        # Override performance metrics with company KPIs
        metrics_override = MemoryObservations(
            id=uuid4(),
            entity_id=client_policy.id,
            observation_type='policy_rule',
            observation_value={
                'rule_type': 'Performance Metrics Override',
                'priority': 'OVERRIDE',
                'overrides': ['synth_class_24.performance_metrics'],
                'company_kpis': {
                    'primary_metrics': {
                        'Lead Quality Score': {
                            'weight': '40%',
                            'target': '>7/10',
                            'calculation': 'Based on lead scoring model'
                        },
                        'Pipeline Contribution': {
                            'weight': '35%',
                            'target': '$50K per post quarterly',
                            'attribution': 'First-touch model'
                        },
                        'Brand Sentiment': {
                            'weight': '25%',
                            'target': '>85% positive',
                            'measurement': 'Quarterly survey'
                        }
                    },
                    'deprioritized_metrics': [
                        'Time on page (quality over duration)',
                        'Social shares (focus on qualified audience)',
                        'Traffic volume (quality over quantity)'
                    ]
                },
                'reporting': 'Weekly to CMO, Monthly to board'
            },
            source='company_okr_framework'
        )
        
        # Override content approval workflow
        approval_override = MemoryObservations(
            id=uuid4(),
            entity_id=client_policy.id,
            observation_type='policy_rule',
            observation_value={
                'rule_type': 'Approval Workflow Override',
                'priority': 'OVERRIDE_ALL',
                'overrides': ['synth_class_24.blog_sop.phase_4_qa'],
                'approval_stages': [
                    {
                        'stage': 1,
                        'name': 'AI/Synth Draft',
                        'owner': 'Content synth',
                        'sla': '2 hours',
                        'checklist': ['Grammar', 'Basic facts', 'Format']
                    },
                    {
                        'stage': 2,
                        'name': 'Human Editor Review',
                        'owner': 'Content Manager',
                        'sla': '4 hours',
                        'checklist': ['Tone', 'Accuracy', 'Brand voice']
                    },
                    {
                        'stage': 3,
                        'name': 'Legal Compliance',
                        'owner': 'Legal Team',
                        'sla': '24 hours',
                        'checklist': ['Claims verification', 'Disclaimers', 'IP clearance'],
                        'triggers': ['Financial content', 'Health claims', 'Competitor mentions']
                    },
                    {
                        'stage': 4,
                        'name': 'Final Approval',
                        'owner': 'Marketing Director',
                        'sla': '24 hours',
                        'authority': 'Can override all previous approvals'
                    }
                ],
                'exceptions': {
                    'crisis_communications': 'Skip to Final Approval',
                    'pre_approved_topics': 'Skip Legal if no triggers'
                }
            },
            source='content_governance_policy'
        )
        
        # Add tone and voice override specific to company culture
        voice_override = MemoryObservations(
            id=uuid4(),
            entity_id=client_policy.id,
            observation_type='policy_rule',
            observation_value={
                'rule_type': 'Brand Voice Override',
                'priority': 'OVERRIDE',
                'overrides': ['synth_class_24.style_guide'],
                'brand_voice': {
                    'personality': 'Professional Mentor',
                    'attributes': [
                        'Authoritative but approachable',
                        'Data-driven without being dry',
                        'Innovative yet practical',
                        'Global perspective with local relevance'
                    ],
                    'tone_variations': {
                        'thought_leadership': 'Visionary, forward-thinking',
                        'how_to_content': 'Patient teacher, step-by-step',
                        'company_news': 'Proud but humble',
                        'crisis_response': 'Calm, transparent, solution-focused'
                    },
                    'language_rules': {
                        'pronouns': 'We (company), You (reader), They (competitors)',
                        'forbidden_phrases': [
                            'industry-leading unless verified',
                            'best-in-class without proof',
                            'disrupt or game-changer'
                        ],
                        'preferred_terms': {
                            'customers': 'partners',
                            'employees': 'team members',
                            'problems': 'challenges',
                            'buy': 'invest'
                        }
                    }
                }
            },
            source='brand_voice_guidelines_2024'
        )
        
        # Create override relationship
        # Find the synth_class 24 blog SOP to link
        sop_result = db.execute(text("""
            SELECT id FROM memory_entities
            WHERE actor_type = 'synth_class'
            AND actor_id = '24'
            AND entity_name LIKE '%Blog Writing Standard Operating Procedure%'
            LIMIT 1
        """))
        
        sop = sop_result.fetchone()
        if sop:
            override_rel = MemoryRelations(
                id=uuid4(),
                from_entity_id=client_policy.id,
                to_entity_id=sop[0],
                relation_type='overrides',
                metadata={
                    'override_level': 'complete',
                    'precedence': 'client > synth_class',
                    'description': 'Client policies take precedence over class procedures'
                }
            )
            db.add(override_rel)
            logger.info("✅ Created override relationship to synth_class 24 SOP")
        
        # Add all observations
        observations = [
            content_restrictions,
            seo_override,
            metrics_override,
            approval_override,
            voice_override
        ]
        
        for obs in observations:
            db.add(obs)
            rule_type = obs.observation_value.get('rule_type', 'Policy rule')
            logger.info(f"   - Added {rule_type}")
        
        db.commit()
        logger.info("\n✅ Successfully created client policy overrides")
        
        # Test the override hierarchy
        logger.info("\n🔍 Testing Override Hierarchy:")
        logger.info("-" * 50)
        
        # Show what a synth would see when querying for blog procedures
        result = db.execute(text("""
            SELECT 
                me.entity_name,
                me.actor_type,
                me.actor_id,
                mo.observation_value->>'rule_type' as rule_type,
                mo.observation_value->>'priority' as priority
            FROM memory_entities me
            JOIN memory_observations mo ON mo.entity_id = me.id
            WHERE 
                (me.actor_type = 'synth_class' AND me.actor_id = '24')
                OR (me.actor_type = 'client' AND me.actor_id = :client_id)
            AND mo.observation_type IN ('procedure_phase', 'policy_rule', 'seo_technique')
            ORDER BY 
                CASE 
                    WHEN me.actor_type = 'client' THEN 1
                    WHEN me.actor_type = 'synth_class' THEN 2
                    ELSE 3
                END
            LIMIT 10
        """), {"client_id": client_id})
        
        logger.info("\nHierarchical view (client overrides come first):")
        for row in result:
            actor_desc = f"{row[1]}:{row[2]}"
            logger.info(f"   {row[3] or row[0]} | {actor_desc} | Priority: {row[4] or 'normal'}")
        
        logger.info("\n📊 Summary:")
        logger.info(f"   - Client: {client_name}")
        logger.info(f"   - Policy rules: {len(observations)}")
        logger.info(f"   - Override scope: Complete blog writing procedures")
        logger.info(f"   - Enforcement: Mandatory for all synths in this client")
        
    except Exception as e:
        logger.error(f"❌ Error creating client policy: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_client_policy_override()