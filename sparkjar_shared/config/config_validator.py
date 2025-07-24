"""
Centralized Configuration Management System
Provides validation, type checking, and environment profiles for SparkJAR Crew
"""

import os
import logging
from typing import Dict, Any, List, Optional, Union, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json


class Environment(Enum):
    """Supported environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass
class ConfigField:
    """Configuration field definition with validation rules."""
    name: str
    type: Type
    required: bool = True
    default: Any = None
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ""
    sensitive: bool = False  # For logging purposes
    environment_specific: bool = False  # Different values per environment


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    invalid_values: List[str] = field(default_factory=list)


class ConfigValidator:
    """Centralized configuration validator with environment profiles."""
    
    def __init__(self, environment: Optional[str] = None):
        """Initialize configuration validator.
        
        Args:
            environment: Target environment (development, staging, production)
        """
        self.environment = Environment(environment or os.getenv("ENVIRONMENT", "development"))
        self.logger = logging.getLogger(__name__)
        self._config_fields = self._define_config_fields()
        self._environment_profiles = self._define_environment_profiles()
        
    def _define_config_fields(self) -> Dict[str, ConfigField]:
        """Define all configuration fields with validation rules."""
        return {
            # Core Required Configuration
            "API_SECRET_KEY": ConfigField(
                name="API_SECRET_KEY",
                type=str,
                required=True,
                sensitive=True,
                validator=lambda x: len(x) >= 32,
                description="Secret key for JWT generation (minimum 32 characters)"
            ),
            
            # Database Configuration (Required)
            "DATABASE_URL": ConfigField(
                name="DATABASE_URL",
                type=str,
                required=True,
                validator=lambda x: x.startswith(("postgresql://", "postgresql+asyncpg://")),
                description="Primary database connection URL"
            ),
            "DATABASE_URL_DIRECT": ConfigField(
                name="DATABASE_URL_DIRECT",
                type=str,
                required=True,
                validator=lambda x: x.startswith(("postgresql://", "postgresql+asyncpg://")),
                description="Direct database connection URL (port 5432)"
            ),
            "DATABASE_URL_POOLED": ConfigField(
                name="DATABASE_URL_POOLED",
                type=str,
                required=True,
                validator=lambda x: x.startswith(("postgresql://", "postgresql+asyncpg://")),
                description="Pooled database connection URL (port 6543)"
            ),
            
            # OpenAI Configuration (Required)
            "OPENAI_API_KEY": ConfigField(
                name="OPENAI_API_KEY",
                type=str,
                required=True,
                sensitive=True,
                validator=lambda x: x.startswith("sk-"),
                description="OpenAI API key for CrewAI functionality"
            ),
            
            # ChromaDB Configuration (Required for vector storage)
            "CHROMA_URL": ConfigField(
                name="CHROMA_URL",
                type=str,
                required=True,
                environment_specific=True,
                description="ChromaDB service URL (port 8000)"
            ),
            "CHROMA_HOST": ConfigField(
                name="CHROMA_HOST",
                type=str,
                required=True,
                environment_specific=True,
                description="ChromaDB host"
            ),
            "CHROMA_PORT": ConfigField(
                name="CHROMA_PORT",
                type=int,
                required=True,
                validator=lambda x: 1 <= x <= 65535,
                description="ChromaDB port (should be 8000)"
            ),
            
            # Optional ChromaDB Authentication
            "CHROMA_SERVER_AUTHN_CREDENTIALS": ConfigField(
                name="CHROMA_SERVER_AUTHN_CREDENTIALS",
                type=str,
                required=False,
                sensitive=True,
                description="ChromaDB authentication credentials"
            ),
            "CHROMA_SERVER_AUTHN_PROVIDER": ConfigField(
                name="CHROMA_SERVER_AUTHN_PROVIDER",
                type=str,
                required=False,
                description="ChromaDB authentication provider"
            ),
            
            # Supabase Configuration (Optional)
            "SUPABASE_URL": ConfigField(
                name="SUPABASE_URL",
                type=str,
                required=False,
                validator=lambda x: x.startswith("https://") if x else True,
                description="Supabase project URL"
            ),
            "SUPABASE_SECRET_KEY": ConfigField(
                name="SUPABASE_SECRET_KEY",
                type=str,
                required=False,
                sensitive=True,
                description="Supabase service role secret key"
            ),
            "SUPABASE_SERVICE_KEY": ConfigField(
                name="SUPABASE_SERVICE_KEY",
                type=str,
                required=False,
                sensitive=True,
                description="Supabase service key (alias for SUPABASE_SECRET_KEY)"
            ),
            
            # Embedding Configuration (Optional - depends on provider)
            "EMBEDDING_PROVIDER": ConfigField(
                name="EMBEDDING_PROVIDER",
                type=str,
                required=False,
                validator=lambda x: x in ["custom", "openai"] if x else True,
                description="Embedding provider (custom or openai)"
            ),
            "EMBEDDING_MODEL": ConfigField(
                name="EMBEDDING_MODEL",
                type=str,
                required=False,
                description="Custom embedding model name"
            ),
            "EMBEDDING_DIMENSION": ConfigField(
                name="EMBEDDING_DIMENSION",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="Embedding vector dimension"
            ),
            "OPENAI_EMBEDDING_MODEL": ConfigField(
                name="OPENAI_EMBEDDING_MODEL",
                type=str,
                required=False,
                description="OpenAI embedding model name"
            ),
            "OPENAI_EMBEDDING_DIMENSION": ConfigField(
                name="OPENAI_EMBEDDING_DIMENSION",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="OpenAI embedding dimension"
            ),
            "EMBEDDINGS_API_URL": ConfigField(
                name="EMBEDDINGS_API_URL",
                type=str,
                required=False,
                environment_specific=True,
                description="Custom embeddings API URL"
            ),
            "EMBEDDINGS_API_KEY": ConfigField(
                name="EMBEDDINGS_API_KEY",
                type=str,
                required=False,
                sensitive=True,
                description="Custom embeddings API key"
            ),
            
            # MCP Registry Configuration (Optional)
            "MCP_REGISTRY_ENABLED": ConfigField(
                name="MCP_REGISTRY_ENABLED",
                type=bool,
                required=False,
                description="Enable MCP registry service"
            ),
            "MCP_REGISTRY_URL": ConfigField(
                name="MCP_REGISTRY_URL",
                type=str,
                required=False,
                environment_specific=True,
                description="MCP registry service URL"
            ),
            "MCP_REGISTRY_HEALTH_CHECK_INTERVAL": ConfigField(
                name="MCP_REGISTRY_HEALTH_CHECK_INTERVAL",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="MCP registry health check interval (seconds)"
            ),
            "MCP_REGISTRY_CACHE_TTL": ConfigField(
                name="MCP_REGISTRY_CACHE_TTL",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="MCP registry cache TTL (seconds)"
            ),
            "MCP_REGISTRY_UNHEALTHY_THRESHOLD": ConfigField(
                name="MCP_REGISTRY_UNHEALTHY_THRESHOLD",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="MCP registry unhealthy threshold"
            ),
            "MCP_REGISTRY_CLEANUP_INTERVAL": ConfigField(
                name="MCP_REGISTRY_CLEANUP_INTERVAL",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="MCP registry cleanup interval (seconds)"
            ),
            "MCP_SERVERS_CONFIG_PATH": ConfigField(
                name="MCP_SERVERS_CONFIG_PATH",
                type=str,
                required=False,
                description="Path to MCP servers configuration file"
            ),
            
            # External API Keys (Optional)
            "GOOGLE_API_KEY": ConfigField(
                name="GOOGLE_API_KEY",
                type=str,
                required=False,
                sensitive=True,
                description="Google API key for search functionality"
            ),
            "GOOGLE_CSE_ID": ConfigField(
                name="GOOGLE_CSE_ID",
                type=str,
                required=False,
                description="Google Custom Search Engine ID"
            ),
            "SERPER_API_KEY": ConfigField(
                name="SERPER_API_KEY",
                type=str,
                required=False,
                sensitive=True,
                description="Serper API key for search functionality"
            ),
            "NVIDIA_NIM_API_KEY": ConfigField(
                name="NVIDIA_NIM_API_KEY",
                type=str,
                required=False,
                sensitive=True,
                description="NVIDIA NIM API key for OCR functionality"
            ),
            "NVIDIA_OCR_ENDPOINT": ConfigField(
                name="NVIDIA_OCR_ENDPOINT",
                type=str,
                required=False,
                description="NVIDIA OCR API endpoint"
            ),
            
            # Memory Service Configuration (Optional)
            "CREWAI_MEMORY_DIR": ConfigField(
                name="CREWAI_MEMORY_DIR",
                type=str,
                required=False,
                description="Directory for CrewAI memory storage"
            ),
            "INTERNAL_API_HOST": ConfigField(
                name="INTERNAL_API_HOST",
                type=str,
                required=False,
                description="Internal API host address"
            ),
            "INTERNAL_API_PORT": ConfigField(
                name="INTERNAL_API_PORT",
                type=int,
                required=False,
                validator=lambda x: 1 <= x <= 65535 if x else True,
                description="Internal API port"
            ),
            "EXTERNAL_API_HOST": ConfigField(
                name="EXTERNAL_API_HOST",
                type=str,
                required=False,
                description="External API host address"
            ),
            "EXTERNAL_API_PORT": ConfigField(
                name="EXTERNAL_API_PORT",
                type=int,
                required=False,
                validator=lambda x: 1 <= x <= 65535 if x else True,
                description="External API port"
            ),
            "SECRET_KEY": ConfigField(
                name="SECRET_KEY",
                type=str,
                required=False,
                sensitive=True,
                validator=lambda x: len(x) >= 32 if x else True,
                description="General secret key (minimum 32 characters)"
            ),
            "ACCESS_TOKEN_EXPIRE_MINUTES": ConfigField(
                name="ACCESS_TOKEN_EXPIRE_MINUTES",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="JWT access token expiration time (minutes)"
            ),
            
            # SSL Configuration (Optional)
            "SSL_CERTFILE": ConfigField(
                name="SSL_CERTFILE",
                type=str,
                required=False,
                description="Path to SSL certificate file"
            ),
            "SSL_KEYFILE": ConfigField(
                name="SSL_KEYFILE",
                type=str,
                required=False,
                description="Path to SSL private key file"
            ),
            
            # Redis Configuration (Optional)
            "REDIS_URL": ConfigField(
                name="REDIS_URL",
                type=str,
                required=False,
                description="Redis connection URL"
            ),
            "SCRAPER_SESSION_TTL": ConfigField(
                name="SCRAPER_SESSION_TTL",
                type=int,
                required=False,
                validator=lambda x: x > 0 if x else True,
                description="Scraper session TTL (seconds)"
            ),
            
            # Token Configuration (Optional)
            "JWT_SECRET_KEY": ConfigField(
                name="JWT_SECRET_KEY",
                type=str,
                required=False,
                sensitive=True,
                validator=lambda x: len(x) >= 32 if x else True,
                description="JWT secret key (minimum 32 characters, defaults to API_SECRET_KEY)"
            ),
            "JWT_ALGORITHM": ConfigField(
                name="JWT_ALGORITHM",
                type=str,
                required=False,
                validator=lambda x: x in ["HS256", "HS384", "HS512", "RS256"] if x else True,
                description="JWT signing algorithm"
            ),
            "TOKEN_DEFAULT_EXPIRY_HOURS": ConfigField(
                name="TOKEN_DEFAULT_EXPIRY_HOURS",
                type=int,
                required=False,
                environment_specific=True,
                validator=lambda x: 1 <= x <= 8760 if x else True,  # 1 hour to 1 year
                description="Default token expiration time in hours"
            ),
            "TOKEN_MAX_EXPIRY_HOURS": ConfigField(
                name="TOKEN_MAX_EXPIRY_HOURS",
                type=int,
                required=False,
                environment_specific=True,
                validator=lambda x: 1 <= x <= 8760 if x else True,  # 1 hour to 1 year
                description="Maximum allowed token expiration time in hours"
            ),
            "TOKEN_INTERNAL_EXPIRY_HOURS": ConfigField(
                name="TOKEN_INTERNAL_EXPIRY_HOURS",
                type=int,
                required=False,
                environment_specific=True,
                validator=lambda x: 1 <= x <= 8760 if x else True,  # 1 hour to 1 year
                description="Internal service token expiration time in hours"
            ),
            "TOKEN_AVAILABLE_SCOPES": ConfigField(
                name="TOKEN_AVAILABLE_SCOPES",
                type=str,
                required=False,
                environment_specific=True,
                description="Comma-separated list of available token scopes"
            ),
            "TOKEN_DEFAULT_SCOPES": ConfigField(
                name="TOKEN_DEFAULT_SCOPES",
                type=str,
                required=False,
                environment_specific=True,
                description="Comma-separated list of default token scopes"
            ),
            
            # Development/Debug Configuration (Optional)
            "VERBOSE": ConfigField(
                name="VERBOSE",
                type=bool,
                required=False,
                description="Enable verbose logging"
            ),
            "ENVIRONMENT": ConfigField(
                name="ENVIRONMENT",
                type=str,
                required=False,
                validator=lambda x: x in ["development", "staging", "production"] if x else True,
                description="Application environment"
            ),
        }
    
    def _define_environment_profiles(self) -> Dict[Environment, Dict[str, Any]]:
        """Define environment-specific configuration profiles."""
        return {
            Environment.DEVELOPMENT: {
                "CHROMA_URL": "http://localhost:8000",
                "CHROMA_HOST": "localhost",
                "CHROMA_PORT": 8000,
                "TOKEN_DEFAULT_EXPIRY_HOURS": 168,  # 1 week
                "TOKEN_MAX_EXPIRY_HOURS": 720,  # 30 days
                "TOKEN_INTERNAL_EXPIRY_HOURS": 168,  # 1 week
                "TOKEN_AVAILABLE_SCOPES": "sparkjar_internal,admin,user,read_only,crew_execute",
                "TOKEN_DEFAULT_SCOPES": "sparkjar_internal,admin,user",
            },
            Environment.STAGING: {
                "CHROMA_URL": "http://chroma-gjdq-staging.railway.internal:8000",
                "CHROMA_HOST": "chroma-gjdq-staging.railway.internal",
                "CHROMA_PORT": 8000,
                "TOKEN_DEFAULT_EXPIRY_HOURS": 24,  # 1 day
                "TOKEN_MAX_EXPIRY_HOURS": 72,  # 3 days
                "TOKEN_INTERNAL_EXPIRY_HOURS": 168,  # 1 week
                "TOKEN_AVAILABLE_SCOPES": "sparkjar_internal,user,read_only,crew_execute",
                "TOKEN_DEFAULT_SCOPES": "sparkjar_internal",
            },
            Environment.PRODUCTION: {
                "CHROMA_URL": "http://chroma-gjdq.railway.internal:8000",
                "CHROMA_HOST": "chroma-gjdq.railway.internal", 
                "CHROMA_PORT": 8000,
                "TOKEN_DEFAULT_EXPIRY_HOURS": 8,  # 8 hours
                "TOKEN_MAX_EXPIRY_HOURS": 24,  # 1 day
                "TOKEN_INTERNAL_EXPIRY_HOURS": 168,  # 1 week
                "TOKEN_AVAILABLE_SCOPES": "sparkjar_internal,user,read_only,crew_execute",
                "TOKEN_DEFAULT_SCOPES": "sparkjar_internal",
            }
        }
    
    def _convert_value(self, value: str, target_type: Type) -> Any:
        """Convert string environment variable to target type."""
        if target_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        elif target_type == str:
            return value
        else:
            raise ValueError(f"Unsupported type: {target_type}")
    
    def _get_environment_default(self, field_name: str) -> Any:
        """Get environment-specific default value for a field."""
        profile = self._environment_profiles.get(self.environment, {})
        return profile.get(field_name)
    
    def validate_config(self, fail_fast: bool = True) -> ValidationResult:
        """Validate all configuration variables.
        
        Args:
            fail_fast: If True, raise exception on validation failure
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        
        for field_name, field_def in self._config_fields.items():
            try:
                # Get value from environment
                env_value = os.getenv(field_name)
                
                # Use environment-specific default if available
                if env_value is None and field_def.environment_specific:
                    env_default = self._get_environment_default(field_name)
                    if env_default is not None:
                        env_value = str(env_default)
                
                # Check if required field is missing
                if field_def.required and env_value is None:
                    result.missing_required.append(field_name)
                    result.errors.append(f"Required environment variable {field_name} is missing")
                    continue
                
                # Use default if not provided and not required
                if env_value is None:
                    if field_def.default is not None:
                        continue  # Default will be used
                    else:
                        continue  # Optional field without default
                
                # Convert to target type
                try:
                    converted_value = self._convert_value(env_value, field_def.type)
                except (ValueError, TypeError) as e:
                    result.invalid_values.append(field_name)
                    result.errors.append(f"Invalid value for {field_name}: {e}")
                    continue
                
                # Run custom validator if provided
                if field_def.validator and not field_def.validator(converted_value):
                    result.invalid_values.append(field_name)
                    result.errors.append(f"Validation failed for {field_name}: {field_def.description}")
                    continue
                    
            except Exception as e:
                result.errors.append(f"Error validating {field_name}: {str(e)}")
        
        # Check for environment-specific warnings
        self._add_environment_warnings(result)
        
        # Set overall validation status
        result.is_valid = len(result.errors) == 0
        
        if fail_fast and not result.is_valid:
            error_msg = f"Configuration validation failed:\n" + "\n".join(result.errors)
            raise ConfigValidationError(error_msg)
        
        return result
    
    def _add_environment_warnings(self, result: ValidationResult) -> None:
        """Add environment-specific warnings."""
        if self.environment == Environment.DEVELOPMENT:
            # Check for production secrets in development
            api_secret = os.getenv("API_SECRET_KEY", "")
            if api_secret == "dev-secret-key-change-in-production-minimum-32-chars":
                result.warnings.append("Using default development API secret key")
        
        elif self.environment == Environment.PRODUCTION:
            # Check for development values in production
            if os.getenv("VERBOSE", "").lower() == "true":
                result.warnings.append("VERBOSE mode enabled in production")
            
            # Check for localhost URLs in production
            for field_name in ["CHROMA_URL", "EMBEDDINGS_API_URL", "MCP_REGISTRY_URL"]:
                value = os.getenv(field_name, "")
                if "localhost" in value:
                    result.warnings.append(f"{field_name} contains localhost in production")
    
    def get_config_summary(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Get a summary of current configuration.
        
        Args:
            include_sensitive: Whether to include sensitive values (masked)
            
        Returns:
            Dictionary with configuration summary
        """
        summary = {
            "environment": self.environment.value,
            "validation_status": "unknown",
            "fields": {}
        }
        
        try:
            validation_result = self.validate_config(fail_fast=False)
            summary["validation_status"] = "valid" if validation_result.is_valid else "invalid"
            summary["errors"] = validation_result.errors
            summary["warnings"] = validation_result.warnings
        except Exception as e:
            summary["validation_status"] = "error"
            summary["validation_error"] = str(e)
        
        for field_name, field_def in self._config_fields.items():
            env_value = os.getenv(field_name)
            
            if env_value is None and field_def.environment_specific:
                env_value = self._get_environment_default(field_name)
            
            if env_value is None and field_def.default is not None:
                env_value = field_def.default
            
            field_summary = {
                "value": "***MASKED***" if field_def.sensitive and include_sensitive else env_value,
                "set": env_value is not None,
                "required": field_def.required,
                "type": field_def.type.__name__,
                "description": field_def.description
            }
            
            if not field_def.sensitive or include_sensitive:
                field_summary["value"] = env_value
            
            summary["fields"][field_name] = field_summary
        
        return summary
    
    def generate_env_template(self, environment: Optional[Environment] = None) -> str:
        """Generate .env template file for specified environment.
        
        Args:
            environment: Target environment (defaults to current)
            
        Returns:
            String content for .env file
        """
        target_env = environment or self.environment
        profile = self._environment_profiles.get(target_env, {})
        
        lines = [
            f"# SparkJAR Crew Configuration - {target_env.value.upper()}",
            f"# Generated configuration template",
            "",
            f"ENVIRONMENT={target_env.value}",
            ""
        ]
        
        # Group fields by category
        categories = {
            "Core API": ["API_HOST", "API_PORT", "API_SECRET_KEY"],
            "Database": ["DATABASE_URL", "DATABASE_URL_DIRECT", "DATABASE_URL_POOLED"],
            "Supabase": ["SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_KEY"],
            "OpenAI": ["OPENAI_API_KEY", "OPENAI_API_URL"],
            "ChromaDB": ["CHROMA_URL", "CHROMA_HOST", "CHROMA_PORT", "CHROMA_SERVER_AUTHN_CREDENTIALS", "CHROMA_SERVER_AUTHN_PROVIDER"],
            "Embeddings": ["EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_DIMENSION", "OPENAI_EMBEDDING_MODEL", "OPENAI_EMBEDDING_DIMENSION", "EMBEDDINGS_API_URL", "EMBEDDINGS_API_KEY"],
            "MCP Registry": ["MCP_REGISTRY_ENABLED", "MCP_REGISTRY_URL", "MCP_REGISTRY_HEALTH_CHECK_INTERVAL", "MCP_REGISTRY_CACHE_TTL", "MCP_REGISTRY_UNHEALTHY_THRESHOLD", "MCP_REGISTRY_CLEANUP_INTERVAL", "MCP_SERVERS_CONFIG_PATH"],
            "External APIs": ["GOOGLE_API_KEY", "GOOGLE_CSE_ID", "GOOGLE_SEARCH_API_URL", "SERPER_API_KEY", "NVIDIA_NIM_API_KEY", "NVIDIA_OCR_ENDPOINT"],
            "Memory & Storage": ["CREWAI_MEMORY_DIR", "REDIS_URL", "SCRAPER_SESSION_TTL"],
            "Service Ports": ["INTERNAL_API_HOST", "INTERNAL_API_PORT", "EXTERNAL_API_HOST", "EXTERNAL_API_PORT"],
            "Security": ["SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES", "SSL_CERTFILE", "SSL_KEYFILE"],
            "Development": ["VERBOSE"]
        }
        
        for category, field_names in categories.items():
            lines.append(f"# {category}")
            for field_name in field_names:
                if field_name in self._config_fields:
                    field_def = self._config_fields[field_name]
                    
                    # Get value from profile or default
                    value = profile.get(field_name, field_def.default)
                    
                    # Format value
                    if value is None:
                        value_str = ""
                    elif isinstance(value, bool):
                        value_str = "true" if value else "false"
                    else:
                        value_str = str(value)
                    
                    # Add comment with description
                    if field_def.description:
                        lines.append(f"# {field_def.description}")
                    
                    # Add required/optional indicator
                    req_indicator = " # REQUIRED" if field_def.required else " # Optional"
                    
                    # Add the environment variable
                    if field_def.sensitive and value_str:
                        lines.append(f"{field_name}=your-{field_name.lower().replace('_', '-')}-here{req_indicator}")
                    else:
                        lines.append(f"{field_name}={value_str}{req_indicator}")
                    
                    lines.append("")
            lines.append("")
        
        return "\n".join(lines)


# Global validator instance
_validator: Optional[ConfigValidator] = None


def get_validator() -> ConfigValidator:
    """Get the global configuration validator instance."""
    global _validator
    if _validator is None:
        _validator = ConfigValidator()
    return _validator


def validate_config_on_startup(fail_fast: bool = True) -> ValidationResult:
    """Validate configuration on application startup.
    
    Args:
        fail_fast: If True, raise exception on validation failure
        
    Returns:
        ValidationResult with validation status
    """
    validator = get_validator()
    result = validator.validate_config(fail_fast=fail_fast)
    
    # Log validation results
    logger = logging.getLogger(__name__)
    
    if result.is_valid:
        logger.info(f"✅ Configuration validation passed for {validator.environment.value} environment")
        if result.warnings:
            for warning in result.warnings:
                logger.warning(f"⚠️  {warning}")
    else:
        logger.error(f"❌ Configuration validation failed for {validator.environment.value} environment")
        for error in result.errors:
            logger.error(f"  • {error}")
    
    return result


def get_config_summary(include_sensitive: bool = False) -> Dict[str, Any]:
    """Get configuration summary."""
    validator = get_validator()
    return validator.get_config_summary(include_sensitive=include_sensitive)


def generate_env_template(environment: str = "development") -> str:
    """Generate .env template for specified environment."""
    env = Environment(environment)
    validator = ConfigValidator(environment)
    return validator.generate_env_template(env)