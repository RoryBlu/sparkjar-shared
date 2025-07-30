"""
JWT utilities for authentication
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from jose import JWTError, jwt


def create_jwt_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[List[str]] = None
) -> str:
    """
    Create a JWT token with the given data and scopes
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "scopes": scopes or ["sparkjar_internal"]
    })
    
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def verify_jwt_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
    required_scopes: Optional[List[str]] = None
) -> bool:
    """
    Verify a JWT token and optionally check scopes
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        
        if required_scopes:
            token_scopes = payload.get("scopes", [])
            if not all(scope in token_scopes for scope in required_scopes):
                return False
        
        return True
    except JWTError:
        return False


def decode_jwt_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256"
) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token and return the payload
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError:
        return None