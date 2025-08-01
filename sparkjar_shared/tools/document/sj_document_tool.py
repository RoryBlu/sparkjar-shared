"""
SparkJar Document Tool for CrewAI.

Provides comprehensive access to the SparkJar Document Service for document
conversion, organization, and management.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import httpx
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

class DocumentConfig(BaseModel):
    """Configuration for Document Service access."""
    base_url: str = Field(
        default="http://sparkjar-document-mcp.railway.internal", 
        description="Document service internal URL (IPv6)"
    )
    timeout: int = Field(default=60, description="Request timeout in seconds (longer for conversions)")
    use_ipv6: bool = Field(default=True, description="Use IPv6 for internal communication")

class SJDocumentTool(BaseTool):
    """
    SparkJar Document Tool for comprehensive document management.
    
    Supports:
    - Document conversion (multiple formats)
    - Batch document processing
    - Template management
    - Folder organization
    - Document search and retrieval
    - Folder hierarchy management
    """
    
    name: str = "sj_document"
    description: str = """Access SparkJar Document Service for document conversion and management.
    
    Available operations:
    - convert_document: Convert and save a document to various formats
    - batch_convert: Convert multiple documents at once
    - list_templates: Get available document templates
    - get_template: Retrieve a specific template
    - create_folder: Create a new folder
    - list_folders: List all folders
    - list_documents: List documents in a folder
    - search_documents: Search across all documents
    - organize_documents: Move and organize documents
    - get_folder_structure: Get complete folder hierarchy
    - check_health: Check service health status
    """
    
    config: DocumentConfig = Field(default_factory=DocumentConfig)
    
    def __init__(self, config: Optional[DocumentConfig] = None):
        """Initialize with optional configuration."""
        super().__init__()
        if config:
            self.config = config
        self._client = None
    
    @property
    def client(self) -> httpx.Client:
        """Lazy initialization of HTTP client with IPv6 support."""
        if self._client is None:
            # Configure for IPv6 if needed
            transport = None
            if self.config.use_ipv6:
                # Force IPv6 resolution
                transport = httpx.HTTPTransport(
                    retries=3,
                    http2=True,
                )
            
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                transport=transport,
                headers={
                    "User-Agent": "SparkJar-CrewAI-DocumentTool/1.0",
                    "Accept": "application/json",
                }
            )
        return self._client
    
    def _run(self, 
             operation: str,
             **kwargs) -> Dict[str, Any]:
        """
        Execute document operations.
        
        Args:
            operation: The operation to perform
            **kwargs: Operation-specific parameters
            
        Returns:
            Dict containing operation results
        """
        logger.info(f"[SJDocument] Executing operation: {operation} with params: {kwargs}")
        
        try:
            # Map operations to methods
            operations = {
                "convert_document": self._convert_document,
                "batch_convert": self._batch_convert,
                "list_templates": self._list_templates,
                "get_template": self._get_template,
                "create_folder": self._create_folder,
                "list_folders": self._list_folders,
                "list_documents": self._list_documents,
                "search_documents": self._search_documents,
                "organize_documents": self._organize_documents,
                "get_folder_structure": self._get_folder_structure,
                "check_health": self._check_health,
            }
            
            if operation not in operations:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}. Available: {list(operations.keys())}"
                }
            
            return operations[operation](**kwargs)
            
        except Exception as e:
            logger.error(f"[SJDocument] Error in operation {operation}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "operation": operation
            }
    
    def _convert_document(self,
                         source_path: str,
                         output_format: str,
                         template_name: Optional[str] = None,
                         save_to_folder: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None,
                         **kwargs) -> Dict[str, Any]:
        """Convert and save a document."""
        try:
            payload = {
                "source_path": source_path,
                "output_format": output_format,
                "metadata": metadata or {}
            }
            
            if template_name:
                payload["template_name"] = template_name
            if save_to_folder:
                payload["save_to_folder"] = save_to_folder
            
            response = self.client.post("/convert", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "document_id": data.get("document_id"),
                "output_path": data.get("output_path"),
                "format": output_format,
                "message": f"Document converted to {output_format}"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error converting document: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _batch_convert(self,
                      documents: List[Dict[str, Any]],
                      output_format: str,
                      template_name: Optional[str] = None,
                      **kwargs) -> Dict[str, Any]:
        """Batch convert multiple documents."""
        try:
            payload = {
                "documents": documents,
                "output_format": output_format
            }
            
            if template_name:
                payload["template_name"] = template_name
            
            response = self.client.post("/batch-convert", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "converted_count": data.get("converted_count", len(documents)),
                "results": data.get("results", []),
                "failed_count": data.get("failed_count", 0),
                "message": f"Batch conversion completed for {len(documents)} documents"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error in batch conversion: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _list_templates(self, **kwargs) -> Dict[str, Any]:
        """List available document templates."""
        try:
            response = self.client.get("/templates")
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "templates": data.get("templates", []),
                "count": len(data.get("templates", [])),
                "message": "Templates retrieved successfully"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error listing templates: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _get_template(self,
                     template_name: str,
                     **kwargs) -> Dict[str, Any]:
        """Get a specific template."""
        try:
            response = self.client.get(f"/template/{template_name}")
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "template": data,
                "template_name": template_name,
                "message": f"Template '{template_name}' retrieved"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error getting template: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _create_folder(self,
                      folder_name: str,
                      parent_folder: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      **kwargs) -> Dict[str, Any]:
        """Create a new folder."""
        try:
            payload = {
                "folder_name": folder_name,
                "metadata": metadata or {}
            }
            
            if parent_folder:
                payload["parent_folder"] = parent_folder
            
            response = self.client.post("/folders/create", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "folder_id": data.get("folder_id"),
                "folder_path": data.get("folder_path"),
                "message": f"Folder '{folder_name}' created successfully"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error creating folder: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _list_folders(self,
                     parent_folder: Optional[str] = None,
                     **kwargs) -> Dict[str, Any]:
        """List all folders."""
        try:
            params = {}
            if parent_folder:
                params["parent_folder"] = parent_folder
            
            response = self.client.get("/folders/list", params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "folders": data.get("folders", []),
                "count": len(data.get("folders", [])),
                "message": "Folders retrieved successfully"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error listing folders: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _list_documents(self,
                       folder_path: Optional[str] = None,
                       document_type: Optional[str] = None,
                       limit: int = 50,
                       **kwargs) -> Dict[str, Any]:
        """List documents in a folder."""
        try:
            params = {"limit": limit}
            if folder_path:
                params["folder_path"] = folder_path
            if document_type:
                params["document_type"] = document_type
            
            response = self.client.get("/documents/list", params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "documents": data.get("documents", []),
                "count": len(data.get("documents", [])),
                "folder": folder_path or "root",
                "message": "Documents retrieved successfully"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error listing documents: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _search_documents(self,
                         query: str,
                         document_type: Optional[str] = None,
                         folder_path: Optional[str] = None,
                         limit: int = 20,
                         **kwargs) -> Dict[str, Any]:
        """Search across documents."""
        try:
            params = {
                "query": query,
                "limit": limit
            }
            if document_type:
                params["document_type"] = document_type
            if folder_path:
                params["folder_path"] = folder_path
            
            response = self.client.get("/documents/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "results": data.get("results", []),
                "count": len(data.get("results", [])),
                "query": query,
                "message": f"Found {len(data.get('results', []))} documents"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error searching documents: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _organize_documents(self,
                           document_ids: List[str],
                           target_folder: str,
                           operation: str = "move",
                           **kwargs) -> Dict[str, Any]:
        """Move or copy documents to different folders."""
        try:
            payload = {
                "document_ids": document_ids,
                "target_folder": target_folder,
                "operation": operation  # "move" or "copy"
            }
            
            response = self.client.post("/documents/organize", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "processed_count": data.get("processed_count", len(document_ids)),
                "operation": operation,
                "target_folder": target_folder,
                "message": f"Successfully {operation}d {len(document_ids)} documents"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error organizing documents: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _get_folder_structure(self,
                             root_folder: Optional[str] = None,
                             max_depth: Optional[int] = None,
                             **kwargs) -> Dict[str, Any]:
        """Get complete folder hierarchy."""
        try:
            params = {}
            if root_folder:
                params["root_folder"] = root_folder
            if max_depth:
                params["max_depth"] = max_depth
            
            response = self.client.get("/folders/structure", params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "structure": data.get("structure", {}),
                "folder_count": data.get("folder_count", 0),
                "document_count": data.get("document_count", 0),
                "message": "Folder structure retrieved successfully"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error getting folder structure: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _check_health(self, **kwargs) -> Dict[str, Any]:
        """Check document service health."""
        try:
            response = self.client.get("/health")
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "status": data.get("status", "unknown"),
                "service": "sparkjar-document",
                "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
                "message": "Service is healthy"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error checking health: {str(e)}",
                "status": "unhealthy",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if self._client:
            self._client.close()

# Example usage patterns for agents:
"""
# Convert a document
result = sj_document_tool._run(
    operation="convert_document",
    source_path="/path/to/document.docx",
    output_format="pdf",
    template_name="professional",
    save_to_folder="/converted/pdfs"
)

# Batch convert multiple documents
result = sj_document_tool._run(
    operation="batch_convert",
    documents=[
        {"source_path": "/doc1.docx", "metadata": {"author": "John"}},
        {"source_path": "/doc2.docx", "metadata": {"author": "Jane"}}
    ],
    output_format="pdf"
)

# Search documents
result = sj_document_tool._run(
    operation="search_documents",
    query="quarterly report",
    document_type="pdf",
    limit=10
)

# Create folder structure
result = sj_document_tool._run(
    operation="create_folder",
    folder_name="2024-Q1-Reports",
    parent_folder="/reports",
    metadata={"year": 2024, "quarter": 1}
)

# Organize documents
result = sj_document_tool._run(
    operation="organize_documents",
    document_ids=["doc1-id", "doc2-id", "doc3-id"],
    target_folder="/archive/2024",
    operation="move"
)

# Get folder hierarchy
result = sj_document_tool._run(
    operation="get_folder_structure",
    root_folder="/reports",
    max_depth=3
)
"""