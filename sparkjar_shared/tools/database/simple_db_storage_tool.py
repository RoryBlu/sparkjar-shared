"""Simple Database Storage Tool for Book Ingestion."""
import logging
import json
from typing import Any
from crewai.tools import BaseTool
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime

from src.database.models import ClientUsers, ClientSecrets, BookIngestions

logger = logging.getLogger(__name__)


class SimpleDBStorageTool(BaseTool):
    name: str = "simple_db_storage"
    description: str = "Store book page to database. Pass all parameters as a single JSON string."
    
    def __init__(self):
        super().__init__()
        self._engine = None
    
    async def _store_page(self, params: dict) -> dict:
        """Store page in database."""
        # Get client database URL
        from src.database.connection import get_db_session
        
        async with get_db_session() as session:
            # Get user's client_id
            result = await session.execute(
                select(ClientUsers).filter_by(id=params['client_user_id'])
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError(f"User not found")
            
            # Get database URL
            secrets_result = await session.execute(
                select(ClientSecrets).filter_by(
                    client_id=user.clients_id,
                    secret_key="database_url"
                )
            )
            secret = secrets_result.scalar_one_or_none()
            
            if not secret:
                raise ValueError(f"Database URL not found")
            
            db_url = secret.secret_value
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Connect to client database
        engine = create_async_engine(db_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        try:
            async with async_session() as session:
                # Check if page already exists
                existing = await session.execute(
                    select(BookIngestions).filter_by(
                        book_key=params['book_key'],
                        page_number=params['page_number'],
                        version=params.get('version', 'original')
                    )
                )
                page = existing.scalar_one_or_none()
                
                if page:
                    # Update existing
                    page.file_name = params['file_name']
                    page.page_text = params['page_text']
                    page.ocr_metadata = params.get('ocr_metadata', {})
                    page.updated_at = datetime.utcnow()
                else:
                    # Create new
                    page = BookIngestions(
                        book_key=params['book_key'],
                        page_number=params['page_number'],
                        file_name=params['file_name'],
                        language_code=params['language_code'],
                        version=params.get('version', 'original'),
                        page_text=params['page_text'],
                        ocr_metadata=params.get('ocr_metadata', {})
                    )
                    session.add(page)
                
                await session.commit()
                await session.refresh(page)
                
                return {
                    "success": True,
                    "page_id": str(page.id),
                    "page_number": page.page_number
                }
        finally:
            await engine.dispose()
    
    def _run(self, input: str) -> str:
        """Execute storage."""
        try:
            # Parse input - it might be wrapped in various ways
            if isinstance(input, dict):
                params = input
            else:
                # Try to parse as JSON
                try:
                    params = json.loads(input)
                except:
                    # Try to extract JSON from string
                    import re
                    json_match = re.search(r'\{.*\}', input, re.DOTALL)
                    if json_match:
                        params = json.loads(json_match.group())
                    else:
                        return json.dumps({"success": False, "error": "Could not parse input"})
            
            # Run async operation
            result = asyncio.run(self._store_page(params))
            return json.dumps(result)
            
        except Exception as e:
            logger.error(f"Storage error: {e}")
            return json.dumps({"success": False, "error": str(e)})