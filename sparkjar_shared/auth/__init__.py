"""
Authentication utilities for SparkJAR platform
"""

from .jwt_utils import create_jwt_token, verify_jwt_token, decode_jwt_token
from sparkjar_shared.config.shared_settings import API_SECRET_KEY
from datetime import timedelta
from typing import Dict, Any, Optional

class InvalidTokenError(Exception):
    """Custom exception for invalid tokens"""
    pass

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token and return decoded payload.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        InvalidTokenError: If token is invalid
    """
    payload = decode_jwt_token(token, API_SECRET_KEY)
    if payload is None:
        raise InvalidTokenError("Invalid or expired token")
    return payload

def create_token(subject: str, scopes: list = None, expires_delta: timedelta = None) -> str:
    """
    Create a new JWT token.
    
    Args:
        subject: Token subject (usually user ID or service name)
        scopes: List of permission scopes
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token
    """
    data = {"sub": subject}
    return create_jwt_token(
        data=data,
        secret_key=API_SECRET_KEY,
        expires_delta=expires_delta,
        scopes=scopes or ["sparkjar_internal"]
    )

def get_internal_token() -> str:
    """
    Generate an internal service token for inter-service communication.
    
    Returns:
        JWT token with internal service scopes
    """
    return create_token(
        subject="sparkjar-internal-service",
        scopes=["sparkjar_internal", "crew_execute"],
        expires_delta=timedelta(hours=24)
    )

__all__ = [
    "create_jwt_token", 
    "verify_jwt_token", 
    "decode_jwt_token",
    "verify_token",
    "InvalidTokenError", 
    "create_token",
    "get_internal_token"
]