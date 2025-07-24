"""
Database models for SparkJAR Crew system.
AUTO-GENERATED from database schema - DO NOT EDIT MANUALLY.
Use UPDATE_MODELS.py script to regenerate.

PROTECTED NAME MAPPINGS:
The following database column names are mapped to Python-safe attribute names:
- metadata -> metadata_json
- class -> class_name
- type -> type_name
- schema -> schema_data
- Any other Python/SQLAlchemy reserved words are similarly mapped

To access these columns in queries, use the mapped Python attribute name.
Example: MyModel.metadata_json (not MyModel.metadata)

ACTOR TYPE SYSTEM:
The memory system uses actor_type and actor_id to provide context for all operations.
Valid actor_type values and their corresponding tables:
- 'human' -> client_users table (for human users)
- 'synth' -> synths table (for AI agents/personas)
- 'synth_class' -> synth_classes table (for agent class definitions)
- 'client' -> clients table (for client organizations)

This allows the memory system to work across different contexts without requiring
a direct client_id relationship on every memory entity.
"""
from sqlalchemy import Column, String, DateTime, Text, Integer, BigInteger, Date, Boolean, Index, Numeric, Float, Time, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, JSON, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

Base = declarative_base()

# Import crew configuration model
try:
    from services.crew_api.src.database.crew_config_model import CrewConfig
except ImportError:
    # Define a placeholder if not available
    class CrewConfig:
        pass


