"""
Embedding generator tool for creating overlapping text embeddings.

This tool is integrated into the database storage tool but can also
be used independently for re-processing or analysis.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from crewai.tools import BaseTool
from sqlalchemy import create_engine, text
import uuid

from src.utils.crew_logger import setup_logging
from src.utils.embedding_client import EmbeddingClient

logger = setup_logging(__name__)


class EmbeddingGeneratorTool(BaseTool):
    """Generates overlapping embeddings for text chunks."""
    
    name: str = "embedding_generator"
    description: str = "Generate overlapping embeddings for semantic search"
    
    def __init__(self, **kwargs):
        """Initialize with embedding client."""
        super().__init__(**kwargs)
        self.embedding_client = EmbeddingClient()
    
    def _run(self,
             page_id: str,
             page_text: str,
             metadata: Dict[str, Any],
             chunk_size: int = 512,
             overlap_size: int = 128) -> str:
        """
        Generate embeddings for a page of text.
        
        Args:
            page_id: UUID of the page in book_ingestions table
            page_text: Text content to embed
            metadata: Metadata for embeddings (book_key, page_number, etc.)
            chunk_size: Size of each chunk in characters
            overlap_size: Overlap between chunks
            
        Returns:
            JSON string with embedding statistics
        """
        try:
            chunks = self._create_overlapping_chunks(
                page_text, 
                chunk_size, 
                overlap_size
            )
            
            logger.info(f"Creating {len(chunks)} embeddings for page {metadata.get('page_number')}")
            
            embeddings = []
            for idx, (chunk_text, start, end) in enumerate(chunks):
                # Generate embedding
                embedding_vector = self.embedding_client.create_embedding(chunk_text)
                
                # Prepare embedding metadata
                embedding_metadata = {
                    **metadata,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "overlap_chars": overlap_size,
                    "model": "text-embedding-3-small",
                    "dimension": 1536,
                    "token_count": self._estimate_tokens(chunk_text),
                    "processing_timestamp": datetime.utcnow().isoformat()
                }
                
                embeddings.append({
                    "chunk_text": chunk_text,
                    "start_char": start,
                    "end_char": end,
                    "embedding": embedding_vector,
                    "metadata": embedding_metadata
                })
            
            return json.dumps({
                "success": True,
                "page_id": page_id,
                "chunks_created": len(embeddings),
                "total_characters": len(page_text),
                "embeddings": [
                    {
                        "chunk_index": e["metadata"]["chunk_index"],
                        "start_char": e["start_char"],
                        "end_char": e["end_char"],
                        "token_count": e["metadata"]["token_count"]
                    }
                    for e in embeddings
                ]
            })
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "page_id": page_id
            })
    
    def _create_overlapping_chunks(self, 
                                  text: str, 
                                  chunk_size: int, 
                                  overlap_size: int) -> List[tuple]:
        """Create overlapping text chunks."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Extend to word boundary if not at end
            if end < len(text):
                # Find next space
                while end < len(text) and text[end] != ' ':
                    end += 1
            
            # Extract chunk
            chunk_text = text[start:end].strip()
            
            # Skip empty chunks
            if chunk_text:
                chunks.append((chunk_text, start, end))
            
            # Move start with overlap
            start = end - overlap_size
            
            # Ensure we make progress
            if start >= end:
                start = end
        
        return chunks
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Rough approximation: 1 token per 4 characters
        return max(1, len(text) // 4)
    
    def regenerate_embeddings(self,
                             db_url: str,
                             book_key: str,
                             version: Optional[str] = None) -> str:
        """
        Regenerate embeddings for an entire book.
        
        Args:
            db_url: Database connection URL
            book_key: Book identifier
            version: Optional version filter
            
        Returns:
            JSON string with regeneration results
        """
        try:
            engine = create_engine(db_url)
            
            # Query for pages
            query = text("""
                SELECT id, page_number, page_text, language_code, version
                FROM book_ingestions
                WHERE book_key = :book_key
                AND (:version IS NULL OR version = :version)
                ORDER BY page_number
            """)
            
            with engine.connect() as conn:
                pages = conn.execute(query, {
                    "book_key": book_key,
                    "version": version
                }).fetchall()
                
                logger.info(f"Regenerating embeddings for {len(pages)} pages")
                
                results = []
                for page in pages:
                    # Delete existing embeddings
                    delete_query = text("""
                        DELETE FROM object_embeddings 
                        WHERE source_id = :page_id
                    """)
                    conn.execute(delete_query, {"page_id": page.id})
                    
                    # Generate new embeddings
                    result = self._run(
                        page_id=str(page.id),
                        page_text=page.page_text,
                        metadata={
                            "book_key": book_key,
                            "page_number": page.page_number,
                            "language_code": page.language_code,
                            "version": page.version
                        }
                    )
                    
                    results.append(json.loads(result))
                
                # Commit changes
                conn.commit()
            
            successful = sum(1 for r in results if r.get("success"))
            
            return json.dumps({
                "success": True,
                "book_key": book_key,
                "pages_processed": len(pages),
                "successful": successful,
                "failed": len(pages) - successful,
                "results": results
            })
            
        except Exception as e:
            logger.error(f"Error regenerating embeddings: {str(e)}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "book_key": book_key
            })