#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Generate a test JWT token for SparkJAR API
"""

import jwt
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def generate_jwt():
    # Get secret from environment
    secret_key = os.getenv('API_SECRET_KEY')
    if not secret_key:
        logger.info("❌ API_SECRET_KEY not found in environment")
        return None
    
    # Create token payload
    payload = {
        'sub': '587f8370-825f-4f0c-8846-2e6d70782989',  # client_user_id
        'scopes': ['sparkjar_internal'],  # Changed to array format expected by API
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow(),
        'iss': 'sparkjar-test'
    }
    
    # Generate token
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    
    return token

if __name__ == "__main__":
    token = generate_jwt()
    if token:
        logger.info(f"🔑 JWT Token generated:\n")
        logger.info(token)
        logger.info(f"\n📋 Export command:")
        logger.info(f"export JWT_TOKEN=\"{token}\"")
        logger.info(f"\n🚀 Test command:")
        logger.info(f"JWT_TOKEN=\"{token}\" ./scripts/test_entity_research_crew.sh")
    else:
        logger.error("Failed to generate token")