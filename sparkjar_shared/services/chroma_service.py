"""
Centralized ChromaDB service for SparkJAR Crew.

This service provides a unified interface for all ChromaDB operations,
including connection management, authentication, and error handling.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
import chromadb
from chromadb.config import Settings
from chromadb.api.models.Collection import Collection
import httpx
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ChromaService:
    """Centralized ChromaDB service client with authentication and error handling."""
    
    def __init__(self, 
                 chroma_url: str = None,
                 auth_credentials: str = None,
                 auth_provider: str = None):
        """
        Initialize ChromaDB service.
        
        Args:
            chroma_url: ChromaDB server URL (defaults to config)
            auth_credentials: Authentication credentials (defaults to config)
            auth_provider: Authentication provider (defaults to config)
        """
        # Import here to avoid circular imports
        from shared.config.shared_settings import (
            CHROMA_URL, 
            CHROMA_SERVER_AUTHN_CREDENTIALS,
            CHROMA_SERVER_AUTHN_PROVIDER
        )
        
        self.chroma_url = chroma_url or CHROMA_URL
        self.auth_credentials = auth_credentials or CHROMA_SERVER_AUTHN_CREDENTIALS
        self.auth_provider = auth_provider or CHROMA_SERVER_AUTHN_PROVIDER
        
        self._client = None
        self._connection_tested = False
        
        # Apply ChromaDB patches on initialization
        self._apply_chromadb_patches()
    
    def _apply_chromadb_patches(self):
        """Apply necessary patches for ChromaDB compatibility."""
        try:
            from chromadb.api.configuration import ConfigurationInternal
            
            # Only patch if not already patched
            if not hasattr(ConfigurationInternal, '_from_json_patched'):
                original_from_json = ConfigurationInternal.from_json.__func__
                
                @classmethod
                def patched_from_json(cls, json_map):
                    """Handle missing _type field in configuration"""
                    if isinstance(json_map, dict) and "_type" not in json_map:
                        # Add _type based on class name if missing
                        json_map = json_map.copy()
                        json_map["_type"] = cls.__name__
                    return original_from_json(cls, json_map)
                
                # Apply patch and mark as patched
                ConfigurationInternal.from_json = patched_from_json
                ConfigurationInternal._from_json_patched = True
                logger.info("Applied ChromaDB _type field patch")
        except Exception as e:
            logger.warning(f"Could not apply ChromaDB patches: {e}")
    
    def _parse_connection_details(self) -> tuple[str, int, bool]:
        """
        Parse ChromaDB URL to extract connection details.
        
        Returns:
            tuple: (host, port, ssl_enabled)
        """
        parsed = urlparse(self.chroma_url)
        
        # Extract components
        ssl = parsed.scheme == 'https'
        host = parsed.hostname or parsed.netloc.split(':')[0]
        
        # Handle port - check for explicit port in URL first
        if ':' in self.chroma_url and self.chroma_url.rstrip('/').split(':')[-1].isdigit():
            # Extract port from the end of URL
            port = int(self.chroma_url.rstrip('/').split(':')[-1])
        elif parsed.port:
            port = parsed.port
        else:
            # Default ports - ChromaDB typically uses 8000
            port = 443 if ssl else 8000
        
        # For Railway internal domains, adjust settings
        if '.railway.internal' in self.chroma_url:
            # Extract just the hostname for Railway internal
            if self.chroma_url.startswith('http://'):
                host = self.chroma_url[7:].split(':')[0]
            elif self.chroma_url.startswith('https://'):
                host = self.chroma_url[8:].split(':')[0]
            else:
                host = self.chroma_url.split(':')[0]
            
            ssl = False  # Railway internal is always HTTP
            logger.info(f"Using Railway internal connection: host={host}, port={port}")
        
        return host, port, ssl
    
    def _create_client(self) -> chromadb.HttpClient:
        """
        Create and configure ChromaDB HTTP client.
        
        Returns:
            chromadb.HttpClient: Configured client instance
        """
        host, port, ssl = self._parse_connection_details()
        
        logger.info(f"Creating ChromaDB client for {host}:{port} (ssl={ssl})")
        
        # Check IPv6 resolution
        try:
            addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, _, _, _, sockaddr in addr_info:
                if family == socket.AF_INET6:
                    logger.info(f"Resolved to IPv6 address: {sockaddr[0]}")
                elif family == socket.AF_INET:
                    logger.info(f"Resolved to IPv4 address: {sockaddr[0]}")
        except Exception as e:
            logger.warning(f"Could not resolve {host}: {e}")
        
        # Create authentication headers
        auth_headers = {}
        if self.auth_credentials:
            auth_headers["Authorization"] = f"Bearer {self.auth_credentials}"
        
        # Create client settings
        client_settings = Settings(
            anonymized_telemetry=False,
            chroma_server_host=host,
            chroma_server_http_port=port,
            chroma_server_ssl_enabled=ssl,
            chroma_client_auth_provider=None,  # Don't use provider that causes errors
            chroma_client_auth_credentials=None
        )
        
        # Create HTTP client
        client = chromadb.HttpClient(
            host=host,
            port=port,
            ssl=ssl,
            headers=auth_headers if auth_headers else None,
            settings=client_settings
        )
        
        logger.info(f"ChromaDB client created successfully")
        return client
    
    @property
    def client(self) -> chromadb.HttpClient:
        """Get or create ChromaDB client instance."""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    async def health_check(self) -> bool:
        """
        Check ChromaDB service health.
        
        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            # Test direct HTTP connection first
            await self._test_http_connection()
            
            # Test ChromaDB client
            collections = self.client.list_collections()
            logger.info(f"ChromaDB health check passed - {len(collections)} collections found")
            self._connection_tested = True
            return True
            
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False
    
    async def _test_http_connection(self):
        """Test direct HTTP connection to ChromaDB server."""
        test_url = f"{self.chroma_url}/api/v1/heartbeat"
        headers = {}
        if self.auth_credentials:
            headers["Authorization"] = f"Bearer {self.auth_credentials}"
        
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get(test_url, headers=headers)
            response.raise_for_status()
            logger.info(f"Direct HTTP connection test passed: {response.status_code}")
    
    def list_collections(self) -> List[str]:
        """
        List all collection names.
        
        Returns:
            List[str]: Collection names
        """
        try:
            collections = self.client.list_collections()
            collection_names = []
            
            # Handle different ChromaDB API response formats
            if hasattr(collections, '__iter__'):
                for col in collections:
                    if hasattr(col, 'name'):
                        collection_names.append(col.name)
                    elif isinstance(col, dict) and 'name' in col:
                        collection_names.append(col['name'])
                    elif hasattr(col, 'get') and col.get('name'):
                        collection_names.append(col.get('name'))
            
            logger.info(f"Found {len(collection_names)} collections")
            return collection_names
            
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
    
    def get_or_create_collection(self, 
                                name: str, 
                                metadata: Optional[Dict[str, Any]] = None,
                                embedding_function = None) -> Collection:
        """
        Get existing collection or create new one.
        
        Args:
            name: Collection name
            metadata: Optional collection metadata
            embedding_function: Optional embedding function
            
        Returns:
            Collection: ChromaDB collection instance
        """
        try:
            # Try to get existing collection first
            collection = self.client.get_collection(
                name=name,
                embedding_function=embedding_function
            )
            logger.info(f"Retrieved existing collection: {name}")
            return collection
            
        except Exception:
            # Collection doesn't exist, create it
            logger.info(f"Creating new collection: {name}")
            collection = self.client.create_collection(
                name=name,
                metadata=metadata or {},
                embedding_function=embedding_function
            )
            logger.info(f"Created collection: {name}")
            return collection
    
    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.
        
        Args:
            name: Collection name to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            self.client.delete_collection(name=name)
            logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False
    
    def add_documents(self,
                     collection_name: str,
                     documents: List[str],
                     metadatas: Optional[List[Dict[str, Any]]] = None,
                     ids: Optional[List[str]] = None,
                     embeddings: Optional[List[List[float]]] = None) -> bool:
        """
        Add documents to a collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: Optional list of metadata dicts
            ids: Optional list of document IDs
            embeddings: Optional pre-computed embeddings
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            
            # Generate IDs if not provided
            if ids is None:
                ids = [f"doc_{i}" for i in range(len(documents))]
            
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings
            )
            
            logger.info(f"Added {len(documents)} documents to collection {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add documents to {collection_name}: {e}")
            return False
    
    def query_collection(self,
                        collection_name: str,
                        query_texts: Optional[List[str]] = None,
                        query_embeddings: Optional[List[List[float]]] = None,
                        n_results: int = 10,
                        where: Optional[Dict[str, Any]] = None,
                        where_document: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query a collection for similar documents.
        
        Args:
            collection_name: Name of the collection to query
            query_texts: List of query texts
            query_embeddings: List of query embeddings
            n_results: Number of results to return
            where: Metadata filter conditions
            where_document: Document content filter conditions
            
        Returns:
            Dict[str, Any]: Query results
        """
        try:
            collection = self.client.get_collection(collection_name)
            
            results = collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            logger.info(f"Queried collection {collection_name}, found {len(results.get('ids', [[]]))} result sets")
            return results
            
        except Exception as e:
            logger.error(f"Failed to query collection {collection_name}: {e}")
            return {}
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dict[str, Any]: Collection information
        """
        try:
            collection = self.client.get_collection(collection_name)
            count = collection.count()
            
            return {
                "name": collection_name,
                "count": count,
                "metadata": getattr(collection, 'metadata', {}),
                "status": "healthy"
            }
            
        except Exception as e:
            logger.error(f"Failed to get info for collection {collection_name}: {e}")
            return {
                "name": collection_name,
                "status": "error",
                "error": str(e)
            }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test ChromaDB connection and return detailed status.
        
        Returns:
            Dict[str, Any]: Connection test results
        """
        try:
            # Test HTTP connection
            await self._test_http_connection()
            
            # Test ChromaDB operations
            collections = self.list_collections()
            
            return {
                "status": "success",
                "chroma_url": self.chroma_url,
                "collections": collections,
                "total_collections": len(collections),
                "authenticated": bool(self.auth_credentials)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "chroma_url": self.chroma_url,
                "error": str(e),
                "authenticated": bool(self.auth_credentials)
            }


# Global service instance
_chroma_service = None


def get_chroma_service() -> ChromaService:
    """
    Get global ChromaService instance.
    
    Returns:
        ChromaService: Global service instance
    """
    global _chroma_service
    if _chroma_service is None:
        _chroma_service = ChromaService()
    return _chroma_service


# Backward compatibility functions
def get_chroma_client():
    """Backward compatibility function - returns the client from ChromaService."""
    return get_chroma_service().client


def test_chroma_connection():
    """Backward compatibility function - returns sync connection test."""
    service = get_chroma_service()
    
    # Run async test in sync context
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, service.test_connection())
                return future.result()
        else:
            return asyncio.run(service.test_connection())
    except Exception as e:
        return {
            "status": "error",
            "chroma_url": service.chroma_url,
            "error": str(e)
        }