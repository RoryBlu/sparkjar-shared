"""
Base models for crew requests and responses
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BaseCrewRequest(BaseModel):
    """Base request model for all crew operations"""
    
    job_id: UUID = Field(..., description="Unique job identifier")
    crew_name: str = Field(..., description="Name of the crew to execute")
    client_id: UUID = Field(..., description="Client identifier")
    user_id: Optional[UUID] = Field(None, description="User identifier")
    context: Dict[str, Any] = Field(default_factory=dict, description="Request context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "crew_name": "entity_research_crew",
                "client_id": "123e4567-e89b-12d3-a456-426614174001",
                "context": {"entity": "OpenAI", "research_depth": "comprehensive"}
            }
        }


class BaseCrewResponse(BaseModel):
    """Base response model for all crew operations"""
    
    job_id: UUID = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result")
    error: Optional[str] = Field(None, description="Error message if failed")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "completed",
                "result": {"entities": ["OpenAI", "GPT-4"], "confidence": 0.95},
                "started_at": "2024-01-01T00:00:00Z",
                "completed_at": "2024-01-01T00:05:00Z"
            }
        }