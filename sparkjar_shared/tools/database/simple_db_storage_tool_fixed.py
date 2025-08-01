"""Fixed Simple Database Storage Tool for translations."""
import logging
import asyncio
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from datetime import datetime
import json

from database.models import ClientUsers, ClientSecrets

logger = logging.getLogger(__name__)


class SimpleDBStorageInput(BaseModel):
    """Input schema for database storage tool."""
    client_user_id: str = Field(..., description="The client user ID")
    book_key: str = Field(..., description="The book key")
    page_number: int = Field(..., description="Page number")
    page_text: str = Field(..., description="Translated text for the page")
    file_name: str = Field(..., description="File name for the page")
    version: str = Field(..., description="Version identifier (e.g., 'translation_en')")
    language_code: str = Field(..., description="Target language code")


class SimpleDBStorageToolFixed(BaseTool):
    name: str = "simple_db_storage"
    description: str = "Store translated book page to database"
    args_schema: Type[BaseModel] = SimpleDBStorageInput
    
    def __init__(self):
        super().__init__()
    
    async def _store_page(
        self, 
        client_user_id: str,
        book_key: str,
        page_number: int,
        page_text: str,
        file_name: str,
        version: str,
        language_code: str
    ) -> dict:
        """Store page in client database."""
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
                # Insert translated page
                query = text("""
                    INSERT INTO book_ingestions 
                    (book_key, page_number, page_text, file_name, language_code, version, created_at, updated_at)
                    VALUES (:book_key, :page_number, :page_text, :file_name, :language_code, :version, NOW(), NOW())
                    ON CONFLICT (book_key, page_number, version) 
                    DO UPDATE SET 
                        page_text = EXCLUDED.page_text,
                        updated_at = NOW()
                """)
                
                await session.execute(
                    query,
                    {
                        "book_key": book_key,
                        "page_number": page_number,
                        "page_text": page_text,
                        "file_name": file_name,
                        "language_code": language_code,
                        "version": version
                    }
                )
                
                await session.commit()
                
                return {
                    "success": True,
                    "message": f"Page {page_number} stored successfully"
                }
                
        except Exception as e:
            logger.error(f"Error storing page: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            await engine.dispose()
    
    def _run(
        self, 
        client_user_id: str,
        book_key: str,
        page_number: int,
        page_text: str,
        file_name: str,
        version: str,
        language_code: str
    ) -> str:
        """Run the tool to store a page."""
        try:
            # Create new event loop for async operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._store_page(
                        client_user_id,
                        book_key,
                        page_number,
                        page_text,
                        file_name,
                        version,
                        language_code
                    )
                )
                
                if result["success"]:
                    return result["message"]
                else:
                    return f"Error: {result['error']}"
                    
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error in _run: {e}")
            return f"Error: {str(e)}"