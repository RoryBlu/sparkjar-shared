"""
Database models for SparkJAR Crew system.
AUTO-GENERATED from database schema - DO NOT EDIT MANUALLY.
Use UPDATE_MODELS.py script to regenerate.
"""
from sqlalchemy import Column, String, DateTime, Text, Integer, BigInteger, Date, Boolean, Float, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey, CheckConstraint, UniqueConstraint
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

Base = declarative_base()

# Note: CrewConfig is defined as CrewCfgs class below

class CallSessions(Base):
    """
    call_sessions table model.
    """
    __tablename__ = "call_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    client_user_id = Column(UUID(as_uuid=True), nullable=False)
    call_context = Column(Text, nullable=True)
    call_metadata = Column(JSONB, nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def __repr__(self):
        return f"<CallSessions(id='{self.id}')>"

class CallTranscriptSegments(Base):
    """
    call_transcript_segments table model.
    """
    __tablename__ = "call_transcript_segments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    call_id = Column(UUID(as_uuid=True), nullable=False)
    speaker = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<CallTranscriptSegments(id='{self.id}')>"

class ChatMessages(Base):
    """
    chat_messages table model.
    """
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    previous_message_id = Column(Text, nullable=False)
    message_role = Column(Text, nullable=False)
    message_text = Column(Text, nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatMessages(id='{self.id}')>"

class ChatSessions(Base):
    """
    chat_sessions table model.
    """
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    client_user_id = Column(UUID(as_uuid=True), nullable=False)
    chat_context = Column(Text, nullable=True)
    chat_metadata = Column(JSONB, nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatSessions(id='{self.id}')>"

class ClientRoles(Base):
    """
    client_roles table model.
    """
    __tablename__ = "client_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    role_code = Column(Text, nullable=False)
    role_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ClientRoles(id='{self.id}')>"

class ClientSecrets(Base):
    """
    client_secrets table model.
    """
    __tablename__ = "client_secrets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=False)
    actor_type = Column(Text, nullable=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    secret_key = Column(Text, nullable=True)
    secret_value = Column(Text, nullable=True)
    secrets_metadata = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ClientSecrets(id='{self.id}')>"

class ClientUserRoles(Base):
    """
    client_user_roles table model.
    """
    __tablename__ = "client_user_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    client_user_id = Column(UUID(as_uuid=True), nullable=True)
    role_id = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<ClientUserRoles(id='{self.id}')>"

class ClientUsers(Base):
    """
    client_users table model.
    """
    __tablename__ = "client_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    clients_id = Column(UUID(as_uuid=True), nullable=False)
    email = Column(Text, nullable=False)
    full_name = Column(Text, nullable=False)
    preferred_name = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    attributes = Column(JSONB, nullable=True)
    timezone = Column(Text, nullable=True)
    language = Column(Text, nullable=True)
    last_active_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ClientUsers(id='{self.id}')>"

class Clients(Base):
    """
    clients table model.
    """
    __tablename__ = "clients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    legal_name = Column(Text, nullable=False)
    display_name = Column(Text, nullable=True)
    domain = Column(Text, nullable=True)
    website_url = Column(Text, nullable=True)
    industry = Column(Text, nullable=True)
    naics_code = Column(Text, nullable=True)
    tax_id = Column(Text, nullable=True)
    number_of_employees = Column(Integer, nullable=True)
    status = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    client_metadata = Column(JSONB, nullable=False)
    client_key = Column(Text, nullable=False)

    def __repr__(self):
        return f"<Clients(id='{self.id}')>"

class CrewCfgs(Base):
    """
    crew_cfgs table model.
    """
    __tablename__ = "crew_cfgs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(Text, nullable=False)
    config_type = Column(Text, nullable=False)
    config_data = Column(JSONB, nullable=False)
    schema_name = Column(Text, nullable=False)
    version = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<CrewCfgs(id='{self.id}')>"

class CrewJobEvent(Base):
    """
    crew_job_event table model.
    """
    __tablename__ = "crew_job_event"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(Text, nullable=False)
    event_data = Column(JSONB, nullable=True)
    event_time = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<CrewJobEvent(id='{self.id}')>"

class CrewJobs(Base):
    """
    crew_jobs table model.
    """
    __tablename__ = "crew_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    job_key = Column(Text, nullable=False)
    client_user_id = Column(UUID(as_uuid=True), nullable=False)
    actor_type = Column(Text, nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(Text, nullable=True)
    queued_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False)
    last_error = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=False)
    result = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<CrewJobs(id='{self.id}')>"

class CrewMemory(Base):
    """
    crew_memory table model.
    """
    __tablename__ = "crew_memory"
    
    id = Column(String, primary_key=True, nullable=False)
    crew_id = Column(String, nullable=False)
    memory_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    memory_metadata = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<CrewMemory(id='{self.id}')>"

class EntityResearch(Base):
    """
    entity_research table model.
    """
    __tablename__ = "entity_research"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=False)
    entity_type = Column(Text, nullable=False)
    legal_name = Column(Text, nullable=False)
    tin = Column(Text, nullable=True)
    reg_or_birth_state = Column(Text, nullable=True)
    reg_or_birth_country = Column(Text, nullable=True)
    date_incorp_or_birth = Column(Date, nullable=True)
    reg_number = Column(Text, nullable=True)
    report_text = Column(Text, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<EntityResearch(id='{self.id}')>"

class KnowledgeCollections(Base):
    """
    knowledge_collections table model.
    """
    __tablename__ = "knowledge_collections"
    
    id = Column(String, primary_key=True, nullable=False)
    collection_name = Column(String, nullable=False)
    collection_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    collection_metadata = Column(String, nullable=True)
    document_count = Column(String, nullable=True)
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<KnowledgeCollections(id='{self.id}')>"

class ObjectSchemas(Base):
    """
    object_schemas table model.
    """
    __tablename__ = "object_schemas"
    
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Text, nullable=False)
    object_type = Column(Text, nullable=False)
    schema = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, default=datetime.utcnow)

    def __repr__(self):
        return f"<ObjectSchemas(id='{self.id}')>"

class ObjectEmbeddings(Base):
    """
    object_embeddings table model.
    Stores embeddings for semantic search across knowledge realms.
    """
    __tablename__ = "object_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    
    # Client realm (nullable for synth_class and skill_module)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Source tracking
    source_table = Column(Text, nullable=False)
    source_id = Column(UUID(as_uuid=True), nullable=False)
    source_field = Column(Text, nullable=True)
    
    # Embedding data
    embedding_model = Column(Text, nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    embedding = Column(Vector, nullable=True)  # Dynamic dimension based on model
    
    # Context/Realm tracking
    actor_type = Column(Text, nullable=False)
    actor_id = Column(Text, nullable=False)
    
    # Metadata
    metadata = Column(JSONB, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ObjectEmbeddings(id='{self.id}', model='{self.embedding_model}')>"

class SynthClasses(Base):
    """
    synth_classes table model.
    """
    __tablename__ = "synth_classes"
    
    id = Column(Integer, primary_key=True, nullable=False)
    job_key = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    default_attributes = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<SynthClasses(id='{self.id}')>"

class Synths(Base):
    """
    synths table model.
    """
    __tablename__ = "synths"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    synth_classes_id = Column(Integer, nullable=True)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    preferred_name = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    backstory = Column(Text, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, default=datetime.utcnow)
    role_code = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Synths(id='{self.id}')>"
