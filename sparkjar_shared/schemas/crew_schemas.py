"""
Crew execution request/response schemas for SparkJAR services
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CrewExecutionRequest(BaseModel):
    """Request model for crew execution"""
    crew_name: str = Field(..., description="Name of the crew to execute")
    inputs: Dict[str, Any] = Field(..., description="Input parameters for the crew")
    timeout: Optional[int] = Field(300, description="Execution timeout in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "crew_name": "memory_maker_crew",
                "inputs": {
                    "text_content": "This is a sample conversation to analyze",
                    "actor_type": "human",
                    "actor_id": "user-123",
                    "client_user_id": "client-456"
                },
                "timeout": 300
            }
        }


class CrewExecutionResponse(BaseModel):
    """Response model for crew execution"""
    success: bool = Field(..., description="Whether execution was successful")
    crew_name: str = Field(..., description="Name of the executed crew")
    result: Optional[Any] = Field(None, description="Crew execution result")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "crew_name": "memory_maker_crew",
                "result": "Crew execution completed successfully",
                "error": None,
                "execution_time": 45.2,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class CrewHealthResponse(BaseModel):
    """Health check response model for crews service"""
    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    environment: str = Field(..., description="Current environment")
    available_crews: list = Field(..., description="List of available crews")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")


class CrewListResponse(BaseModel):
    """Response model for listing available crews"""
    available_crews: Dict[str, Any] = Field(..., description="Dictionary of available crews and their metadata")
    total_count: int = Field(..., description="Total number of available crews")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")