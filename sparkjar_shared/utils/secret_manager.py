"""
Secret manager for handling client-specific credentials.

Retrieves client secrets from the database, not environment variables.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from src.database.connection import get_db_session
from src.database.models import ClientSecrets
from src.utils.crew_logger import setup_logging

logger = setup_logging(__name__)


class SecretManager:
    """Manages client-specific secrets stored in the database."""
    
    @staticmethod
    def get_client_secret(client_id: str, secret_name: str) -> Optional[str]:
        """
        Get a client-specific secret from the database.
        
        Args:
            client_id: Client identifier
            secret_name: Name of the secret
            
        Returns:
            Secret value or None if not found
        """
        try:
            with get_db_session() as session:
                secret = session.query(ClientSecrets).filter(
                    ClientSecrets.client_id == client_id,
                    ClientSecrets.secret_key == secret_name,
                ).first()
                
                if secret:
                    logger.info(f"Retrieved secret '{secret_name}' for client '{client_id}'")
                    return secret.secret_value
                else:
                    logger.warning(f"Secret '{secret_name}' not found for client '{client_id}'")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving secret: {str(e)}")
            return None
    
    @staticmethod
    def set_client_secret(client_id: str, secret_name: str, secret_value: str, 
                         actor_type: str = None, actor_id: str = None) -> bool:
        """
        Store or update a client secret in the database.
        
        Args:
            client_id: Client identifier
            secret_name: Name of the secret
            secret_value: Secret value to store
            actor_type: Optional actor type
            actor_id: Optional actor ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                # Check if secret already exists
                existing = session.query(ClientSecrets).filter(
                    ClientSecrets.client_id == client_id,
                    ClientSecrets.secret_key == secret_name
                ).first()
                
                if existing:
                    # Update existing secret
                    existing.secret_value = secret_value
                    existing.updated_at = datetime.utcnow()
                    if actor_type:
                        existing.actor_type = actor_type
                    if actor_id:
                        existing.actor_id = actor_id
                else:
                    # Create new secret
                    new_secret = ClientSecrets(
                        client_id=client_id,
                        secret_key=secret_name,
                        secret_value=secret_value,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        secrets_metadata={}
                    )
                    session.add(new_secret)
                
                session.commit()
                logger.info(f"Stored secret '{secret_name}' for client '{client_id}'")
                return True
                
        except Exception as e:
            logger.error(f"Error storing secret: {str(e)}")
            return False
    
    @staticmethod
    def get_all_client_secrets(client_id: str) -> Dict[str, str]:
        """
        Get all active secrets for a specific client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Dictionary of secret names to values
        """
        try:
            with get_db_session() as session:
                secrets = session.query(ClientSecrets).filter(
                    ClientSecrets.client_id == client_id
                ).all()
                
                result = {
                    secret.secret_key: secret.secret_value 
                    for secret in secrets
                }
                
                if result:
                    logger.info(f"Found {len(result)} secrets for client '{client_id}'")
                else:
                    logger.warning(f"No secrets found for client '{client_id}'")
                
                return result
                
        except Exception as e:
            logger.error(f"Error retrieving secrets: {str(e)}")
            return {}