"""Fixed Simple Database Query Tool for Book Translation."""
import logging
import asyncio
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from datetime import datetime

from database.models import ClientUsers, ClientSecrets

logger = logging.getLogger(__name__)


class SimpleDBQueryInput(BaseModel):
    """Input schema for database query tool."""
    client_user_id: str = Field(..., description="The client user ID")
    book_key: str = Field(..., description="The book key to query")
    version: str = Field(default="original", description="Version of the book to query")


class SimpleDBQueryToolFixed(BaseTool):
    name: str = "simple_db_query"
    description: str = "Query book pages from database for a specific book key and version"
    args_schema: Type[BaseModel] = SimpleDBQueryInput
    
    def __init__(self):
        super().__init__()
    
    async def _query_pages(self, client_user_id: str, book_key: str, version: str) -> dict:
        """Query pages from client database."""
        # Get client database URL
        from database.connection import get_db_session
        
        async with get_db_session() as session:
            # Get user's client_id
            result = await session.execute(
                select(ClientUsers).filter_by(id=client_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Get database URL
            secrets_result = await session.execute(
                select(ClientSecrets).filter_by(
                    client_id=user.clients_id,
                    secret_key="database_url"
                )
            )
            secret = secrets_result.scalar_one_or_none()
            
            if not secret:
                return {"success": False, "error": "Database URL not found"}
            
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
                    LIMIT 5
                """)
                
                result = await session.execute(
                    query,
                    {
                        "book_key": book_key,
                        "version": version
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
                
                return {
                    "success": True,
                    "pages": pages,
                    "count": len(pages)
                }
        except Exception as e:
            logger.error(f"Error querying pages: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            await engine.dispose()
    
    def _run(self, client_user_id: str, book_key: str, version: str = "original") -> str:
        """Run the tool to query pages."""
        try:
            # Create new event loop for async operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._query_pages(client_user_id, book_key, version)
                )
                
                if result["success"]:
                    # Format pages for agent consumption
                    output = f"Found {result['count']} pages:\n\n"
                    for page in result["pages"]:
                        output += f"Page {page['page_number']}:\n"
                        output += f"{page['page_text']}\n"
                        output += "-" * 80 + "\n\n"
                    return output
                else:
                    return f"Error: {result['error']}"
                    
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error in _run: {e}")
            return f"Error: {str(e)}"