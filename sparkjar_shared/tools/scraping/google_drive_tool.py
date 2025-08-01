"""Google Drive Tool for accessing and downloading files.

Simple, focused tool for retrieving images from Google Drive folders.
Uses client-specific service account credentials from database.
"""
import os
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import tempfile
import logging
from uuid import UUID
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Database imports for credential retrieval
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from database.models import ClientSecrets, ClientUsers

# Google Drive API imports
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    import io
except ImportError:
    raise ImportError(
        "Google API client not installed. Run: pip install google-api-python-client google-auth"
    )

logger = logging.getLogger(__name__)

class GoogleDriveToolInput(BaseModel):
    """Input schema for Google Drive operations."""
    folder_path: str = Field(
        ..., 
        description=(
            "Google Drive folder path, URL, or folder ID. Supports:\n"
            "- Folder paths: 'Sparkjar/vervelyn/castor gonzalez/book 1/'\n"
            "- Share URLs: 'https://drive.google.com/drive/folders/0AM0PEUhIEQFUUk9PVA'\n"
            "- Folder IDs: '0AM0PEUhIEQFUUk9PVA'\n"
            "- Mixed: '0AM0PEUhIEQFUUk9PVA/vervelyn/castor gonzalez/book 1/'"
        )
    )
    client_user_id: str = Field(
        ...,
        description="Client user ID for credential lookup"
    )
    file_types: List[str] = Field(
        default=["image/jpeg", "image/png", "image/jpg", "image/webp"],
        description="MIME types to filter (default: common image types)"
    )
    max_files: Optional[int] = Field(
        None,
        description="Maximum number of files to retrieve"
    )
    download: bool = Field(
        default=True,
        description="Whether to download files to temp directory"
    )
    
class GoogleDriveUploadInput(BaseModel):
    """Input schema for uploading files to Google Drive."""
    folder_path: str = Field(
        ...,
        description=(
            "Google Drive folder path, URL, or folder ID where file should be uploaded. Supports:\n"
            "- Folder paths: 'Sparkjar/vervelyn/castor gonzalez/book 1/'\n"
            "- Share URLs: 'https://drive.google.com/drive/folders/0AM0PEUhIEQFUUk9PVA'\n"
            "- Folder IDs: '0AM0PEUhIEQFUUk9PVA'\n"
            "- Mixed: '0AM0PEUhIEQFUUk9PVA/vervelyn/castor gonzalez/book 1/'"
        )
    )
    client_user_id: str = Field(
        ...,
        description="Client user ID for credential lookup"
    )
    file_path: str = Field(
        ...,
        description="Local file path to upload"
    )
    file_name: str = Field(
        ...,
        description="Name for the file in Google Drive"
    )
    mime_type: str = Field(
        default="text/plain",
        description="MIME type of the file"
    )

