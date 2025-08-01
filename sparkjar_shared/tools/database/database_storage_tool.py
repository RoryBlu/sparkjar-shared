"""Database Storage Tool for Book Ingestion Crew."""
import logging
from typing import Dict, Any, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import asyncio
import json
from datetime import datetime

from database.models import ClientUsers, ClientSecrets, BookIngestions

logger = logging.getLogger(__name__)


class DatabaseStorageInput(BaseModel):
    """Input schema for database storage tool."""
    params: str = Field(description="JSON string with storage parameters")


class DatabaseStorageTool(BaseTool):
    name: str = "database_storage"
    description: str = """Store transcribed book pages to client database.
    
    This tool:
    1. Looks up the client database URL from client_secrets
    2. Connects to the client-specific database
    3. Stores the transcribed page in book_ingestions table
    4. Returns confirmation with the stored record ID
    """
    
    def __init__(self):
        super().__init__()
        self._engine_cache = {}
    
    async def _get_client_db_url(self, client_user_id: str) -> str:
        """Get client database URL from secrets."""
        # Import here to avoid circular imports
        from database.connection import get_db_session
        
        async with get_db_session() as session:
            # Get user's client_id
            result = await session.execute(
                select(ClientUsers).filter_by(id=client_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError(f"User {client_user_id} not found")
            
            # Get database URL from secrets
            secrets_result = await session.execute(
                select(ClientSecrets).filter_by(
                    client_id=user.clients_id,
                    secret_key="database_url"
                )
            )
            secret = secrets_result.scalar_one_or_none()
            
            if not secret:
                raise ValueError(f"Database URL not found for client {user.clients_id}")
            
            return secret.secret_value
    
    async def _get_client_engine(self, client_user_id: str):
        """Get or create engine for client database."""
        if client_user_id not in self._engine_cache:
            db_url = await self._get_client_db_url(client_user_id)
            
            # Convert to async URL if needed
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            self._engine_cache[client_user_id] = create_async_engine(
                db_url,
                echo=False,
                pool_pre_ping=True
            )
        
        return self._engine_cache[client_user_id]
    
    async def _store_page_async(self, input_data) -> Dict[str, Any]:
        """Store page in client database asynchronously."""
        engine = await self._get_client_engine(input_data.client_user_id)
        
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            # Create new book ingestion record
            page = BookIngestions(
                book_key=input_data.book_key,
                page_number=input_data.page_number,
                file_name=input_data.file_name,
                language_code=input_data.language_code,
                version=input_data.version,
                page_text=input_data.page_text,
                ocr_metadata=input_data.ocr_metadata
            )
            
            session.add(page)
            await session.commit()
            await session.refresh(page)
            
            return {
                "success": True,
                "page_id": str(page.id),
                "book_key": page.book_key,
                "page_number": page.page_number,
                "stored_at": page.created_at.isoformat() if page.created_at else datetime.now().isoformat()
            }
    
    def _run(self, params: str) -> str:
        """Execute the storage operation."""
        try:
            # Parse JSON params
            if isinstance(params, str):
                storage_params = json.loads(params)
            else:
                storage_params = params
            
            # Create storage input from params
            class StorageParams(BaseModel):
                client_user_id: str
                book_key: str
                page_number: int
                file_name: str
                language_code: str
                page_text: str
                ocr_metadata: Dict[str, Any]
                version: str = "original"
            
            input_data = StorageParams(**storage_params)
            
            # Run async operation
            result = asyncio.run(self._store_page_async(input_data))
            
            return json.dumps(result)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return json.dumps({
                "success": False,
                "error": f"Invalid JSON: {str(e)}"
            })
        except Exception as e:
            logger.error(f"Database storage error: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            })
    
    def __del__(self):
        """Clean up database connections."""
        for engine in self._engine_cache.values():
            asyncio.run(engine.dispose())