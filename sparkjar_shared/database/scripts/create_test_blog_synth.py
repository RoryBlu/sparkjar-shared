#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Create a test synth with blog writer class (24) to test hierarchical memory access.
"""
import os
import sys
from uuid import UUID, uuid4
from datetime import datetime
from pathlib import Path

# Add parent directory to Python path
# Add crew-api path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from crew-api models
from services.crew_api.src.database.models import Synths, SynthClasses, Clients
from sparkjar_crew.shared.config.config import DATABASE_URL_DIRECT

# Create synchronous engine for this script
engine = create_engine(DATABASE_URL_DIRECT.replace('postgresql+asyncpg', 'postgresql'))
SessionLocal = sessionmaker(bind=engine)

def create_test_synth():
    """Create a test synth with blog writer class"""
    
    logger.info("🚀 Creating test synth with blog writer class (24)")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # First, verify synth_class 24 exists
        synth_class = db.query(SynthClasses).filter(
            SynthClasses.id == 24
        ).first()
        
        if not synth_class:
            logger.info("❌ Synth class 24 not found in database!")
            logger.info("   Creating synth_class 24...")
            
            synth_class = SynthClasses(
                id=24,
                job_key='blog_writer',
                title='Blog Writer',
                description='Professional blog content creator specializing in SEO-optimized articles',
                default_attributes={
                    "specialization": "Content Creation",
                    "skills": ["Blog Writing", "SEO", "Research", "Content Strategy"],
                    "tools": ["Google Analytics", "SEMrush", "Grammarly"]
                }
            )
            db.add(synth_class)
            db.commit()
            logger.info(f"   ✅ Created synth_class 24: {synth_class.title}")
        else:
            logger.info(f"   ✅ Found synth_class 24: {synth_class.title}")
        
        # Get a test client (using first available client)
        client = db.query(Clients).first()
        
        if not client:
            logger.info("❌ No clients found in database!")
            logger.info("   Creating test client...")
            
            client = Clients(
                id=uuid4(),
                legal_name='Test Company Inc.',
                display_name='Test Company',
                domain='testcompany.com',
                website_url='https://testcompany.com',
                industry='Technology',
                status='active',
                client_key='test_company',
                client_metadata={}
            )
            db.add(client)
            db.commit()
            logger.info(f"   ✅ Created test client: {client.display_name}")
        else:
            logger.info(f"   ✅ Using existing client: {client.display_name or client.legal_name}")
        
        # Create test synth
        test_synth = Synths(
            id=uuid4(),
            client_id=client.id,
            synth_classes_id=24,  # Blog writer class
            first_name='Sarah',
            last_name='BlogWriter',
            preferred_name='Sarah',
            backstory='Sarah is an experienced blog writer with 10 years of experience in content creation. She specializes in SEO-optimized articles and has a talent for making complex topics accessible to readers.',
            attributes={
                "experience_years": 10,
                "specialties": ["Technology", "Business", "Lifestyle"],
                "writing_style": "Professional yet conversational",
                "certifications": ["Google Analytics", "HubSpot Content Marketing"],
                "languages": ["English", "Spanish"],
                "personality_traits": ["detail-oriented", "creative", "deadline-driven"]
            }
        )
        
        db.add(test_synth)
        db.commit()
        
        logger.info(f"\n✅ Successfully created test synth!")
        logger.info(f"   - ID: {test_synth.id}")
        logger.info(f"   - Name: {test_synth.first_name} {test_synth.last_name}")
        logger.info(f"   - Class: {synth_class.title} (ID: {test_synth.synth_classes_id})")
        logger.info(f"   - Client: {client.display_name or client.legal_name}")
        
        logger.info(f"\n📋 Synth Details:")
        logger.info(f"   - Actor Type: synth")
        logger.info(f"   - Actor ID: {test_synth.id}")
        logger.info(f"   - Can access:")
        logger.info(f"     • Own memories (synth context)")
        logger.info(f"     • Class knowledge (synth_class 24)")
        logger.info(f"     • Client policies (when implemented)")
        
        return {
            "synth_id": str(test_synth.id),
            "synth_name": f"{test_synth.first_name} {test_synth.last_name}",
            "synth_class_id": test_synth.synth_classes_id,
            "client_id": str(test_synth.client_id),
            "client_name": client.display_name or client.legal_name
        }
        
    except Exception as e:
        logger.error(f"❌ Error creating test synth: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    result = create_test_synth()
    
    if result:
        logger.info("\n🎯 Next steps:")
        logger.info("   1. Test hierarchical memory retrieval with this synth")
        logger.info("   2. Verify synth can access blog writing procedures")
        logger.info("   3. Test that synth CANNOT access other class knowledge")
        
        # Save synth details for next test
        import json
        test_file = Path(__file__).parent / 'test_synth_details.json'
        with open(test_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"\n💾 Synth details saved to: {test_file}")