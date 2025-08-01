"""Simple file creation and upload tool for CrewAI.

This tool creates a text file and uploads it to Google Drive.
"""
import os
import json
import tempfile
from typing import Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from tools.google_drive_tool import GoogleDriveTool

class SimpleFileUploadInput(BaseModel):
    """Input schema for simple file upload."""
    file_name: str = Field(
        ...,
        description="Name of the file to create (e.g., 'book_ingestion_crew_123.txt')"
    )
    content: str = Field(
        ...,
        description="Content to write to the file"
    )
    folder_path: str = Field(
        ...,
        description="Google Drive folder path where file should be uploaded"
    )
    client_user_id: str = Field(
        ...,
        description="Client user ID for credential lookup"
    )

class SimpleFileUploadTool(BaseTool):
    """Tool for creating a text file and uploading it to Google Drive."""
    
    name: str = "simple_file_upload"
    description: str = (
        "Create a text file with specified content and upload it to Google Drive. "
        "Perfect for creating job completion files or simple text documents."
    )
    args_schema: type[BaseModel] = SimpleFileUploadInput
    
    def _run(self, file_name: str, content: str, folder_path: str, 
             client_user_id: str, **kwargs) -> str:
        """
        Create a text file and upload it to Google Drive.
        
        Args:
            file_name: Name for the file
            content: Text content to write
            folder_path: Google Drive folder path
            client_user_id: Client user ID
            
        Returns:
            JSON string with upload result
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', 
                                           delete=False) as tmp_file:
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            try:
                # Use GoogleDriveTool to upload
                drive_tool = GoogleDriveTool()
                result = drive_tool.upload_file(
                    folder_path=folder_path,
                    client_user_id=client_user_id,
                    file_path=tmp_file_path,
                    file_name=file_name,
                    mime_type="text/plain"
                )
                
                # Parse result and add our info
                result_data = json.loads(result)
                result_data["local_file"] = tmp_file_path
                result_data["content_preview"] = content[:200] + "..." if len(content) > 200 else content
                
                return json.dumps(result_data, indent=2)
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
                "file_name": file_name
            })