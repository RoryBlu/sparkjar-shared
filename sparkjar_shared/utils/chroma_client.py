"""
ChromaDB client utilities for connecting to remote ChromaDB server.
Uses authentication and maintains consistency with the memory system.
"""
import chromadb
from chromadb.config import Settings
from config import CHROMA_URL, CHROMA_SERVER_AUTHN_CREDENTIALS, CHROMA_SERVER_AUTHN_PROVIDER
import logging
import httpx

logger = logging.getLogger(__name__)

def get_chroma_client():
    """
    Get authenticated ChromaDB HTTP client.
    Handles Railway's IPv6 internal networking.
    
    Returns:
        chromadb.HttpClient: Authenticated client instance
    """
    try:
        import socket
        from urllib.parse import urlparse
        
        # Parse the URL
        parsed = urlparse(CHROMA_URL)
        
        # Extract components
        ssl = parsed.scheme == 'https'
        host = parsed.hostname or parsed.netloc.split(':')[0]
        
        # Handle port - check for explicit port in URL first
        if ':' in CHROMA_URL and CHROMA_URL.rstrip('/').split(':')[-1].isdigit():
            # Extract port from the end of URL
            port = int(CHROMA_URL.rstrip('/').split(':')[-1])
        elif parsed.port:
            port = parsed.port
        else:
            # Default ports - ChromaDB typically uses 8000
            port = 443 if ssl else 8000
        
        # For Railway, check if PORT env var is set
        import os
        railway_port = os.environ.get('CHROMA_PORT')
        if railway_port and railway_port.isdigit():
            port = int(railway_port)
            logger.info(f"Using CHROMA_PORT from environment: {port}")
        
        # For Railway internal domains, ensure we use the hostname without scheme
        if '.railway.internal' in CHROMA_URL:
            # Extract just the hostname for Railway internal
            if CHROMA_URL.startswith('http://'):
                host = CHROMA_URL[7:].split(':')[0]
            elif CHROMA_URL.startswith('https://'):
                host = CHROMA_URL[8:].split(':')[0]
            else:
                host = CHROMA_URL.split(':')[0]
            
            ssl = False  # Railway internal is always HTTP
            logger.info(f"Using Railway internal connection: host={host}, port={port}")
        
        # Log connection attempt
        logger.info(f"Attempting ChromaDB connection to {host}:{port} (ssl={ssl})")
        
        # Try to resolve the hostname to check IPv6
        resolved_ipv6 = False
        try:
            addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, _, _, _, sockaddr in addr_info:
                if family == socket.AF_INET6:
                    logger.info(f"Resolved to IPv6 address: {sockaddr[0]}")
                    resolved_ipv6 = True
                    # For direct IPv6 addresses, we might need square brackets
                    if ':' in sockaddr[0] and not host.startswith('['):
                        logger.info(f"IPv6 detected, using direct connection to [{sockaddr[0]}]")
                elif family == socket.AF_INET:
                    logger.info(f"Resolved to IPv4 address: {sockaddr[0]}")
        except Exception as e:
            logger.warning(f"Could not resolve {host}: {e}")
        
        # Create client with proper authentication
        # Use headers for authentication instead of settings
        auth_headers = {}
        if CHROMA_SERVER_AUTHN_CREDENTIALS:
            auth_headers["Authorization"] = f"Bearer {CHROMA_SERVER_AUTHN_CREDENTIALS}"
        
        # Try with explicit timeout and settings
        from chromadb.config import Settings
        client_settings = Settings(
            anonymized_telemetry=False,
            chroma_server_host=host,
            chroma_server_http_port=port,
            chroma_server_ssl_enabled=ssl,
            chroma_client_auth_provider=None,  # Don't use the provider that causes errors
            chroma_client_auth_credentials=None
        )
        
        client = chromadb.HttpClient(
            host=host,
            port=port,
            ssl=ssl,
            headers=auth_headers if auth_headers else None,
            settings=client_settings
        )
        
        logger.info(f"ChromaDB client created for {host}:{port}")
        return client
        
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        logger.error(f"CHROMA_URL: {CHROMA_URL}")
        raise

def test_chroma_connection():
    """
    Test ChromaDB connection and list collections.
    
    Returns:
        dict: Status and collections info
    """
    try:
        # First, let's test if we can reach the server with httpx
        logger.info(f"Testing direct httpx connection to {CHROMA_URL}")
        try:
            # Test with httpx directly to see if it's a ChromaDB client issue
            test_url = f"{CHROMA_URL}/api/v1/heartbeat"
            headers = {}
            if CHROMA_SERVER_AUTHN_CREDENTIALS:
                headers["Authorization"] = f"Bearer {CHROMA_SERVER_AUTHN_CREDENTIALS}"
            
            with httpx.Client(timeout=10.0) as http_client:
                response = http_client.get(test_url, headers=headers)
                logger.info(f"Direct httpx test response: {response.status_code}")
        except Exception as e:
            logger.error(f"Direct httpx connection failed: {e}")
        
        # Apply monkey patch to fix _type field issue
        # This happens when ChromaDB server returns configs without _type
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
        
        # Now try the ChromaDB client
        client = get_chroma_client()
        collections = client.list_collections()
        
        # Handle different ChromaDB API responses
        collection_names = []
        try:
            # Try to access collections - handle both old and new API formats
            if hasattr(collections, '__iter__'):
                for col in collections:
                    # Try different ways to get the name
                    if hasattr(col, 'name'):
                        collection_names.append(col.name)
                    elif isinstance(col, dict) and 'name' in col:
                        collection_names.append(col['name'])
                    elif hasattr(col, 'get') and col.get('name'):
                        collection_names.append(col.get('name'))
            else:
                # If collections is not iterable, log the type for debugging
                logger.warning(f"Unexpected collections type: {type(collections)}")
        except Exception as e:
            logger.warning(f"Error processing collections: {e}")
            # Continue without collection names
            # Note: MCP validation errors can occur if ChromaDB has corrupted collections
            # These show as "Invalid parameter name" errors but are actually Zod validation issues
        
        return {
            "status": "success",
            "collections": collection_names,
            "chroma_url": CHROMA_URL,
            "total_collections": len(collection_names)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "chroma_url": CHROMA_URL
        }
