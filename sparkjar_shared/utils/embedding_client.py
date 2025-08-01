"""
Embedding client utilities for consistent embedding across the system.
Supports both custom embeddings service and OpenAI embeddings.
"""
import asyncio
import logging
import os
from typing import List, Union, Optional
from enum import Enum

from config import EMBEDDING_MODEL, EMBEDDINGS_API_URL, OPENAI_API_KEY
from shared.utils.retry_utils import retry_async, RetryConfig, CircuitBreaker

logger = logging.getLogger(__name__)

class EmbeddingProvider(Enum):
    """Enum for embedding providers"""
    CUSTOM = "custom"
    OPENAI = "openai"

class EmbeddingClient:
    """
    Client for generating embeddings using custom service or OpenAI.
    Automatically switches based on EMBEDDING_PROVIDER environment variable.
    """
    
    def __init__(self, provider: Optional[str] = None):
        # Determine provider from environment or parameter
        self.provider = EmbeddingProvider(provider or os.getenv("EMBEDDING_PROVIDER", "custom"))
        
        if self.provider == EmbeddingProvider.OPENAI:
            self.model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            self.dimension = int(os.getenv("OPENAI_EMBEDDING_DIMENSION", "1536"))
            self.api_key = OPENAI_API_KEY
            self.api_url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/embeddings")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        else:
            # Custom provider (default)
            self.model_name = EMBEDDING_MODEL
            self.dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))
            self.embeddings_api_url = EMBEDDINGS_API_URL
            if not self.embeddings_api_url:
                raise ValueError("EMBEDDINGS_API_URL is required for custom embeddings service")
        
        # Initialize circuit breaker for API protection
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            half_open_attempts=1
        )
        
    async def get_embeddings(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Get embeddings for text(s) using configured provider.
        
        Args:
            texts: Single text string or list of texts
            
        Returns:
            List of embedding vectors (dimension depends on provider)
        """
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            if self.provider == EmbeddingProvider.OPENAI:
                return await self._get_openai_embeddings(texts)
            else:
                return await self._get_custom_embeddings(texts)
                
        except Exception as e:
            logger.error(f"Failed to get embeddings using {self.provider.value} provider: {str(e)}")
            raise
    
    @retry_async(max_retries=3, initial_delay=1.0, exponential_base=2.0, max_delay=10.0)
    async def _get_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API with retry logic."""
        import httpx
        
        embeddings = []
        async with httpx.AsyncClient() as client:
            # Process texts individually to handle OpenAI rate limits
            for text in texts:
                # Use circuit breaker to prevent excessive calls when service is down
                response = await self.circuit_breaker.call(
                    self._make_openai_request,
                    client,
                    text
                )
                
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    embeddings.append(data["data"][0]["embedding"])
                else:
                    raise ValueError(f"Unexpected OpenAI response format: {data}")
            
            logger.info(f"Generated {len(embeddings)} embeddings using OpenAI {self.model_name}")
            return embeddings
    
    async def _make_openai_request(self, client: 'httpx.AsyncClient', text: str) -> 'httpx.Response':
        """Make the actual OpenAI API request."""
        response = await client.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model_name,
                "input": text,
                "encoding_format": "float"
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response
    
    @retry_async(max_retries=3, initial_delay=1.0, exponential_base=2.0, max_delay=10.0)
    async def _get_custom_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from custom embeddings service with retry logic."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await self.circuit_breaker.call(
                self._make_custom_request,
                client,
                texts
            )
            
            data = response.json()
            embeddings = data["embeddings"]
            
            logger.info(f"Generated {len(embeddings)} embeddings using custom {self.model_name} service")
            return embeddings
    
    async def _make_custom_request(self, client: 'httpx.AsyncClient', texts: List[str]) -> 'httpx.Response':
        """Make the actual custom embeddings API request."""
        response = await client.post(
            f"{self.embeddings_api_url}/embeddings",
            json={
                "texts": texts,
                "model": self.model_name
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response
    
    def get_embeddings_sync(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """Synchronous wrapper for get_embeddings."""
        return asyncio.run(self.get_embeddings(texts))

# Global client instance
_embedding_client = None

def get_embedding_client() -> EmbeddingClient:
    """Get the global embedding client instance."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
