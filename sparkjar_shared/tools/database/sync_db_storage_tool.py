"""Synchronous Database Storage Tool for Book Ingestion."""
import logging
import json
import os
import re
from typing import Any, Type, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from sparkjar_shared.database.models import BookIngestions, ClientUsers, ClientSecrets

logger = logging.getLogger(__name__)


class SyncDBStorageToolSchema(BaseModel):
    """Input schema for SyncDBStorageTool - accepts parameters directly."""
    client_user_id: str = Field(description="Client user ID")
    book_key: str = Field(description="Book key identifier")
    page_number: Optional[int] = Field(default=None, description="Page number (will be extracted from filename if not provided)")
    file_name: str = Field(description="File name")
    language_code: str = Field(description="Language code")
    page_text: str = Field(description="Transcribed text from OCR")
    ocr_metadata: dict = Field(default={}, description="OCR metadata")
    version: str = Field(default="original", description="Version of the transcription")


class SyncDBStorageTool(BaseTool):
    name: str = "sync_db_storage"
    description: str = """Store book page to database using synchronous operations.
    
    This tool:
    1. Extracts page number from filename if not provided
    2. Looks up client database URL from client_secrets
    3. Connects to the client-specific database using synchronous operations
    4. Stores the transcribed page in book_ingestions table with proper transaction management
    5. Returns confirmation with the stored record ID
    """
    args_schema: Type[BaseModel] = SyncDBStorageToolSchema
    
    def __init__(self):
        super().__init__()
        self._engine_cache = {}
    
    def _extract_page_number_from_filename(self, filename: str) -> Optional[int]:
        """Extract page number from filename using various patterns."""
        try:
            # Remove file extension
            name_without_ext = os.path.splitext(filename)[0]
            
            # Common patterns for page numbers in filenames (ordered by specificity)
            patterns = [
                r'page[_\s-]*(\d+)',          # page_1, page 1, page1, page-1
                r'p[_\s-]*(\d+)',             # p_1, p 1, p1, p-1
                r'pg[_\s-]*(\d+)',            # pg_1, pg 1, pg1, pg-1
                r'[_\s-](\d+)[_\s-]',         # number surrounded by separators
                r'[_\s-](\d+)(?:_[a-zA-Z])', # number followed by underscore and word (like _version2)
                r'(\d+)$',                    # ending with number: file_001, scan_1
                r'^(\d+)',                    # starting with number: 001_page
                r'(\d{3,})',                  # any sequence of 3+ digits (likely page numbers)
                r'(\d{2})',                   # any sequence of 2 digits as fallback
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, name_without_ext, re.IGNORECASE)
                for match in matches:
                    page_num = int(match.group(1))
                    # Reasonable page number validation (1-9999)
                    if 1 <= page_num <= 9999:
                        # Additional validation: prefer numbers that look like page numbers
                        # Skip very large numbers that are likely dates or IDs
                        if page_num > 2024 and len(str(page_num)) >= 4:
                            # Could be a year, check if there are other candidates
                            continue
                        logger.info(f"Extracted page number {page_num} from filename: {filename}")
                        return page_num
            
            logger.warning(f"Could not extract page number from filename: {filename}")
            return None
            
        except (ValueError, AttributeError) as e:
            logger.error(f"Error extracting page number from filename {filename}: {e}")
            return None
    
    def _get_client_db_url(self, client_user_id: str) -> str:
        """Get client database URL from secrets using synchronous operations."""
        try:
            # Use main database URL for client lookup
            main_db_url = os.getenv('DATABASE_URL_DIRECT')
            if not main_db_url:
                raise ValueError("DATABASE_URL_DIRECT not configured")
            
            # Convert to sync URL
            sync_url = main_db_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
            engine = create_engine(sync_url, pool_pre_ping=True)
            Session = sessionmaker(bind=engine)
            
            try:
                with Session() as session:
                    # Get user's client_id
                    user_result = session.execute(
                        select(ClientUsers).filter_by(id=client_user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    
                    if not user:
                        raise ValueError(f"User {client_user_id} not found")
                    
                    # Get database URL from secrets
                    secrets_result = session.execute(
                        select(ClientSecrets).filter_by(
                            client_id=user.clients_id,
                            secret_key="database_url"
                        )
                    )
                    secret = secrets_result.scalar_one_or_none()
                    
                    if not secret:
                        raise ValueError(f"Database URL not found for client {user.clients_id}")
                    
                    return secret.secret_value
            finally:
                engine.dispose()
                
        except SQLAlchemyError as e:
            logger.error(f"Database error getting client URL: {e}")
            raise ValueError(f"Failed to get client database URL: {str(e)}")
    
    def _get_client_engine(self, client_user_id: str):
        """Get or create synchronous engine for client database."""
        if client_user_id not in self._engine_cache:
            db_url = self._get_client_db_url(client_user_id)
            
            # Convert to sync URL if needed
            if db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
            elif db_url.startswith("postgresql://"):
                # Ensure we use psycopg2 for sync operations
                db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            
            self._engine_cache[client_user_id] = create_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_timeout=30,
                pool_size=5,
                max_overflow=10
            )
        
        return self._engine_cache[client_user_id]
    
    def _store_page_sync(self, input_data: SyncDBStorageToolSchema) -> dict:
        """Store page in client database synchronously with proper transaction management."""
        engine = self._get_client_engine(input_data.client_user_id)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        
        with Session() as session:
            try:
                # Extract page number if not provided
                page_number = input_data.page_number
                if page_number is None:
                    page_number = self._extract_page_number_from_filename(input_data.file_name)
                    if page_number is None:
                        raise ValueError(f"Could not determine page number from filename: {input_data.file_name}")
                
                # Check if page already exists (for upsert behavior)
                existing_page = session.execute(
                    select(BookIngestions).filter_by(
                        book_key=input_data.book_key,
                        page_number=page_number,
                        version=input_data.version
                    )
                ).scalar_one_or_none()
                
                if existing_page:
                    # Update existing page
                    existing_page.file_name = input_data.file_name
                    existing_page.language_code = input_data.language_code
                    existing_page.page_text = input_data.page_text
                    existing_page.ocr_metadata = input_data.ocr_metadata
                    existing_page.updated_at = datetime.utcnow()
                    
                    session.commit()
                    
                    logger.info(f"Updated existing page {page_number} for book {input_data.book_key}")
                    
                    return {
                        "success": True,
                        "page_id": str(existing_page.id),
                        "book_key": existing_page.book_key,
                        "page_number": existing_page.page_number,
                        "action": "updated",
                        "stored_at": existing_page.updated_at.isoformat() if existing_page.updated_at else datetime.utcnow().isoformat()
                    }
                else:
                    # Create new page
                    new_page = BookIngestions(
                        book_key=input_data.book_key,
                        page_number=page_number,
                        file_name=input_data.file_name,
                        language_code=input_data.language_code,
                        version=input_data.version,
                        page_text=input_data.page_text,
                        ocr_metadata=input_data.ocr_metadata
                    )
                    
                    session.add(new_page)
                    session.commit()
                    session.refresh(new_page)
                    
                    logger.info(f"Created new page {page_number} for book {input_data.book_key}")
                    
                    return {
                        "success": True,
                        "page_id": str(new_page.id),
                        "book_key": new_page.book_key,
                        "page_number": new_page.page_number,
                        "action": "created",
                        "stored_at": new_page.created_at.isoformat() if new_page.created_at else datetime.utcnow().isoformat()
                    }
                    
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing page: {e}")
                raise
    
    def _run(self, **kwargs) -> str:
        """Execute storage with direct parameters."""
        try:
            # Create input data model for validation
            input_data = SyncDBStorageToolSchema(**kwargs)
            
            # Store page with proper transaction management
            result = self._store_page_sync(input_data)
            
            return json.dumps(result)
            
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return json.dumps({
                "success": False,
                "error": f"Validation error: {str(e)}"
            })
        except SQLAlchemyError as e:
            logger.error(f"Database error: {e}")
            return json.dumps({
                "success": False,
                "error": f"Database error: {str(e)}"
            })
        except Exception as e:
            logger.error(f"Unexpected error in SyncDBStorageTool: {e}")
            return json.dumps({
                "success": False,
                "error": f"Storage failed: {str(e)}"
            })
    
    def __del__(self):
        """Clean up database connections."""
        for engine in self._engine_cache.values():
            try:
                engine.dispose()
            except Exception as e:
                logger.debug(f"Error disposing engine during cleanup: {e}")