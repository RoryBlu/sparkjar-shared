"""Google Drive Download Tool - downloads a single file by ID.

Production-ready tool for downloading individual manuscript images from Google Drive.
Supports all required image formats and includes comprehensive error handling.
"""
import os
import json
import tempfile
import logging
from pathlib import Path
from typing import Type, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, validator

from tools.google_drive_tool import GoogleDriveTool

logger = logging.getLogger(__name__)

# Supported image formats as per requirements
SUPPORTED_IMAGE_FORMATS = {
    'png': 'image/png',
    'jpg': 'image/jpeg', 
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
    'gif': 'image/gif',
    'bmp': 'image/bmp',
    'tiff': 'image/tiff',
    'tif': 'image/tiff'
}

class GoogleDriveDownloadInput(BaseModel):
    """Input schema for downloading a single file."""
    file_id: str = Field(
        ..., 
        description="Google Drive file ID to download",
        min_length=1
    )
    file_name: str = Field(
        ..., 
        description="Name of the file for saving locally",
        min_length=1
    )
    client_user_id: str = Field(
        ..., 
        description="Client user ID for credentials",
        min_length=1
    )
    
    @validator('file_name')
    def validate_image_format(cls, v):
        """Validate that the file has a supported image format."""
        if not v:
            raise ValueError("File name cannot be empty")
        
        # Extract file extension
        file_path = Path(v)
        extension = file_path.suffix.lower().lstrip('.')
        
        if not extension:
            raise ValueError("File must have an extension")
        
        if extension not in SUPPORTED_IMAGE_FORMATS:
            supported = ', '.join(SUPPORTED_IMAGE_FORMATS.keys())
            raise ValueError(
                f"Unsupported image format '{extension}'. "
                f"Supported formats: {supported}"
            )
        
        return v


class GoogleDriveDownloadTool(BaseTool):
    """Download a single file from Google Drive with comprehensive error handling.
    
    This tool is designed for production use in the book ingestion crew.
    It downloads one file at a time, validates image formats, and provides
    detailed error reporting for troubleshooting.
    """
    
    name: str = "google_drive_download"
    description: str = (
        "Download a single image file from Google Drive by file ID. "
        "Supports PNG, JPG, JPEG, WEBP, GIF, BMP, and TIFF formats. "
        "Returns local file path for further processing."
    )
    args_schema: Type[BaseModel] = GoogleDriveDownloadInput
    
    def __init__(self):
        super().__init__()
        self._temp_dirs = []  # Track temp directories for cleanup
    
    def _validate_file_format(self, file_name: str) -> str:
        """Validate and return the MIME type for the file."""
        file_path = Path(file_name)
        extension = file_path.suffix.lower().lstrip('.')
        
        if extension not in SUPPORTED_IMAGE_FORMATS:
            supported = ', '.join(SUPPORTED_IMAGE_FORMATS.keys())
            raise ValueError(
                f"Unsupported image format '{extension}'. "
                f"Supported formats: {supported}"
            )
        
        return SUPPORTED_IMAGE_FORMATS[extension]
    
    def _create_temp_directory(self) -> Path:
        """Create a temporary directory for file download."""
        temp_dir = Path(tempfile.mkdtemp(prefix="book_page_download_"))
        self._temp_dirs.append(temp_dir)
        logger.info(f"Created temporary directory: {temp_dir}")
        return temp_dir
    
    def _cleanup_temp_directory(self, temp_dir: Path) -> None:
        """Clean up a specific temporary directory."""
        try:
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
                if temp_dir in self._temp_dirs:
                    self._temp_dirs.remove(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")
    
    def _run(self, file_id: str, file_name: str, client_user_id: str) -> str:
        """Download a single file and return the local path.
        
        Args:
            file_id: Google Drive file ID to download
            file_name: Name of the file for saving locally
            client_user_id: Client user ID for credential lookup
            
        Returns:
            JSON string with download result including local_path or error details
        """
        temp_dir = None
        
        try:
            logger.info(f"Starting download: file_id={file_id}, file_name={file_name}, client_user_id={client_user_id}")
            
            # Validate image format
            mime_type = self._validate_file_format(file_name)
            logger.info(f"Validated file format: {file_name} -> {mime_type}")
            
            # Create temp directory for this download
            temp_dir = self._create_temp_directory()
            
            # Initialize GoogleDriveTool with our temp directory
            drive_tool = GoogleDriveTool()
            drive_tool._temp_dir = temp_dir
            
            # Get service with client credentials
            service = drive_tool._get_service(client_user_id, readonly=True)
            logger.info(f"Retrieved Google Drive service for client: {client_user_id}")
            
            # Verify file exists and get metadata
            try:
                file_metadata = service.files().get(
                    fileId=file_id,
                    fields="id,name,mimeType,size,parents",
                    supportsAllDrives=True
                ).execute()
                
                logger.info(f"File metadata: {file_metadata}")
                
                # Validate MIME type matches expected format
                actual_mime = file_metadata.get('mimeType', '')
                if actual_mime and actual_mime != mime_type:
                    logger.warning(f"MIME type mismatch: expected {mime_type}, got {actual_mime}")
                
            except Exception as e:
                raise ValueError(f"File not found or not accessible: {file_id}. Error: {str(e)}")
            
            # Download the file
            local_path = drive_tool._download_file(service, file_id, file_name)
            
            # Verify file was downloaded successfully
            local_file = Path(local_path)
            if not local_file.exists():
                raise RuntimeError(f"Download completed but file not found at: {local_path}")
            
            file_size = local_file.stat().st_size
            if file_size == 0:
                raise RuntimeError(f"Downloaded file is empty: {local_path}")
            
            logger.info(f"Successfully downloaded file: {local_path} ({file_size} bytes)")
            
            return json.dumps({
                "success": True,
                "local_path": local_path,
                "file_name": file_name,
                "file_id": file_id,
                "file_size": file_size,
                "mime_type": mime_type,
                "temp_directory": str(temp_dir)
            })
            
        except ValueError as e:
            # Input validation errors
            logger.error(f"Validation error: {e}")
            if temp_dir:
                self._cleanup_temp_directory(temp_dir)
            return json.dumps({
                "success": False,
                "error": str(e),
                "error_type": "validation_error",
                "file_id": file_id,
                "file_name": file_name
            })
            
        except Exception as e:
            # All other errors
            logger.error(f"Download error: {e}", exc_info=True)
            if temp_dir:
                self._cleanup_temp_directory(temp_dir)
            return json.dumps({
                "success": False,
                "error": str(e),
                "error_type": "download_error",
                "file_id": file_id,
                "file_name": file_name
            })
    
    def cleanup_all(self) -> None:
        """Clean up all temporary directories created by this tool."""
        for temp_dir in self._temp_dirs.copy():
            self._cleanup_temp_directory(temp_dir)