"""
Unified Schema Validation Service

Provides consistent schema validation across all services using the object_schemas table.
Supports caching, error handling, and validation metadata storage.
"""
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from uuid import UUID

try:
    from jsonschema import validate, ValidationError, Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception  # Fallback for type hints

from sqlalchemy.orm import Session
from sqlalchemy import text
import hashlib

logger = logging.getLogger(__name__)

class SchemaValidationResult:
    """Result of schema validation"""
    def __init__(self, 
                 valid: bool,
                 schema_used: Optional[str] = None,
                 schema_id: Optional[int] = None,
                 errors: Optional[List[str]] = None,
                 warnings: Optional[List[str]] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.valid = valid
        self.schema_used = schema_used
        self.schema_id = schema_id
        self.errors = errors or []
        self.warnings = warnings or []
        self.metadata = metadata or {}
        self.validated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "_schema_used": self.schema_used,
            "_schema_id": self.schema_id,
            "_validated_at": self.validated_at.isoformat(),
            "_validation_passed": self.valid,
            "_validation_errors": self.errors,
            "_validation_warnings": self.warnings,
            **self.metadata
        }

class BaseSchemaValidator:
    """
    Base schema validator with caching and consistent error handling.
    
    Features:
    - Schema caching with TTL
    - Consistent error handling
    - Validation metadata generation
    - Support for different object types
    """
    
    def __init__(self, db_session: Session, cache_ttl: int = 300):
        """
        Initialize validator
        
        Args:
            db_session: SQLAlchemy database session
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self.db = db_session
        self.cache_ttl = cache_ttl
        self._schema_cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
        self._cache_enabled = True
    
    def enable_cache(self, enabled: bool = True):
        """Enable or disable schema caching"""
        self._cache_enabled = enabled
        if not enabled:
            self._schema_cache.clear()
    
    def clear_cache(self):
        """Clear the schema cache"""
        self._schema_cache.clear()
    
    def _get_cache_key(self, name: str, object_type: str) -> str:
        """Generate cache key for schema"""
        return f"{object_type}:{name}"
    
    def _is_cache_valid(self, cached_at: datetime) -> bool:
        """Check if cached schema is still valid"""
        age = (datetime.utcnow() - cached_at).total_seconds()
        return age < self.cache_ttl
    
    async def get_schema(self, name: str, object_type: str) -> Optional[Dict[str, Any]]:
        """
        Get schema from cache or database
        
        Args:
            name: Schema name
            object_type: Type of object (e.g., 'memory_observation', 'thinking_metadata')
            
        Returns:
            Schema dict or None if not found
        """
        cache_key = self._get_cache_key(name, object_type)
        
        # Check cache first
        if self._cache_enabled and cache_key in self._schema_cache:
            schema, cached_at = self._schema_cache[cache_key]
            if self._is_cache_valid(cached_at):
                logger.debug(f"Schema '{name}' retrieved from cache")
                return schema
        
        # Query database
        try:
            query = text("""
                SELECT id, name, object_type, schema, description
                FROM object_schemas 
                WHERE name = :name AND object_type = :object_type
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            result = self.db.execute(query, {"name": name, "object_type": object_type}).first()
            
            if result:
                schema = {
                    'id': result[0],
                    'name': result[1],
                    'object_type': result[2],
                    'schema': result[3],
                    'description': result[4]
                }
                
                # Cache the schema
                if self._cache_enabled:
                    self._schema_cache[cache_key] = (schema, datetime.utcnow())
                    logger.debug(f"Schema '{name}' cached")
                
                return schema
            
            logger.warning(f"Schema '{name}' with type '{object_type}' not found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load schema '{name}': {e}")
            return None
    
    async def validate_data(self, 
                          data: Dict[str, Any],
                          schema_name: str,
                          object_type: str,
                          additional_context: Optional[Dict[str, Any]] = None) -> SchemaValidationResult:
        """
        Validate data against a schema
        
        Args:
            data: Data to validate
            schema_name: Name of schema to use
            object_type: Type of object being validated
            additional_context: Additional context for validation metadata
            
        Returns:
            SchemaValidationResult
        """
        # Get schema
        schema_data = await self.get_schema(schema_name, object_type)
        if not schema_data:
            return SchemaValidationResult(
                valid=False,
                errors=[f"Schema '{schema_name}' not found for type '{object_type}'"]
            )
        
        # Validate against JSON schema
        errors = []
        warnings = []
        
        if JSONSCHEMA_AVAILABLE:
            try:
                schema_def = schema_data['schema']
                validate(instance=data, schema=schema_def)
                
                # Check for additional properties if schema is strict
                if schema_def.get('additionalProperties') == False:
                    extra_keys = set(data.keys()) - set(schema_def.get('properties', {}).keys())
                    if extra_keys:
                        warnings.append(f"Additional properties found: {', '.join(extra_keys)}")
                        
            except ValidationError as e:
                errors.append(f"Schema validation error: {e.message}")
                # Add path information if available
                if e.path:
                    errors.append(f"Error at path: {'.'.join(str(p) for p in e.path)}")
            except Exception as e:
                errors.append(f"Validation error: {str(e)}")
        else:
            warnings.append("JSONSchema library not available - structural validation skipped")
        
        # Create validation result
        result = SchemaValidationResult(
            valid=len(errors) == 0,
            schema_used=schema_name,
            schema_id=schema_data['id'],
            errors=errors,
            warnings=warnings,
            metadata=additional_context or {}
        )
        
        # Log result
        if result.valid:
            logger.info(f"Validation successful for schema '{schema_name}'")
        else:
            logger.warning(f"Validation failed for schema '{schema_name}': {errors}")
        
        return result
    
    async def validate_batch(self,
                           items: List[Tuple[Dict[str, Any], str]],
                           object_type: str,
                           additional_context: Optional[Dict[str, Any]] = None) -> List[SchemaValidationResult]:
        """
        Validate multiple items with potentially different schemas
        
        Args:
            items: List of (data, schema_name) tuples
            object_type: Type of all objects being validated
            additional_context: Additional context for all validations
            
        Returns:
            List of SchemaValidationResult
        """
        results = []
        
        for data, schema_name in items:
            result = await self.validate_data(
                data=data,
                schema_name=schema_name,
                object_type=object_type,
                additional_context=additional_context
            )
            results.append(result)
        
        return results
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        return {
            "cache_enabled": self._cache_enabled,
            "schemas_cached": len(self._schema_cache),
            "cache_ttl_seconds": self.cache_ttl
        }

