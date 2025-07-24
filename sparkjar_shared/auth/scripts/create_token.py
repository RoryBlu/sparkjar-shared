#!/usr/bin/env python3
"""Create a valid JWT token with configurable settings"""

import argparse
import sys
from typing import List
from dotenv import load_dotenv
from services.crew_api.src.api.auth import create_token
from shared.config.shared_settings import ENVIRONMENT
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Token configuration profiles based on environment
TOKEN_PROFILES = {
    "development": {
        "default_scopes": ["sparkjar_internal", "admin", "user"],
        "default_expiry_hours": 24 * 7,  # 1 week for development
        "available_scopes": ["sparkjar_internal", "admin", "user", "read_only", "crew_execute"]
    },
    "staging": {
        "default_scopes": ["sparkjar_internal"],
        "default_expiry_hours": 24,  # 1 day for staging
        "available_scopes": ["sparkjar_internal", "user", "read_only", "crew_execute"]
    },
    "production": {
        "default_scopes": ["sparkjar_internal"],
        "default_expiry_hours": 8,  # 8 hours for production
        "available_scopes": ["sparkjar_internal", "user", "read_only", "crew_execute"]
    }
}

def get_token_profile():
    """Get token configuration profile for current environment."""
    return TOKEN_PROFILES.get(ENVIRONMENT, TOKEN_PROFILES["development"])

def validate_scopes(scopes: List[str]) -> bool:
    """Validate that requested scopes are available in current environment."""
    profile = get_token_profile()
    available_scopes = profile["available_scopes"]
    
    invalid_scopes = [scope for scope in scopes if scope not in available_scopes]
    if invalid_scopes:
        logger.error(f"Invalid scopes for {ENVIRONMENT} environment: {invalid_scopes}")
        logger.info(f"Available scopes: {available_scopes}")
        return False
    
    return True

def create_configurable_token(
    user_id: str = "system",
    scopes: List[str] = None,
    expires_in_hours: int = None
) -> str:
    """
    Create a JWT token with configurable settings based on environment.
    
    Args:
        user_id: User identifier for the token
        scopes: List of permission scopes (defaults to environment profile)
        expires_in_hours: Token expiration time (defaults to environment profile)
        
    Returns:
        JWT token string
    """
    profile = get_token_profile()
    
    # Use defaults from profile if not specified
    if scopes is None:
        scopes = profile["default_scopes"]
    if expires_in_hours is None:
        expires_in_hours = profile["default_expiry_hours"]
    
    # Validate scopes
    if not validate_scopes(scopes):
        raise ValueError(f"Invalid scopes for {ENVIRONMENT} environment")
    
    # Create token
    token = create_token(
        user_id=user_id,
        scopes=scopes,
        expires_in_hours=expires_in_hours
    )
    
    logger.info(f"Created token for user '{user_id}' in {ENVIRONMENT} environment")
    logger.info(f"Scopes: {scopes}")
    logger.info(f"Expires in: {expires_in_hours} hours")
    
    return token

def main():
    """Command-line interface for token creation."""
    parser = argparse.ArgumentParser(description="Create JWT tokens with configurable settings")
    parser.add_argument("--user-id", default="system", help="User ID for the token")
    parser.add_argument("--scopes", nargs="+", help="Token scopes (space-separated)")
    parser.add_argument("--expires-hours", type=int, help="Token expiration in hours")
    parser.add_argument("--list-scopes", action="store_true", help="List available scopes for current environment")
    parser.add_argument("--profile", action="store_true", help="Show current environment profile")
    
    args = parser.parse_args()
    
    try:
        if args.list_scopes:
            profile = get_token_profile()
            logger.info(f"Available scopes for {ENVIRONMENT} environment:")
            for scope in profile["available_scopes"]:
                logger.info(f"  - {scope}")
            return
        
        if args.profile:
            profile = get_token_profile()
            logger.info(f"Token profile for {ENVIRONMENT} environment:")
            logger.info(f"  Default scopes: {profile['default_scopes']}")
            logger.info(f"  Default expiry: {profile['default_expiry_hours']} hours")
            logger.info(f"  Available scopes: {profile['available_scopes']}")
            return
        
        # Create token with specified or default settings
        token = create_configurable_token(
            user_id=args.user_id,
            scopes=args.scopes,
            expires_in_hours=args.expires_hours
        )
        
        logger.info(token)
        
    except Exception as e:
        logger.error(f"Failed to create token: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()