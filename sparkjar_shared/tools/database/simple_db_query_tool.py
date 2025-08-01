"""Simple Database Query Tool for Book Translation."""
import logging
import json
from typing import Any
from crewai.tools import BaseTool
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from datetime import datetime

from src.database.models import ClientUsers, ClientSecrets

logger = logging.getLogger(__name__)


class SimpleDBQueryTool(BaseTool):
    name: str = "simple_db_query"
    description: str = "Query book pages from database. Pass parameters as JSON: {\"client_user_id\": \"...\", \"book_key\": \"...\", \"version\": \"original\"}"
    
    def __init__(self):
        super().__init__()
    
    async def _query_pages(self, params: dict) -> list:
        """Query pages from client database."""
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
                # Query pages directly
                query = text("""
                    SELECT page_number, page_text, file_name, language_code
                    FROM book_ingestions
                    WHERE book_key = :book_key 
                    AND version = :version
                    ORDER BY page_number
                """)
                
                result = await session.execute(
                    query,
                    {
                        "book_key": params['book_key'],
                        "version": params.get('version', 'original')
                    }
                )
                
                pages = []
                for row in result.fetchall():
                    pages.append({
                        "page_number": row.page_number,
                        "page_text": row.page_text,
                        "file_name": row.file_name,
                        "language_code": row.language_code
                    })
                
                return pages
        finally:
            await engine.dispose()
    
    def _run(self, input_data: str) -> str:
        """Run the tool to query pages."""
        try:
            # Parse input
            params = json.loads(input_data)
            
            # Run async query
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                pages = loop.run_until_complete(self._query_pages(params))
                return json.dumps({
                    "success": True,
                    "pages": pages,
                    "count": len(pages)
                })
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error querying pages: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            })