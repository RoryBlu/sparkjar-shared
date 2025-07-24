# shared/schemas/memory_schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal, Union
from uuid import UUID
from datetime import datetime

# Base Observation Models
class Observation(BaseModel):
    type: str = Field(..., description="Type of observation: skill, database_ref, writing_pattern, fact, etc.")
    value: Any = Field(..., description="The main content/value of the observation")
    source: str = Field(default="api", description="Source of the observation")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: Optional[List[str]] = Field(default_factory=list)

class ObservationContent(BaseModel):
    type: str = Field(..., description="Type of observation")
    value: Any = Field(..., description="The main content/value of the observation")
    source: Optional[str] = "api"
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: Optional[List[str]] = Field(default_factory=list)

# Entity Models
class EntityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entityType: str = Field(..., min_length=1, max_length=100)
    observations: List[Observation]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    identityConfidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score that the entity represents a unique identity"
    )
    aliasOf: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="If this entity is an alias, the canonical entity name"
    )

# Relation Models
class RelationCreate(BaseModel):
    from_entity_name: str = Field(..., min_length=1)
    to_entity_name: str = Field(..., min_length=1)
    relationType: str = Field(..., min_length=1, max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class RelationDelete(BaseModel):
    from_entity_name: str
    to_entity_name: str
    relation_type: str

# Observation Operations
class ObservationAdd(BaseModel):
    entityName: str = Field(..., min_length=1)
    contents: List[ObservationContent]

# Request Models for API
class BaseMemoryRequest(BaseModel):
    client_id: UUID
    actor_type: Literal["human", "synth"]
    actor_id: UUID

class CreateEntitiesRequest(BaseMemoryRequest):
    entities: List[EntityCreate]

class CreateRelationsRequest(BaseMemoryRequest):
    relations: List[RelationCreate]

class AddObservationsRequest(BaseMemoryRequest):
    observations: List[ObservationAdd]

class SearchRequest(BaseMemoryRequest):
    query: str = Field(..., min_length=1)
    entity_types: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=100)

class OpenNodesRequest(BaseMemoryRequest):
    names: List[str] = Field(..., min_items=1)

class GetEntitiesRequest(BaseMemoryRequest):
    entity_names: Optional[List[str]] = None
    entity_types: Optional[List[str]] = None
    names: Optional[List[str]] = None  # Legacy support for open_nodes

class ReadGraphRequest(BaseMemoryRequest):
    pass

class DeleteEntitiesRequest(BaseMemoryRequest):
    entity_names: List[str] = Field(..., min_items=1)

class DeleteRelationsRequest(BaseMemoryRequest):
    relations: List[RelationDelete]

# SparkJar-specific request models
class RememberConversationRequest(BaseMemoryRequest):
    conversation_text: str = Field(..., min_length=1)
    participants: List[str] = Field(..., min_items=1)
    context: Dict[str, Any] = Field(default_factory=dict)

class FindConnectionsRequest(BaseMemoryRequest):
    from_entity: str = Field(..., min_length=1)
    to_entity: Optional[str] = None
    max_hops: int = Field(default=3, ge=1, le=5)
    relationship_types: Optional[List[str]] = None

class GetClientInsightsRequest(BaseMemoryRequest):
    pass

# Cross-Context Access Request
class CrossContextAccessRequest(BaseModel):
    client_id: UUID
    requesting_actor_type: Literal["human", "synth", "synth_class", "client"]
    requesting_actor_id: UUID
    target_actor_type: Literal["human", "synth", "synth_class", "client"]
    target_actor_id: UUID
    query: Optional[str] = None
    permission_check: bool = Field(default=True, description="Whether to enforce permission checks")

# Text Processing request models
class ProcessTextChunkRequest(BaseMemoryRequest):
    text: str = Field(..., min_length=1, max_length=50000, description="Text chunk to process")
    source: str = Field(default="text_chunk", description="Source identifier for tracking")
    extract_context: bool = Field(default=True, description="Whether to search for context from existing memories")
    context_preview_length: int = Field(default=500, description="Length of text preview for context search")

# Response Models
class EntityResponse(BaseModel):
    id: UUID
    entity_name: str
    entity_type: str
    observations: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    identity_confidence: Optional[float] = None
    alias_of: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    similarity: Optional[float] = None

class RelationResponse(BaseModel):
    id: UUID
    from_entity_name: str
    from_entity_type: str
    to_entity_name: str
    to_entity_type: str
    relation_type: str
    metadata: Dict[str, Any]
    created_at: datetime

class GraphResponse(BaseModel):
    entities: List[EntityResponse]
    relations: List[RelationResponse]
    total_entities: int
    total_relations: int