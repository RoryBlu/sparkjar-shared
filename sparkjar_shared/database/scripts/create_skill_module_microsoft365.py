#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Create Microsoft 365 Suite skill module knowledge.
This represents swappable tool knowledge that synths can subscribe to.
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

def create_microsoft365_skill_module():
    """Create Microsoft 365 Suite skill module with Excel, Word, PowerPoint knowledge"""
    
    logger.info("📚 Creating Microsoft 365 Suite Skill Module")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Skill modules use a special actor_type and actor_id pattern
        ACTOR_TYPE = 'skill_module'
        ACTOR_ID = '365'  # Text ID for Microsoft 365
        
        # Check if skill module already exists
        existing = db.execute(text("""
            SELECT COUNT(*) FROM memory_entities
            WHERE actor_type = :actor_type
            AND actor_id = :actor_id
        """), {"actor_type": ACTOR_TYPE, "actor_id": ACTOR_ID})
        
        if existing.scalar() > 0:
            logger.info("⚠️  Microsoft 365 skill module already exists")
            return
        
        # Create main skill module entity
        skill_module = MemoryEntities(
            id=uuid4(),
            actor_type=ACTOR_TYPE,
            actor_id=ACTOR_ID,
            entity_name='Microsoft 365 Suite Professional Skills',
            entity_type='skill_module',
            metadata={
                'suite_version': '2024',
                'included_applications': ['Excel', 'Word', 'PowerPoint', 'Teams', 'Outlook'],
                'proficiency_level': 'advanced',
                'subscription_type': 'enterprise',
                'last_updated': '2024-01',
                'certification_path': 'Microsoft 365 Certified: Enterprise Administrator Expert'
            }
        )
        
        db.add(skill_module)
        db.flush()
        
        # Create Excel knowledge entity
        excel_entity = MemoryEntities(
            id=uuid4(),
            actor_type=ACTOR_TYPE,
            actor_id=ACTOR_ID,
            entity_name='Excel Advanced Analytics & Automation',
            entity_type='application_knowledge',
            metadata={
                'application': 'Microsoft Excel',
                'version': '365',
                'expertise_areas': ['Data Analysis', 'VBA', 'Power Query', 'Power Pivot']
            }
        )
        
        db.add(excel_entity)
        db.flush()
        
        # Add Excel formula knowledge
        excel_formulas = MemoryObservations(
            id=uuid4(),
            entity_id=excel_entity.id,
            observation_type='technical_skill',
            observation_value={
                'skill': 'Advanced Excel Formulas',
                'category': 'data_manipulation',
                'proficiency': 'expert',
                'key_formulas': {
                    'XLOOKUP': {
                        'purpose': 'Modern replacement for VLOOKUP/HLOOKUP',
                        'syntax': 'XLOOKUP(lookup_value, lookup_array, return_array, [if_not_found], [match_mode], [search_mode])',
                        'example': '=XLOOKUP(A2, Products[ID], Products[Price], "Not Found")',
                        'advantages': ['Works in any direction', 'Default exact match', 'Better error handling']
                    },
                    'FILTER': {
                        'purpose': 'Dynamic array filtering',
                        'syntax': 'FILTER(array, include, [if_empty])',
                        'example': '=FILTER(A2:C100, B2:B100>1000, "No results")',
                        'use_cases': ['Dynamic reports', 'Data extraction', 'Conditional analysis']
                    },
                    'LET': {
                        'purpose': 'Define variables within formulas',
                        'syntax': 'LET(name1, value1, [name2, value2], ..., calculation)',
                        'example': '=LET(x, A1*2, y, B1*3, x+y)',
                        'benefits': ['Improved readability', 'Better performance', 'Easier debugging']
                    }
                },
                'array_formulas': [
                    'Dynamic arrays with UNIQUE, SORT, SORTBY',
                    'Spill ranges with # operator',
                    'SEQUENCE for number generation'
                ]
            },
            source='microsoft_excel_docs_2024'
        )
        
        # Add Power Query knowledge
        power_query = MemoryObservations(
            id=uuid4(),
            entity_id=excel_entity.id,
            observation_type='technical_skill',
            observation_value={
                'skill': 'Power Query M Language',
                'category': 'data_transformation',
                'proficiency': 'advanced',
                'key_concepts': {
                    'data_sources': [
                        'SQL databases',
                        'Web APIs (REST/JSON)',
                        'CSV/Excel files',
                        'SharePoint lists',
                        'Dynamics 365'
                    ],
                    'transformations': {
                        'Table.TransformColumns': 'Apply functions to columns',
                        'Table.Group': 'Group and aggregate data',
                        'Table.Join': 'Merge tables with various join types',
                        'Table.Pivot': 'Pivot data dynamically',
                        'Table.AddColumn': 'Create calculated columns'
                    },
                    'best_practices': [
                        'Use native query folding when possible',
                        'Filter early in the query',
                        'Avoid Table.Buffer unless necessary',
                        'Document steps with clear names',
                        'Parameterize connections'
                    ]
                }
            },
            source='power_query_reference'
        )
        
        # Create Word knowledge entity
        word_entity = MemoryEntities(
            id=uuid4(),
            actor_type=ACTOR_TYPE,
            actor_id=ACTOR_ID,
            entity_name='Word Document Automation & Templates',
            entity_type='application_knowledge',
            metadata={
                'application': 'Microsoft Word',
                'version': '365',
                'expertise_areas': ['Templates', 'Styles', 'Mail Merge', 'Macros']
            }
        )
        
        db.add(word_entity)
        db.flush()
        
        # Add Word automation knowledge
        word_automation = MemoryObservations(
            id=uuid4(),
            entity_id=word_entity.id,
            observation_type='technical_skill',
            observation_value={
                'skill': 'Document Automation',
                'category': 'productivity',
                'proficiency': 'expert',
                'techniques': {
                    'building_blocks': {
                        'purpose': 'Reusable content components',
                        'types': ['AutoText', 'Quick Parts', 'Headers/Footers'],
                        'organization': 'Custom galleries for team sharing'
                    },
                    'content_controls': {
                        'types': ['Rich Text', 'Plain Text', 'Picture', 'Date Picker', 'Drop-Down List'],
                        'use_cases': ['Forms', 'Templates', 'Protected documents'],
                        'programming': 'Access via VBA or Office.js'
                    },
                    'mail_merge': {
                        'data_sources': ['Excel', 'Outlook Contacts', 'SQL Database'],
                        'merge_types': ['Letters', 'Emails', 'Labels', 'Envelopes'],
                        'advanced': ['Rules/IF fields', 'Nested merges', 'Custom formatting']
                    },
                    'styles_themes': {
                        'hierarchy': 'Paragraph → Character → Linked → Table',
                        'best_practices': [
                            'Use built-in heading styles',
                            'Create custom style sets',
                            'Link to external templates',
                            'Organize with style pane'
                        ]
                    }
                }
            },
            source='word_developer_reference'
        )
        
        # Create PowerPoint knowledge entity
        ppt_entity = MemoryEntities(
            id=uuid4(),
            actor_type=ACTOR_TYPE,
            actor_id=ACTOR_ID,
            entity_name='PowerPoint Design & Presentation Automation',
            entity_type='application_knowledge',
            metadata={
                'application': 'Microsoft PowerPoint',
                'version': '365',
                'expertise_areas': ['Design', 'Animation', 'Templates', 'Presenter Tools']
            }
        )
        
        db.add(ppt_entity)
        db.flush()
        
        # Add PowerPoint design knowledge
        ppt_design = MemoryObservations(
            id=uuid4(),
            entity_id=ppt_entity.id,
            observation_type='technical_skill',
            observation_value={
                'skill': 'Advanced PowerPoint Design',
                'category': 'visual_communication',
                'proficiency': 'expert',
                'capabilities': {
                    'slide_master': {
                        'purpose': 'Consistent design across presentations',
                        'components': ['Layouts', 'Themes', 'Color schemes', 'Font sets'],
                        'best_practices': [
                            'Create custom layouts for each content type',
                            'Use placeholders for consistency',
                            'Lock background elements',
                            'Version control master templates'
                        ]
                    },
                    'designer_ai': {
                        'features': ['Design Ideas', 'Icons insertion', 'Smart Art conversion'],
                        'customization': 'Train with brand guidelines',
                        'integration': 'Works with company templates'
                    },
                    'morph_transition': {
                        'use_cases': ['Object animation', 'Text reveals', 'Chart builds'],
                        'requirements': 'Named objects across slides',
                        'advanced': 'Combine with trigger animations'
                    },
                    'data_visualization': {
                        'chart_types': ['Sunburst', 'Treemap', 'Waterfall', 'Funnel'],
                        'live_data': 'Link to Excel for auto-updates',
                        'animations': 'Series by series reveal'
                    }
                }
            },
            source='powerpoint_design_guide'
        )
        
        # Create Teams integration entity
        teams_entity = MemoryEntities(
            id=uuid4(),
            actor_type=ACTOR_TYPE,
            actor_id=ACTOR_ID,
            entity_name='Teams Collaboration & Integration Hub',
            entity_type='application_knowledge',
            metadata={
                'application': 'Microsoft Teams',
                'version': '365',
                'expertise_areas': ['Channels', 'Apps', 'Meetings', 'Automation']
            }
        )
        
        db.add(teams_entity)
        db.flush()
        
        # Add Teams automation
        teams_automation = MemoryObservations(
            id=uuid4(),
            entity_id=teams_entity.id,
            observation_type='technical_skill',
            observation_value={
                'skill': 'Teams Platform Development',
                'category': 'collaboration',
                'proficiency': 'advanced',
                'capabilities': {
                    'power_automate': {
                        'triggers': ['New message', 'Mentioned', 'File uploaded'],
                        'actions': ['Post message', 'Create task', 'Update Planner'],
                        'templates': ['Approval workflows', 'Notifications', 'Data collection']
                    },
                    'apps_tabs': {
                        'types': ['Personal apps', 'Channel tabs', 'Meeting apps'],
                        'frameworks': ['SharePoint Framework', 'Power Apps', 'Custom web apps'],
                        'distribution': 'Teams App Store or LOB apps'
                    },
                    'adaptive_cards': {
                        'purpose': 'Rich interactive messages',
                        'components': ['Input forms', 'Action buttons', 'Dynamic content'],
                        'use_cases': ['Polls', 'Approvals', 'Status updates']
                    }
                }
            },
            source='teams_developer_docs'
        )
        
        # Create relationships between skill module and components
        relationships = [
            {
                'from_id': excel_entity.id,
                'to_id': skill_module.id,
                'type': 'component_of'
            },
            {
                'from_id': word_entity.id,
                'to_id': skill_module.id,
                'type': 'component_of'
            },
            {
                'from_id': ppt_entity.id,
                'to_id': skill_module.id,
                'type': 'component_of'
            },
            {
                'from_id': teams_entity.id,
                'to_id': skill_module.id,
                'type': 'component_of'
            }
        ]
        
        for rel in relationships:
            relationship = MemoryRelations(
                id=uuid4(),
                from_entity_id=rel['from_id'],
                to_entity_id=rel['to_id'],
                relation_type=rel['type'],
                metadata={'created_by': 'skill_module_system'}
            )
            db.add(relationship)
        
        # Add all observations
        observations = [excel_formulas, power_query, word_automation, ppt_design, teams_automation]
        for obs in observations:
            db.add(obs)
        
        db.commit()
        logger.info("✅ Successfully created Microsoft 365 skill module")
        
        # Summary
        logger.info("\n📊 Skill Module Summary:")
        logger.info(f"   - Main module: Microsoft 365 Suite")
        logger.info(f"   - Applications: 4 (Excel, Word, PowerPoint, Teams)")
        logger.info(f"   - Technical skills: {len(observations)}")
        logger.info(f"   - Relationships: {len(relationships)}")
        
        logger.info("\n🔑 Skill Module Access Pattern:")
        logger.info(f"   - actor_type: '{ACTOR_TYPE}'")
        logger.info(f"   - actor_id: '{ACTOR_ID}'")
        logger.info("   - Synths can subscribe to this module for Office 365 expertise")
        
    except Exception as e:
        logger.error(f"❌ Error creating skill module: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_microsoft365_skill_module()