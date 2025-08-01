"""
SparkJar Document Tool for CrewAI - Registry Version with MCP Discovery.

This version uses the MCP Registry to discover and connect to the document service.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Union, Type
from pathlib import Path
import httpx
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
from datetime import datetime, timedelta
import jwt
import os

logger = logging.getLogger(__name__)

class DocumentConfig(BaseModel):
    """Configuration for Document Service access via MCP Registry."""
    mcp_registry_url: str = Field(
        default="https://mcp-registry-development.up.railway.app",
        description="MCP Registry URL for service discovery"
    )
    api_secret_key: str = Field(
        default=os.getenv("API_SECRET_KEY", ""),
        description="Secret key for JWT generation"
    )
    timeout: int = Field(default=30, description="Request timeout for document operations")
    cache_ttl: int = Field(default=300, description="Service discovery cache TTL in seconds")

class SJDocumentToolInput(BaseModel):
    """Input schema for SJDocumentTool."""
    action: str = Field(
        description="The action to perform: save_markdown_as_word"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the action"
    )

class SJDocumentTool(BaseTool):
    """
    SparkJar Document Tool with MCP Registry discovery.
    
    This tool discovers the document service through the MCP Registry
    and properly authenticates all requests.
    
    Actions:
    - save_markdown_as_word: Convert markdown to WORD doc (params: content, filename, folder)
    - create_folder: Create folder (params: folder_name, parent_folder)
    - search_documents: Search documents (params: query, limit)
    - get_document_link: Get shareable link for document (params: document_id)
    """
    
    name: str = "sj_document"
    description: str = """Document management via MCP Registry. Pass JSON with 'action' and 'params'.
    
    Actions:
    - save_markdown_as_word: Save markdown as Word doc {"action": "save_markdown_as_word", "params": {"content": "# Title\\nContent", "filename": "doc.docx"}}
    - create_folder: Create folder {"action": "create_folder", "params": {"folder_name": "Reports"}}
    - search_documents: Search docs {"action": "search_documents", "params": {"query": "quarterly report"}}
    - get_document_link: Get share link {"action": "get_document_link", "params": {"document_id": "uuid"}}
    """
    args_schema: Type[BaseModel] = SJDocumentToolInput
    
    config: DocumentConfig = Field(default_factory=DocumentConfig)
    
    def __init__(self, config: Optional[DocumentConfig] = None):
        """Initialize with optional configuration."""
        super().__init__()
        if config:
            self.config = config
        self._service_url = None
        self._service_discovered_at = None
        self._client = None
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for authentication."""
        payload = {
            "sub": "sparkjar-crew-tool",
            "scopes": ["sparkjar_internal"],
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "iss": "sparkjar-crew"
        }
        return jwt.encode(payload, self.config.api_secret_key, algorithm="HS256")
    
    async def _discover_document_service(self) -> Optional[str]:
        """Discover document service URL from MCP Registry."""
        # Check cache first
        if (self._service_url and 
            self._service_discovered_at and 
            (datetime.utcnow() - self._service_discovered_at).seconds < self.config.cache_ttl):
            return self._service_url
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {self._generate_jwt_token()}"}
                
                # Query registry for document services
                response = await client.get(
                    f"{self.config.mcp_registry_url}/registry/services",
                    headers=headers,
                    params={"service_type": "document"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    services = data.get("services", [])
                    
                    # Find the document MCP service
                    for service in services:
                        if (service.get("service_name") == "sparkjar-document-mcp" and
                            service.get("status") == "active"):
                            # Prefer public URL over internal
                            self._service_url = service.get("base_url") or service.get("internal_url")
                            self._service_discovered_at = datetime.utcnow()
                            logger.info(f"Discovered document service at: {self._service_url}")
                            return self._service_url
                
                logger.warning("No active document service found in registry")
                
        except Exception as e:
            logger.error(f"Failed to discover document service: {e}")
        
        # Fallback to known URL if discovery fails
        self._service_url = "https://sparkjar-document-mcp-development.up.railway.app"
        self._service_discovered_at = datetime.utcnow()
        logger.warning(f"Using fallback document service URL: {self._service_url}")
        return self._service_url
    
    @property
    async def client(self) -> httpx.AsyncClient:
        """Get HTTP client with discovered service URL."""
        if self._client is None:
            service_url = await self._discover_document_service()
            if not service_url:
                raise RuntimeError("Failed to discover document service")
            
            self._client = httpx.AsyncClient(
                base_url=service_url,
                timeout=httpx.Timeout(self.config.timeout),
                headers={
                    "Authorization": f"Bearer {self._generate_jwt_token()}",
                    "User-Agent": "SparkJar-CrewAI-DocumentTool/Registry",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    def _run(self, action: str, params: Dict[str, Any]) -> str:
        """
        Execute document operations based on structured input.
        Runs async operations in sync context for CrewAI compatibility.
        """
        import asyncio
        
        try:
            # Direct access to structured input (no JSON parsing needed)
            
            if not action:
                return f"Error: Missing 'action' field. Available: save_markdown_as_word, create_folder, search_documents, get_document_link"
            
            # Map actions to methods
            actions = {
                "save_markdown_as_word": self._save_markdown_as_word,
                "create_folder": self._create_folder,
                "search_documents": self._search_documents,
                "get_document_link": self._get_document_link,
            }
            
            if action not in actions:
                return f"Error: Unknown action '{action}'. Available: {list(actions.keys())}"
            
            # Run async operation in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(actions[action](**params))
                if result.get("success"):
                    return json.dumps(result, indent=2)
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Unexpected error in document tool: {e}")
            return f"Error: {str(e)}"
    
    async def _save_markdown_as_word(self,
                                    content: str,
                                    filename: str,
                                    folder: Optional[str] = None,
                                    metadata: Optional[Dict[str, Any]] = None,
                                    **kwargs) -> Dict[str, Any]:
        """Save markdown content as a Word document."""
        try:
            client = await self.client
            
            # Send markdown content directly, not a file path
            payload = {
                "content": content,  # The actual markdown content
                "output_format": "docx",  # Word format
                "filename": filename,
                "metadata": metadata or {}
            }
            
            if folder:
                payload["folder"] = folder
            
            response = await client.post("/mcp/tools/execute", json={
                "tool": "convert_markdown",
                "params": payload
            })
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "document_id": data.get("document_id"),
                    "document_url": data.get("document_url"),
                    "share_link": data.get("share_link"),
                    "filename": filename,
                    "message": f"Saved markdown as Word document: {filename}"
                }
            else:
                error_text = response.text
                logger.error(f"Document save failed: {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "error": f"Failed to save document: {error_text}"
                }
                
        except Exception as e:
            logger.error(f"Error saving document: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_folder(self,
                            folder_name: str,
                            parent_folder: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None,
                            **kwargs) -> Dict[str, Any]:
        """Create a new folder."""
        try:
            client = await self.client
            
            payload = {
                "folder_name": folder_name,
                "metadata": metadata or {}
            }
            
            if parent_folder:
                payload["parent_folder"] = parent_folder
            
            response = await client.post("/mcp/tools/execute", json={
                "tool": "create_folder",
                "params": payload
            })
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "folder_id": data.get("folder_id"),
                    "folder_path": data.get("folder_path"),
                    "message": f"Folder '{folder_name}' created successfully"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create folder: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _search_documents(self,
                               query: str,
                               document_type: Optional[str] = None,
                               folder_path: Optional[str] = None,
                               limit: int = 20,
                               **kwargs) -> Dict[str, Any]:
        """Search across documents."""
        try:
            client = await self.client
            
            params = {
                "query": query,
                "limit": limit
            }
            if document_type:
                params["document_type"] = document_type
            if folder_path:
                params["folder_path"] = folder_path
            
            response = await client.post("/mcp/tools/execute", json={
                "tool": "search_documents",
                "params": params
            })
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "results": data.get("results", []),
                    "count": len(data.get("results", [])),
                    "query": query
                }
            else:
                return {
                    "success": False,
                    "error": f"Search failed: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_document_link(self,
                                document_id: str,
                                **kwargs) -> Dict[str, Any]:
        """Get shareable link for a document."""
        try:
            client = await self.client
            
            response = await client.post("/mcp/tools/execute", json={
                "tool": "get_document_link",
                "params": {"document_id": document_id}
            })
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "share_link": data.get("share_link"),
                    "document_id": document_id,
                    "expires_at": data.get("expires_at")
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get document link: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error getting document link: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup."""
        if self._client:
            await self._client.aclose()
            self._client = None