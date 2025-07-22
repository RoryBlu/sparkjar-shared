"""
MCP Registry Database Models

This module defines the database schema for the MCP Registry service.
These models are used to register, discover, and monitor MCP services.
"""

from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship
from sparkjar_crew.shared.database.models import Base
from datetime import datetime
import uuid

class MCPService(Base):
    """Core service registry table"""
    __tablename__ = "mcp_services"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(Text, nullable=False)
    service_type = Column(Text, nullable=False)  # 'memory', 'thinking', 'chroma', 'custom'
    service_version = Column(Text, nullable=False)
    base_url = Column(Text, nullable=False)
    internal_url = Column(Text)  # Railway internal IPv6 URL
    protocol = Column(Text, default='mcp-over-http')  # 'mcp-over-http', 'mcp-stdio', 'rest'
    authentication_type = Column(Text, default='bearer')  # 'bearer', 'basic', 'none'
    authentication_credentials = Column(Text)  # Encrypted credentials if needed
    client_id = Column(UUID(as_uuid=True))  # NULL for global services, UUID for client-specific
    status = Column(Text, default='inactive')  # 'active', 'inactive', 'unhealthy', 'maintenance'
    service_metadata_json = Column("metadata", JSONB, server_default=text("'{}'::jsonb"))  # Extra service-specific config
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(TIMESTAMP(timezone=True))
    
    # Relationships
    tools = relationship("MCPServiceTool", back_populates="service", cascade="all, delete-orphan")
    health_checks = relationship("MCPServiceHealth", back_populates="service", cascade="all, delete-orphan")
    events = relationship("MCPServiceEvent", back_populates="service", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('service_name', 'client_id', name='uq_service_name_client'),
        Index('idx_mcp_services_status', 'status'),
        Index('idx_mcp_services_client', 'client_id'),
        Index('idx_mcp_services_type', 'service_type'),
        Index('idx_mcp_services_name_client', 'service_name', 'client_id'),
    )

class MCPServiceTool(Base):
    """Available tools per service"""
    __tablename__ = "mcp_service_tools"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), ForeignKey('mcp_services.id', ondelete='CASCADE'), nullable=False)
    tool_name = Column(Text, nullable=False)
    tool_description = Column(Text)
    input_schema = Column(JSONB, nullable=False)  # JSON Schema for tool inputs
    output_schema = Column(JSONB)  # JSON Schema for tool outputs
    tool_metadata_json = Column("metadata", JSONB, server_default=text("'{}'::jsonb"))  # Tool-specific metadata
    is_enabled = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    service = relationship("MCPService", back_populates="tools")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('service_id', 'tool_name', name='uq_service_tool'),
        Index('idx_mcp_service_tools_service', 'service_id'),
        Index('idx_mcp_service_tools_name', 'tool_name'),
    )

class MCPServiceHealth(Base):
    """Health check history"""
    __tablename__ = "mcp_service_health"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), ForeignKey('mcp_services.id', ondelete='CASCADE'), nullable=False)
    check_type = Column(Text, nullable=False)  # 'ping', 'deep', 'tool_test'
    status = Column(Text, nullable=False)  # 'healthy', 'degraded', 'unhealthy', 'error'
    response_time_ms = Column(Integer)
    error_message = Column(Text)
    health_metadata_json = Column("metadata", JSONB, server_default=text("'{}'::jsonb"))  # Additional health details
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    
    # Relationships
    service = relationship("MCPService", back_populates="health_checks")
    
    # Constraints
    __table_args__ = (
        Index('idx_mcp_service_health_service_created', 'service_id', 'created_at'),
    )

class MCPServiceDiscoveryCache(Base):
    """Performance optimization cache"""
    __tablename__ = "mcp_service_discovery_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True))
    query_hash = Column(Text, nullable=False)  # Hash of discovery query params
    cached_response = Column(JSONB, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('client_id', 'query_hash', name='uq_cache_client_query'),
        Index('idx_mcp_discovery_cache_expires', 'expires_at'),
    )

class MCPServiceEvent(Base):
    """Audit trail"""
    __tablename__ = "mcp_service_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), ForeignKey('mcp_services.id', ondelete='CASCADE'), nullable=False)
    event_type = Column(Text, nullable=False)  # 'registered', 'updated', 'health_changed', 'unregistered'
    event_data = Column(JSONB, default=dict)
    created_by = Column(UUID(as_uuid=True))  # User/service that triggered event
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    
    # Relationships
    service = relationship("MCPService", back_populates="events")
    
    # Constraints
    __table_args__ = (
        Index('idx_mcp_service_events_service_created', 'service_id', 'created_at'),
        Index('idx_mcp_service_events_type', 'event_type'),
    )