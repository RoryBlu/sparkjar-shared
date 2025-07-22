# shared/models/memory_models.py
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index, Numeric as SQLAlchemyNumeric, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

from services.crew_api.src.database.models import Base  # Import from existing database models

class MemoryEntity(Base):
    __tablename__ = "memory_entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=False)
    actor_type = Column(String(10), nullable=False)  # 'human' or 'synth'
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    
    entity_name = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)

    observations = Column(JSON, nullable=False, default=list)
    embedding = Column(Vector(768), nullable=True)  # 768 dimensions for gte-multilingual-base
    identity_confidence = Column(SQLAlchemyNumeric(3, 2), nullable=False, default=1.00)
    alias_of = Column(UUID(as_uuid=True), ForeignKey('memory_entities.id'), nullable=True)
    metadata_json = Column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relations
    from_relations = relationship("MemoryRelation", foreign_keys="MemoryRelation.from_entity_id", back_populates="from_entity")
    to_relations = relationship("MemoryRelation", foreign_keys="MemoryRelation.to_entity_id", back_populates="to_entity")
    
    __table_args__ = (
        Index('idx_memory_entities_client_actor', 'client_id', 'actor_type', 'actor_id'),
        Index('idx_memory_entities_name', 'entity_name'),
        Index('idx_memory_entities_type', 'entity_type'),
        Index('idx_memory_entities_deleted', 'deleted_at'),
        Index('idx_memory_entities_embedding', 'embedding', postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'}),
        Index('idx_memory_entities_alias_of', 'alias_of'),
    )

class MemoryRelation(Base):
    __tablename__ = "memory_relations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=False)
    actor_type = Column(String(10), nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    
    from_entity_type = Column(String(100), nullable=False)
    from_entity_id = Column(UUID(as_uuid=True), ForeignKey('memory_entities.id'), nullable=False)
    from_entity_name = Column(String(255), nullable=False)
    
    to_entity_type = Column(String(100), nullable=False)
    to_entity_id = Column(UUID(as_uuid=True), ForeignKey('memory_entities.id'), nullable=False)
    to_entity_name = Column(String(255), nullable=False)
    
    relation_type = Column(String(100), nullable=False)
    metadata_json = Column('metadata', JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    from_entity = relationship("MemoryEntity", foreign_keys=[from_entity_id], back_populates="from_relations")
    to_entity = relationship("MemoryEntity", foreign_keys=[to_entity_id], back_populates="to_relations")
    
    __table_args__ = (
        Index('idx_memory_relations_client_actor', 'client_id', 'actor_type', 'actor_id'),
        Index('idx_memory_relations_from', 'from_entity_id'),
        Index('idx_memory_relations_to', 'to_entity_id'),
        Index('idx_memory_relations_type', 'relation_type'),
        Index('idx_memory_relations_deleted', 'deleted_at'),
    )