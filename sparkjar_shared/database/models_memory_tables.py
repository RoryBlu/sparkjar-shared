"""
Pydantic models for memory-related database tables.
These models represent the schema for memory entities, observations, relations, and object schemas.

PROTECTED NAME MAPPINGS:
The following database column names are mapped to Python-safe attribute names in the SQLAlchemy models:
- metadata -> metadata_json (used in memory_entities, memory_relations)
- schema -> schema_data (used in object_schemas)

When accessing these columns via SQLAlchemy, use the mapped names (e.g., MemoryEntities.metadata_json).
When using these Pydantic models, the field names match the Python attribute names.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID

import logging
logger = logging.getLogger(__name__)

# Object Schemas model (defines entity types for memory)
class ObjectSchemaModel(BaseModel):
    """Schema definition for validating entity types and observations"""
    id: Optional[int] = None
    name: str = Field(..., description="Name of the schema")
    object_type: str = Field(..., description="Type of object this schema validates")
    schema_data: Dict[str, Any] = Field(..., description="JSON schema definition", alias="schema")
    description: Optional[str] = Field(None, description="Human-readable description")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

# Memory Entities model
class MemoryEntityModel(BaseModel):
    """Represents entities stored in memory (people, organizations, concepts, etc.)"""
    id: Optional[UUID] = None
    actor_type: str = Field(..., description="Type of actor (user, system, etc.)")
    actor_id: UUID = Field(..., description="ID of the actor who created this entity")
    entity_name: str = Field(..., description="Name of the entity")
    entity_type: str = Field(..., description="Type of entity (person, org, etc.)")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Additional entity metadata", alias="metadata")
    embedding: Optional[str] = Field(None, description="Vector embedding for similarity search")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "actor_type": "user",
                "actor_id": "123e4567-e89b-12d3-a456-426614174001",
                "entity_name": "John Doe",
                "entity_type": "person",
                "metadata": {
                    "title": "Software Engineer",
                    "department": "Engineering"
                }
            }
        }

# Memory Observations model
class MemoryObservationModel(BaseModel):
    """Represents observations about entities (facts, events, attributes)"""
    id: Optional[UUID] = None
    entity_id: UUID = Field(..., description="Entity this observation is about")
    observation_type: str = Field(..., max_length=50, description="Type of observation")
    observation_value: Dict[str, Any] = Field(..., description="The observation data")
    source: str = Field(default="api", max_length=100, description="Source of the observation")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    embedding: Optional[str] = Field(None, description="Vector embedding for similarity search")
    created_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "entity_id": "123e4567-e89b-12d3-a456-426614174000",
                "observation_type": "skill",
                "observation_value": {
                    "skill": "Python",
                    "proficiency": "Expert",
                    "years_experience": 5
                },
                "source": "resume",
                "tags": ["technical", "programming"],
                "context": {
                    "extracted_from": "resume_analysis"
                }
            }
        }

# Memory Relations model
class MemoryRelationModel(BaseModel):
    """Represents relationships between entities"""
    id: Optional[UUID] = None
    from_entity_id: UUID = Field(..., description="Source entity in the relationship")
    to_entity_id: UUID = Field(..., description="Target entity in the relationship")
    relation_type: str = Field(..., max_length=100, description="Type of relationship")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Additional relation metadata", alias="metadata")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "from_entity_id": "123e4567-e89b-12d3-a456-426614174002",
                "to_entity_id": "123e4567-e89b-12d3-a456-426614174003",
                "relation_type": "manages",
                "metadata": {
                    "start_date": "2023-01-01",
                    "department": "Engineering"
                }
            }
        }

# Clients model
class ClientsModel(BaseModel):
    """Represents client organizations"""
    id: Optional[UUID] = None
    legal_name: str = Field(..., description="Legal name of the organization")
    display_name: Optional[str] = Field(None, description="Display name for UI")
    domain: Optional[str] = Field(None, description="Primary domain")
    website_url: Optional[str] = Field(None, description="Website URL")
    industry: Optional[str] = Field(None, description="Industry classification")
    naics_code: Optional[str] = Field(None, description="NAICS industry code")
    tax_id: Optional[str] = Field(None, description="Tax identification number")
    number_of_employees: Optional[int] = Field(None, description="Number of employees")
    status: str = Field(default="active", description="Client status")
    client_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional client metadata")
    client_key: str = Field(..., description="Unique client key")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "legal_name": "Acme Corporation",
                "display_name": "Acme Corp",
                "domain": "acme.com",
                "website_url": "https://www.acme.com",
                "industry": "Technology",
                "naics_code": "541511",
                "number_of_employees": 500,
                "status": "active",
                "client_key": "acme_corp_2024",
                "client_metadata": {
                    "primary_contact": "John Smith",
                    "account_tier": "premium"
                }
            }
        }

# Client Users model
class ClientUsersModel(BaseModel):
    """Represents users associated with clients"""
    id: UUID = Field(..., description="Unique user ID")
    clients_id: UUID = Field(..., description="ID of the associated client")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., description="User's full name")
    preferred_name: Optional[str] = Field(None, description="Preferred display name")
    bio: Optional[str] = Field(None, description="User biography")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    attributes: Optional[Dict[str, Any]] = Field(None, description="Additional user attributes")
    timezone: Optional[str] = Field(None, description="User's timezone")
    language: str = Field(default="en", description="Preferred language")
    last_active_at: Optional[datetime] = Field(None, description="Last activity timestamp")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174005",
                "clients_id": "123e4567-e89b-12d3-a456-426614174004",
                "email": "jane.doe@acme.com",
                "full_name": "Jane Doe",
                "preferred_name": "Jane",
                "bio": "Senior Software Engineer with expertise in AI/ML",
                "timezone": "America/New_York",
                "language": "en",
                "attributes": {
                    "department": "Engineering",
                    "role": "Senior Engineer"
                }
            }
        }

# Synth Classes model
class SynthClassesModel(BaseModel):
    """Represents synthetic agent class definitions"""
    id: Optional[int] = None
    job_key: str = Field(..., description="Unique job key for this synth class")
    title: str = Field(..., description="Title of the synth class")
    description: Optional[str] = Field(None, description="Description of the synth class")
    default_attributes: Dict[str, Any] = Field(default_factory=dict, description="Default attributes for synths of this class")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "job_key": "customer_service_agent",
                "title": "Customer Service Agent",
                "description": "AI agent specialized in customer support interactions",
                "default_attributes": {
                    "language_skills": ["English", "Spanish"],
                    "specialization": "Technical Support",
                    "response_style": "Professional and empathetic"
                }
            }
        }

# Synths model
class SynthsModel(BaseModel):
    """Represents synthetic agents (AI personas)"""
    id: Optional[UUID] = None
    client_id: Optional[UUID] = Field(None, description="Associated client ID")
    synth_classes_id: Optional[int] = Field(None, description="Synth class ID")
    first_name: str = Field(..., description="First name of the synth")
    last_name: str = Field(..., description="Last name of the synth")
    preferred_name: Optional[str] = Field(None, description="Preferred name")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    backstory: Optional[str] = Field(None, description="Backstory or persona description")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional synth attributes")
    role_code: Optional[str] = Field(None, description="Associated role code")
    created_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "client_id": "123e4567-e89b-12d3-a456-426614174004",
                "synth_classes_id": 1,
                "first_name": "Alex",
                "last_name": "Smith",
                "preferred_name": "Alex",
                "backstory": "A friendly and knowledgeable customer service representative with 5 years of experience",
                "role_code": "CS_AGENT",
                "attributes": {
                    "personality_traits": ["helpful", "patient", "detail-oriented"],
                    "expertise_areas": ["billing", "technical support", "account management"]
                }
            }
        }