class MemorySchemaValidator(BaseSchemaValidator):
    """Schema validator for memory service with specific patterns"""
    
    def determine_observation_schema(self, obs_type: str) -> str:
        """Determine schema name from observation type"""
        schema_mapping = {
            'skill': 'skill_observation',
            'database_ref': 'database_ref_observation',
            'writing_pattern': 'writing_pattern_observation',
            'general': 'base_observation',
            'fact': 'base_observation'
        }
        return schema_mapping.get(obs_type, 'base_observation')
    
    def determine_entity_metadata_schema(self, entity_type: str) -> str:
        """Determine metadata schema name from entity type"""
        # Try specific schema first
        specific_schema = f"{entity_type}_entity_metadata"
        return specific_schema
    
    async def validate_observation(self, observation: Dict[str, Any], entity_type: str) -> SchemaValidationResult:
        """Validate a single observation"""
        obs_type = observation.get('type', 'general')
        schema_name = self.determine_observation_schema(obs_type)
        
        return await self.validate_data(
            data=observation,
            schema_name=schema_name,
            object_type='memory_observation',
            additional_context={'entity_type': entity_type}
        )
    
    async def validate_entity_metadata(self, metadata: Dict[str, Any], entity_type: str) -> SchemaValidationResult:
        """Validate entity metadata"""
        schema_name = self.determine_entity_metadata_schema(entity_type)
        
        # Try specific schema first
        result = await self.validate_data(
            data=metadata,
            schema_name=schema_name,
            object_type='memory_entity_metadata',
            additional_context={'entity_type': entity_type}
        )
        
        # If specific schema not found, try generic
        if not result.valid and "not found" in str(result.errors):
            result = await self.validate_data(
                data=metadata,
                schema_name='base_entity_metadata',
                object_type='memory_entity_metadata',
                additional_context={'entity_type': entity_type}
            )
        
        return result