class BookIngestions(Base):
    __tablename__ = "book_ingestions"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    book_key = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    file_name = Column(Text, nullable=False)
    language_code = Column(Text, nullable=False)
    version = Column(Text, nullable=False, server_default=text("'original'::text"))
    page_text = Column(Text, nullable=False)
    ocr_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class CallSessions(Base):
    __tablename__ = "call_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    client_user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id"), nullable=False)
    call_context = Column(Text)
    call_metadata = Column(JSONB, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at = Column(DateTime(timezone=True))


class CallTranscriptSegments(Base):
    __tablename__ = "call_transcript_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    call_id = Column(UUID(as_uuid=True), ForeignKey("call_sessions.id"), nullable=False)
    speaker = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChatMessages(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    session_id = Column(UUID(as_uuid=True), nullable=False)
    previous_message_id = Column(Text, nullable=False)
    message_role = Column(Text, nullable=False)
    message_text = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChatSessions(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    client_user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id"), nullable=False)
    chat_context = Column(Text)
    chat_metadata = Column(JSONB, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClientRoles(Base):
    __tablename__ = "client_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    role_code = Column(Text, nullable=False)
    role_name = Column(Text, nullable=False)
    description = Column(Text)


class ClientSecrets(Base):
    __tablename__ = "client_secrets"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    actor_type = Column(Text)
    actor_id = Column(UUID(as_uuid=True))
    secret_key = Column(Text)
    secret_value = Column(Text)
    secrets_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClientUserRoles(Base):
    __tablename__ = "client_user_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    client_user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id"))
    role_id = Column(UUID(as_uuid=True), ForeignKey("client_roles.id"))


class ClientUsers(Base):
    __tablename__ = "client_users"
    # Actor type: human

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    clients_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    email = Column(Text, nullable=False)
    full_name = Column(Text, nullable=False)
    preferred_name = Column(Text)
    bio = Column(Text)
    avatar_url = Column(Text)
    attributes = Column(JSONB)
    timezone = Column(Text)
    language = Column(Text, server_default=text("'en'::text"))
    last_active_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Clients(Base):
    __tablename__ = "clients"
    # Actor type: client

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    legal_name = Column(Text, nullable=False)
    display_name = Column(Text)
    domain = Column(Text)
    website_url = Column(Text)
    industry = Column(Text)
    naics_code = Column(Text)
    tax_id = Column(Text)
    number_of_employees = Column(Integer)
    status = Column(Text, nullable=False, server_default=text("'active'::text"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    client_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    client_key = Column(Text, nullable=False)


class CrewCfgs(Base):
    __tablename__ = "crew_cfgs"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    name = Column(Text, nullable=False)
    config_type = Column(Text, nullable=False)
    config_data = Column(JSONB, nullable=False)
    schema_name = Column(Text, nullable=False)
    version = Column(Text, server_default=text("'1.0'::text"))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CrewJobEvent(Base):
    __tablename__ = "crew_job_event"

    id = Column(BigInteger, primary_key=True, nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("crew_jobs.id"), nullable=False)
    event_type = Column(Text, nullable=False)
    event_data = Column(JSONB)
    event_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CrewJobs(Base):
    __tablename__ = "crew_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    job_key = Column(Text, nullable=False)
    client_user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id"), nullable=False)
    actor_type = Column(Text, nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(Text)
    queued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    attempts = Column(Integer, nullable=False)
    last_error = Column(Text)
    notes = Column(Text)
    payload = Column(JSONB, nullable=False)
    result = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CrewMemory(Base):
    __tablename__ = "crew_memory"

    id = Column(String, primary_key=True, nullable=False)
    crew_id = Column(String, nullable=False)
    memory_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    memory_metadata = Column(JSON)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class DocumentVectors(Base):
    __tablename__ = "document_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    source_table = Column(Text, nullable=False)
    source_id = Column(Text, nullable=False)
    source_column = Column(Text)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(String)
    metadata_json = Column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class DocumentVectorsOpenai(Base):
    __tablename__ = "document_vectors_openai"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    source_table = Column(Text, nullable=False)
    source_id = Column(Text, nullable=False)
    source_column = Column(Text)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(String)
    metadata_json = Column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class EntityResearch(Base):
    __tablename__ = "entity_research"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    entity_type = Column(Text, nullable=False)
    legal_name = Column(Text, nullable=False)
    tin = Column(Text)
    reg_or_birth_state = Column(Text)
    reg_or_birth_country = Column(Text, server_default=text("'US'::text"))
    date_incorp_or_birth = Column(Date)
    reg_number = Column(Text)
    report_text = Column(Text)
    attributes = Column(JSONB, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class KnowledgeCollections(Base):
    __tablename__ = "knowledge_collections"

    id = Column(String, primary_key=True, nullable=False)
    collection_name = Column(String, nullable=False)
    collection_type = Column(String, nullable=False)
    description = Column(Text)
    collection_metadata = Column(JSON)
    document_count = Column(String)
    last_updated = Column(DateTime)
    created_at = Column(DateTime, nullable=False)


class McpServiceDiscoveryCache(Base):
    __tablename__ = "mcp_service_discovery_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    client_id = Column(UUID(as_uuid=True))
    query_hash = Column(Text, nullable=False)
    cached_response = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True))


class McpServiceEvents(Base):
    __tablename__ = "mcp_service_events"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    service_id = Column(UUID(as_uuid=True), ForeignKey("mcp_services.id"), nullable=False)
    event_type = Column(Text, nullable=False)
    event_data = Column(JSONB)
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True))


class McpServiceHealth(Base):
    __tablename__ = "mcp_service_health"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    service_id = Column(UUID(as_uuid=True), ForeignKey("mcp_services.id"), nullable=False)
    check_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    response_time_ms = Column(Integer)
    error_message = Column(Text)
    metadata_json = Column('metadata', JSONB)
    created_at = Column(DateTime(timezone=True))


class McpServiceTools(Base):
    __tablename__ = "mcp_service_tools"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    service_id = Column(UUID(as_uuid=True), ForeignKey("mcp_services.id"), nullable=False)
    tool_name = Column(Text, nullable=False)
    tool_description = Column(Text)
    input_schema = Column(JSONB, nullable=False)
    output_schema = Column(JSONB)
    metadata_json = Column('metadata', JSONB)
    is_enabled = Column(Boolean)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class McpServices(Base):
    __tablename__ = "mcp_services"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    service_name = Column(Text, nullable=False)
    service_type = Column(Text, nullable=False)
    service_version = Column(Text, nullable=False)
    base_url = Column(Text, nullable=False)
    internal_url = Column(Text)
    protocol = Column(Text)
    authentication_type = Column(Text)
    authentication_credentials = Column(Text)
    client_id = Column(UUID(as_uuid=True))
    status = Column(Text)
    metadata_json = Column('metadata', JSONB)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    last_seen_at = Column(DateTime(timezone=True))


class MemoryEntities(Base):
    __tablename__ = "memory_entities"
    # Uses actor_type and actor_id for context (human/synth/synth_class/client)

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    actor_type = Column(Text, nullable=False)
    actor_id = Column(Text, nullable=False)
    entity_name = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    metadata_json = Column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class MemoryObservations(Base):
    __tablename__ = "memory_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("memory_entities.id"), nullable=False)
    observation_type = Column(Text, nullable=False)
    observation_value = Column(JSONB, nullable=False)
    source = Column(Text)
    tags = Column(String, server_default=text("'{}'::text[]"))
    context = Column(JSONB, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MemoryRelations(Base):
    __tablename__ = "memory_relations"
    # Relationships between memory entities across different actor contexts

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    from_entity_id = Column(UUID(as_uuid=True), ForeignKey("memory_entities.id"), nullable=False)
    to_entity_id = Column(UUID(as_uuid=True), ForeignKey("memory_entities.id"), nullable=False)
    relation_type = Column(Text, nullable=False)
    metadata_json = Column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ObjectEmbeddings(Base):
    __tablename__ = "object_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    source_id = Column(UUID(as_uuid=True), ForeignKey("book_ingestions.id"), nullable=False)
    embedding = Column(String)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    embeddings_metadata = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ObjectSchemas(Base):
    __tablename__ = "object_schemas"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Text, nullable=False)
    object_type = Column(Text, nullable=False)
    schema_data = Column('schema', JSONB, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class SynthClasses(Base):
    __tablename__ = "synth_classes"
    # Actor type: synth_class

    id = Column(Integer, primary_key=True, nullable=False)
    job_key = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    default_attributes = Column(JSONB, server_default=text("'{}'::jsonb"))


class Synths(Base):
    __tablename__ = "synths"
    # Actor type: synth

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    client_id = Column(UUID(as_uuid=True), ForeignKey("client_roles.role_code"))
    synth_classes_id = Column(Integer, ForeignKey("synth_classes.id"))
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    preferred_name = Column(Text)
    avatar_url = Column(Text)
    backstory = Column(Text)
    attributes = Column(JSONB, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    role_code = Column(Text, ForeignKey("client_roles.role_code"))


class SystemLogs(Base):
    __tablename__ = "system_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text('gen_random_uuid()'))
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source = Column(String(255), nullable=False)
    level = Column(String(20), nullable=False)
    client_id = Column(UUID(as_uuid=True))
    user_id = Column(String(255))
    message = Column(Text, nullable=False)
    context = Column(JSONB)
    trace_id = Column(UUID(as_uuid=True))
    ip_address = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ThinkingSessions(Base):
    __tablename__ = "thinking_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    client_user_id = Column(UUID(as_uuid=True), nullable=False)
    session_name = Column(Text)
    problem_statement = Column(Text)
    status = Column(Text, nullable=False, server_default=text("'active'::text"))
    final_answer = Column(Text)
    metadata_json = Column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class Thoughts(Base):
    __tablename__ = "thoughts"

    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("thinking_sessions.id"), nullable=False)
    thought_number = Column(Integer, nullable=False)
    thought_content = Column(Text, nullable=False)
    is_revision = Column(Boolean, nullable=False)
    revises_thought_number = Column(Integer)
    metadata_json = Column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# Relationships for thinking models
ThinkingSessions.thoughts = relationship("Thoughts", back_populates="session", cascade="all, delete-orphan")
Thoughts.session = relationship("ThinkingSessions", back_populates="thoughts")
