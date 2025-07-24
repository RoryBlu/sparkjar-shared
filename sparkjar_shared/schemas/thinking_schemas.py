"""
Pydantic schemas for Sequential Thinking feature.
Provides request/response models for the thinking API endpoints.
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime

class ThinkingBaseModel(BaseModel):
    """Base model with common configuration."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {}
        }
    )

# Request Models

class CreateSessionRequest(ThinkingBaseModel):
    """Request to create a new thinking session."""
    client_user_id: UUID = Field(..., description="ID of the user creating the session")
    session_name: Optional[str] = Field(None, max_length=255, description="Optional name for the session")
    problem_statement: Optional[str] = Field(None, max_length=5000, description="The problem to solve")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_user_id": "123e4567-e89b-12d3-a456-426614174000",
                "session_name": "API Design Review",
                "problem_statement": "How should we structure the new payment processing API?",
                "metadata": {"project": "payments", "priority": "high"}
            }
        }
    )

class AddThoughtRequest(ThinkingBaseModel):
    """Request to add a thought to a session."""
    thought_content: str = Field(..., min_length=1, max_length=10000, description="The thought content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('thought_content')
    @classmethod
    def validate_thought_content(cls, v: str) -> str:
        """Ensure thought content is not just whitespace."""
        if not v.strip():
            raise ValueError("Thought content cannot be empty or just whitespace")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thought_content": "We should use RESTful principles with clear resource endpoints",
                "metadata": {"category": "architecture", "confidence": 0.8}
            }
        }
    )

class ReviseThoughtRequest(ThinkingBaseModel):
    """Request to revise an existing thought."""
    thought_number: int = Field(..., gt=0, description="The thought number to revise")
    revised_content: str = Field(..., min_length=1, max_length=10000, description="The revised thought content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('revised_content')
    @classmethod
    def validate_revised_content(cls, v: str) -> str:
        """Ensure revised content is not just whitespace."""
        if not v.strip():
            raise ValueError("Revised content cannot be empty or just whitespace")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thought_number": 3,
                "revised_content": "Actually, we should use GraphQL instead of REST for better flexibility",
                "metadata": {"reason": "performance", "discussed_with": "team"}
            }
        }
    )

class CompleteSessionRequest(ThinkingBaseModel):
    """Request to complete a thinking session."""
    final_answer: str = Field(..., min_length=1, max_length=50000, description="The final answer/solution")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('final_answer')
    @classmethod
    def validate_final_answer(cls, v: str) -> str:
        """Ensure final answer is not just whitespace."""
        if not v.strip():
            raise ValueError("Final answer cannot be empty or just whitespace")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "final_answer": "Based on the analysis, we will implement a GraphQL API with the following schema...",
                "metadata": {"decision_factors": ["performance", "flexibility", "team_expertise"]}
            }
        }
    )

class AbandonSessionRequest(ThinkingBaseModel):
    """Request to abandon a thinking session."""
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for abandoning")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Requirements changed significantly",
                "metadata": {"new_project_id": "proj-456"}
            }
        }
    )

# Response Models

class ThoughtResponse(ThinkingBaseModel):
    """Response model for a single thought."""
    id: UUID = Field(..., description="Unique thought ID")
    session_id: UUID = Field(..., description="Parent session ID")
    thought_number: int = Field(..., description="Sequential thought number")
    thought_content: str = Field(..., description="The thought content")
    is_revision: bool = Field(..., description="Whether this is a revision")
    revises_thought_number: Optional[int] = Field(None, description="Which thought this revises")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(..., description="When the thought was created")

class SessionResponse(ThinkingBaseModel):
    """Response model for a thinking session."""
    id: UUID = Field(..., description="Unique session ID")
    client_user_id: UUID = Field(..., description="User who created the session")
    session_name: Optional[str] = Field(None, description="Session name")
    problem_statement: Optional[str] = Field(None, description="Problem being solved")
    status: Literal["active", "completed", "abandoned"] = Field(..., description="Session status")
    final_answer: Optional[str] = Field(None, description="Final answer if completed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(..., description="When session was created")
    completed_at: Optional[datetime] = Field(None, description="When session was completed/abandoned")
    thoughts: Optional[List[ThoughtResponse]] = Field(None, description="List of thoughts in the session")

class SessionStatsResponse(ThinkingBaseModel):
    """Response model for session statistics."""
    session_id: UUID = Field(..., description="Session ID")
    client_user_id: UUID = Field(..., description="User ID")
    status: str = Field(..., description="Session status")
    total_thoughts: int = Field(..., description="Total number of thoughts")
    revision_count: int = Field(..., description="Number of revisions")
    revised_thought_numbers: List[int] = Field(..., description="Which thoughts were revised")
    average_thought_length: int = Field(..., description="Average length of thoughts")
    duration_seconds: int = Field(..., description="Session duration in seconds")
    thoughts_per_minute: float = Field(..., description="Rate of thought generation")

class SessionListResponse(ThinkingBaseModel):
    """Response model for listing sessions."""
    sessions: List[SessionResponse] = Field(..., description="List of sessions")
    total: int = Field(..., description="Total count of sessions")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessions": [],
                "total": 42,
                "page": 1,
                "page_size": 10
            }
        }
    )

class ErrorResponse(ThinkingBaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Session not found",
                "details": {"session_id": "123e4567-e89b-12d3-a456-426614174000"}
            }
        }
    )

# Validation Models for Object Schemas

class ThinkingSessionSchema(ThinkingBaseModel):
    """Schema for thinking session validation."""
    name: Literal["thinking_session"] = Field(default="thinking_session")
    object_type: Literal["thinking"] = Field(default="thinking")
    schema: Dict[str, Any] = Field(
        default={
            "type": "object",
            "properties": {
                "client_user_id": {"type": "string", "format": "uuid"},
                "session_name": {"type": "string", "maxLength": 255},
                "problem_statement": {"type": "string", "maxLength": 5000},
                "metadata": {"type": "object"}
            },
            "required": ["client_user_id"]
        }
    )
    description: str = Field(default="Schema for Sequential Thinking sessions")

class ThoughtSchema(ThinkingBaseModel):
    """Schema for thought validation."""
    name: Literal["thought"] = Field(default="thought")
    object_type: Literal["thinking"] = Field(default="thinking")
    schema: Dict[str, Any] = Field(
        default={
            "type": "object",
            "properties": {
                "thought_content": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 10000
                },
                "metadata": {"type": "object"}
            },
            "required": ["thought_content"]
        }
    )
    description: str = Field(default="Schema for individual thoughts in Sequential Thinking")