class ThinkingSchemaValidator(BaseSchemaValidator):
    """Schema validator for sequential thinking service"""
    
    async def validate_session_metadata(self, metadata: Dict[str, Any]) -> SchemaValidationResult:
        """Validate thinking session metadata"""
        return await self.validate_data(
            data=metadata,
            schema_name='thinking_session_metadata',
            object_type='thinking_metadata'
        )
    
    async def validate_thought_metadata(self, metadata: Dict[str, Any], is_revision: bool = False) -> SchemaValidationResult:
        """Validate thought metadata"""
        schema_name = 'revision_metadata' if is_revision else 'thought_metadata'
        
        return await self.validate_data(
            data=metadata,
            schema_name=schema_name,
            object_type='thinking_metadata',
            additional_context={'is_revision': is_revision}
        )
    
    async def validate_thinking_pattern(self, pattern: Dict[str, Any]) -> SchemaValidationResult:
        """Validate observed thinking pattern"""
        return await self.validate_data(
            data=pattern,
            schema_name='thinking_pattern',
            object_type='thinking_observation'
        )

class CrewSchemaValidator(BaseSchemaValidator):
    """Schema validator for crew API with request validation"""
    
    def __init__(self, db_session: Session):
        # Crew validator doesn't use caching by default
        super().__init__(db_session, cache_ttl=0)
        self.enable_cache(False)
    
    def validate_core_fields(self, data: Dict[str, Any]) -> List[str]:
        """Validate required core fields for crew requests"""
        required_core_fields = ['job_key', 'client_user_id', 'actor_type', 'actor_id']
        errors = []
        
        for field in required_core_fields:
            if field not in data:
                errors.append(f"Missing required core field: {field}")
            elif data[field] is None:
                errors.append(f"Core field '{field}' cannot be null")
            elif isinstance(data[field], str) and not data[field].strip():
                errors.append(f"Core field '{field}' cannot be empty")
        
        return errors
    
    async def validate_crew_request(self, data: Dict[str, Any], job_key: Optional[str] = None) -> SchemaValidationResult:
        """Validate crew request data"""
        # First validate core fields
        core_errors = self.validate_core_fields(data)
        if core_errors:
            return SchemaValidationResult(
                valid=False,
                errors=core_errors
            )
        
        # Determine schema from job_key
        job_key = job_key or data.get('job_key')
        if not job_key:
            return SchemaValidationResult(
                valid=False,
                errors=["No job_key provided for schema determination"]
            )
        
        # Try exact match first
        result = await self.validate_data(
            data=data,
            schema_name=job_key,
            object_type='crew'
        )
        
        # If not found, try gen_crew type
        if not result.valid and "not found" in str(result.errors):
            result = await self.validate_data(
                data=data,
                schema_name=job_key,
                object_type='gen_crew'
            )
        
        return result

# Convenience functions for quick validation
async def validate_memory_observation(db_session: Session, observation: Dict[str, Any], entity_type: str) -> SchemaValidationResult:
    """Quick validation for memory observations"""
    validator = MemorySchemaValidator(db_session)
    return await validator.validate_observation(observation, entity_type)

async def validate_thinking_session(db_session: Session, metadata: Dict[str, Any]) -> SchemaValidationResult:
    """Quick validation for thinking sessions"""
    validator = ThinkingSchemaValidator(db_session)
    return await validator.validate_session_metadata(metadata)

async def validate_crew_request(db_session: Session, data: Dict[str, Any]) -> SchemaValidationResult:
    """Quick validation for crew requests"""
    validator = CrewSchemaValidator(db_session)
    return await validator.validate_crew_request(data)