class GoogleDriveTool(BaseTool):
    """Tool for accessing files from Google Drive folders using client credentials."""
    
    name: str = "google_drive_tool"
    description: str = (
        "Access, download, and upload files from/to Google Drive folders. "
        "Uses client-specific credentials from database."
    )
    args_schema: type[BaseModel] = GoogleDriveToolInput
    
    def __init__(self):
        super().__init__()
        self._temp_dir = Path(tempfile.mkdtemp(prefix="drive_files_"))
        self._services = {}  # Cache services per client
    
    @property
    def temp_dir(self) -> Path:
        """Get the temporary directory for downloads."""
        return self._temp_dir
    
    def _get_client_credentials(self, client_user_id: str) -> Dict[str, Any]:
        """Retrieve Google service account credentials for the client."""
        logger.info(f"Getting credentials for client_user_id: {client_user_id} (type: {type(client_user_id)})")
        
        # Use sync database connection
        database_url = os.getenv('DATABASE_URL_DIRECT')
        if not database_url:
            raise ValueError("DATABASE_URL_DIRECT not configured")
        
        # Convert asyncpg URL to psycopg2 for sync
        sync_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        engine = create_engine(sync_url)
        Session = sessionmaker(bind=engine)
        
        try:
            with Session() as session:
                # First get client_id from client_user_id
                user_result = session.execute(
                    select(ClientUsers.clients_id).where(
                        ClientUsers.id == UUID(client_user_id)
                    )
                )
                client_id = user_result.scalar_one_or_none()
                
                if not client_id:
                    raise ValueError(f"No client found for user {client_user_id}")
                
                # Get Google credentials for this client
                creds_result = session.execute(
                    select(ClientSecrets).where(
                        ClientSecrets.client_id == client_id,
                        ClientSecrets.secret_key == "googleapis.service_account"
                    )
                )
                client_secret = creds_result.scalar_one_or_none()
                
                if not client_secret or not client_secret.secrets_metadata:
                    raise ValueError(f"No Google credentials found for client")
                
                # The secrets_metadata is already a dict/JSON from the database
                return client_secret.secrets_metadata
                
        finally:
            engine.dispose()
    
    def _get_service(self, client_user_id: str, readonly: bool = True):
        """Get or create Google Drive service for a client."""
        cache_key = f"{client_user_id}_{readonly}"
        
        if cache_key not in self._services:
            creds_data = self._get_client_credentials(client_user_id)
            
            # Create credentials from the service account JSON
            credentials = service_account.Credentials.from_service_account_info(
                creds_data,
                scopes=[
                    'https://www.googleapis.com/auth/drive.readonly' if readonly
                    else 'https://www.googleapis.com/auth/drive'
                ]
            )
            
            self._services[cache_key] = build('drive', 'v3', credentials=credentials)
        
        return self._services[cache_key]
    
    def _extract_folder_id_from_url(self, url: str) -> str:
        """Extract folder ID from Google Drive share URL."""
        import re
        
        # Pattern for share URLs like https://drive.google.com/drive/u/0/folders/FOLDER_ID
        patterns = [
            r'folders/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
            r'/d/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Could not extract folder ID from URL: {url}")
    
    def _find_folder_by_path(self, service, path: str) -> str:
        """Navigate folder path and return folder ID.
        
        Supports:
        - Direct folder IDs (e.g., '0AM0PEUhIEQFUUk9PVA')
        - Google Drive URLs (e.g., 'https://drive.google.com/drive/folders/...')
        - Path navigation (e.g., 'folder1/folder2/folder3')
        - Mixed approach (e.g., 'FOLDER_ID/subfolder1/subfolder2')
        """
        # Check if it's a URL
        if path.startswith('http'):
            folder_id = self._extract_folder_id_from_url(path)
            logger.info(f"Extracted folder ID from URL: {folder_id}")
            return folder_id
        
        # Check if it looks like a direct folder ID (alphanumeric with underscores/dashes)
        if '/' not in path and len(path) > 10 and all(c.isalnum() or c in '_-' for c in path):
            logger.info(f"Using direct folder ID: {path}")
            return path
        
        # Handle path navigation (original logic)
        parts = [p.strip() for p in path.split('/') if p.strip()]
        
        if not parts:
            return 'root'
        
        # Check if first part is a folder ID
        first_part = parts[0]
        if len(first_part) > 10 and all(c.isalnum() or c in '_-' for c in first_part):
            # Start from this folder ID
            current_folder_id = first_part
            parts = parts[1:]  # Remove the ID from parts to process
            logger.info(f"Starting from folder ID: {current_folder_id}")
        else:
            # Start from root
            current_folder_id = 'root'
        
        # Navigate remaining path parts
        for folder_name in parts:
            # Search for folder with this name in current folder
            query = (
                f"name = '{folder_name}' and "
                f"'{current_folder_id}' in parents and "
                f"mimeType = 'application/vnd.google-apps.folder' and "
                f"trashed = false"
            )
            
            results = service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=1,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            if not files:
                raise ValueError(f"Folder '{folder_name}' not found in path: {path}")
            
            current_folder_id = files[0]['id']
            logger.info(f"Found folder '{folder_name}' with ID: {current_folder_id}")
        
        return current_folder_id
    
    def _download_file(self, service, file_id: str, file_name: str) -> str:
        """Download a file from Drive to temp directory."""
        request = service.files().get_media(fileId=file_id)
        
        file_path = self.temp_dir / file_name
        fh = io.BytesIO()
        
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        
        while not done:
            status, done = downloader.next_chunk()
        
        # Write to file
        fh.seek(0)
        with open(file_path, 'wb') as f:
            f.write(fh.read())
        
        return str(file_path)
    
    def upload_file(self, folder_path: str, client_user_id: str, 
                    file_path: str, file_name: str, 
                    mime_type: str = "text/plain") -> str:
        """Upload a file to Google Drive folder.
        
        Args:
            folder_path: Drive folder path
            client_user_id: Client user ID for credentials
            file_path: Local file to upload
            file_name: Name for the file in Drive
            mime_type: MIME type of the file
            
        Returns:
            JSON string with upload result
        """
        try:
            # Get service with write permissions
            service = self._get_service(client_user_id, readonly=False)
            
            # Find folder ID from path
            folder_id = self._find_folder_by_path(service, folder_path)
            
            # Create file metadata
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            # Upload file
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size',
                supportsAllDrives=True
            ).execute()
            
            return json.dumps({
                "status": "success",
                "file_id": file.get('id'),
                "file_name": file.get('name'),
                "size": file.get('size'),
                "folder_path": folder_path
            })
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return json.dumps({
                "status": "error",
                "error": str(e),
                "file_path": file_path
            })
    
    def _run(self, folder_path: str, client_user_id: str, 
             file_types: List[str] = None, max_files: Optional[int] = None, 
             download: bool = True, **kwargs) -> str:
        """
        List and optionally download files from a Google Drive folder.
        
        Returns JSON string with file information.
        """
        if file_types is None:
            file_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
        
        try:
            # Get service for this client
            service = self._get_service(client_user_id, readonly=True)
            
            # Find folder ID from path
            folder_id = self._find_folder_by_path(service, folder_path)
            logger.info(f"Resolved folder path '{folder_path}' to ID: {folder_id}")
            
            # Build query for files in folder
            query_parts = [f"'{folder_id}' in parents", "trashed = false"]
            
            # Add MIME type filters
            if file_types:
                mime_queries = [f"mimeType = '{mt}'" for mt in file_types]
                query_parts.append(f"({' or '.join(mime_queries)})")
            
            query = " and ".join(query_parts)
            
            # List files (with shared drive support)
            results = service.files().list(
                q=query,
                fields="files(id, name, mimeType, size, createdTime, modifiedTime)",
                orderBy="name",  # Order by name for sequential processing
                pageSize=max_files if max_files else 1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                return json.dumps({
                    "status": "success",
                    "message": "No files found in folder",
                    "folder_path": folder_path,
                    "folder_id": folder_id,
                    "files": []
                })
            
            # Process files
            file_info = []
            for file in files[:max_files] if max_files else files:
                info = {
                    "file_id": file['id'],
                    "name": file['name'],
                    "mime_type": file.get('mimeType', ''),
                    "size": int(file.get('size', 0)),
                    "created": file.get('createdTime', ''),
                    "modified": file.get('modifiedTime', '')
                }
                
                # Download if requested
                if download:
                    try:
                        local_path = self._download_file(service, file['id'], file['name'])
                        info['local_path'] = local_path
                        info['download_status'] = 'success'
                    except Exception as e:
                        info['download_status'] = 'failed'
                        info['download_error'] = str(e)
                
                file_info.append(info)
            
            return json.dumps({
                "status": "success",
                "folder_path": folder_path,
                "folder_id": folder_id,
                "file_count": len(file_info),
                "temp_directory": str(self.temp_dir) if download else None,
                "files": file_info
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Google Drive error: {e}")
            return json.dumps({
                "status": "error",
                "error": str(e),
                "folder_path": folder_path
            })
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)