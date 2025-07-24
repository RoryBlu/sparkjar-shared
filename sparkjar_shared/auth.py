"""
Shared authentication module for all services
"""
import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Get secret from environment or config
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token and return decoded payload.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        jwt.InvalidTokenError: If token is invalid
    """
    try:
        payload = jwt.decode(token, API_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise jwt.InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")

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
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode = {
        "sub": subject,
        "exp": expire,
        "scopes": scopes or []
    }
    
    encoded_jwt = jwt.encode(to_encode, API_SECRET_KEY, algorithm="HS256")
    return encoded_jwt