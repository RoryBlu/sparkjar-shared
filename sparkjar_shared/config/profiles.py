"""
Environment-specific configuration profiles for SparkJAR Crew
"""

from typing import Dict, Any
from .config_validator import Environment


class ConfigProfiles:
    """Manages environment-specific configuration profiles."""
    
    @staticmethod
    def get_profile(environment: Environment) -> Dict[str, Any]:
        """Get configuration profile for specified environment."""
        profiles = {
            Environment.DEVELOPMENT: {
                # Development-specific overrides
                "API_SECRET_KEY": "dev-secret-key-change-in-production-minimum-32-chars",
                "CHROMA_URL": "http://localhost:8000",
                "CHROMA_HOST": "localhost",
                "EMBEDDINGS_API_URL": "https://embeddings-development.up.railway.app",
                "MCP_REGISTRY_URL": "http://localhost:8001",
                "VERBOSE": "true",
                "ENVIRONMENT": "development",
                
                # Development database defaults
                "DATABASE_URL_DIRECT": "postgresql+asyncpg://user:password@localhost:5432/sparkjar_crew_dev",
                "DATABASE_URL_POOLED": "postgresql+asyncpg://user:password@localhost:6543/sparkjar_crew_dev",
                
                # Relaxed validation for development
                "MCP_REGISTRY_HEALTH_CHECK_INTERVAL": "30",
                "MCP_REGISTRY_CACHE_TTL": "60",
            },
            
            Environment.STAGING: {
                # Staging-specific configuration
                "CHROMA_URL": "http://chroma-gjdq-staging.railway.internal:8000",
                "CHROMA_HOST": "chroma-gjdq-staging.railway.internal",
                "EMBEDDINGS_API_URL": "https://embeddings-staging.up.railway.app",
                "MCP_REGISTRY_URL": "https://mcp-registry-staging.up.railway.app",
                "VERBOSE": "false",
                "ENVIRONMENT": "staging",
                
                # Staging database configuration
                "DATABASE_URL_DIRECT": "postgresql+asyncpg://staging_user:staging_pass@staging_host:5432/sparkjar_crew_staging",
                "DATABASE_URL_POOLED": "postgresql+asyncpg://staging_user:staging_pass@staging_host:6543/sparkjar_crew_staging",
                
                # Staging-specific timeouts
                "MCP_REGISTRY_HEALTH_CHECK_INTERVAL": "45",
                "MCP_REGISTRY_CACHE_TTL": "180",
            },
            
            Environment.PRODUCTION: {
                # Production configuration
                "CHROMA_URL": "http://chroma-gjdq.railway.internal:8000",
                "CHROMA_HOST": "chroma-gjdq.railway.internal",
                "EMBEDDINGS_API_URL": "https://embeddings-api-production.up.railway.app",
                "MCP_REGISTRY_URL": "https://mcp-registry-production.up.railway.app",
                "VERBOSE": "false",
                "ENVIRONMENT": "production",
                
                # Production database configuration (will be overridden by actual env vars)
                "DATABASE_URL_DIRECT": "postgresql+asyncpg://prod_user:prod_pass@prod_host:5432/sparkjar_crew",
                "DATABASE_URL_POOLED": "postgresql+asyncpg://prod_user:prod_pass@prod_host:6543/sparkjar_crew",
                
                # Production timeouts
                "MCP_REGISTRY_HEALTH_CHECK_INTERVAL": "60",
                "MCP_REGISTRY_CACHE_TTL": "300",
                "MCP_REGISTRY_UNHEALTHY_THRESHOLD": "3",
                "MCP_REGISTRY_CLEANUP_INTERVAL": "300",
                
                # Production security settings
                "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
                "SCRAPER_SESSION_TTL": "300",
            }
        }
        
        return profiles.get(environment, {})
    
    @staticmethod
    def get_required_vars_by_environment(environment: Environment) -> Dict[str, bool]:
        """Get environment-specific required variables."""
        base_required = {
            "OPENAI_API_KEY": True,
            "DATABASE_URL_DIRECT": True,
            "DATABASE_URL_POOLED": True,
            "API_SECRET_KEY": True,
        }
        
        environment_specific = {
            Environment.DEVELOPMENT: {
                # More lenient requirements for development
                "CHROMA_SERVER_AUTHN_CREDENTIALS": False,
                "EMBEDDINGS_API_KEY": False,
                "SUPABASE_URL": False,
                "SUPABASE_SECRET_KEY": False,
            },
            
            Environment.STAGING: {
                # Staging requirements
                "CHROMA_SERVER_AUTHN_CREDENTIALS": True,
                "EMBEDDINGS_API_KEY": False,
                "SUPABASE_URL": False,
                "SUPABASE_SECRET_KEY": False,
            },
            
            Environment.PRODUCTION: {
                # Strict requirements for production
                "CHROMA_SERVER_AUTHN_CREDENTIALS": True,
                "EMBEDDINGS_API_KEY": True,
                "SUPABASE_URL": True,
                "SUPABASE_SECRET_KEY": True,
                "SECRET_KEY": True,
            }
        }
        
        # Merge base requirements with environment-specific ones
        result = base_required.copy()
        result.update(environment_specific.get(environment, {}))
        return result
    
    @staticmethod
    def validate_environment_specific_config(environment: Environment) -> Dict[str, Any]:
        """Validate environment-specific configuration requirements."""
        import os
        
        validation_result = {
            "environment": environment.value,
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        required_vars = ConfigProfiles.get_required_vars_by_environment(environment)
        
        for var_name, is_required in required_vars.items():
            value = os.getenv(var_name)
            
            if is_required and not value:
                validation_result["errors"].append(f"Required variable {var_name} is missing for {environment.value} environment")
                validation_result["valid"] = False
            elif not is_required and not value:
                validation_result["warnings"].append(f"Optional variable {var_name} is not set for {environment.value} environment")
        
        # Environment-specific validations
        if environment == Environment.PRODUCTION:
            # Check for development values in production
            api_secret = os.getenv("API_SECRET_KEY", "")
            if "dev-secret" in api_secret.lower():
                validation_result["errors"].append("Development API secret key detected in production environment")
                validation_result["valid"] = False
            
            # Check for localhost URLs
            for url_var in ["CHROMA_URL", "EMBEDDINGS_API_URL", "MCP_REGISTRY_URL"]:
                url_value = os.getenv(url_var, "")
                if "localhost" in url_value:
                    validation_result["errors"].append(f"{url_var} contains localhost in production environment")
                    validation_result["valid"] = False
        
        elif environment == Environment.DEVELOPMENT:
            # Check for production URLs in development
            chroma_url = os.getenv("CHROMA_URL", "")
            if "railway.internal" in chroma_url:
                validation_result["warnings"].append("Production ChromaDB URL detected in development environment")
        
        return validation_result


def get_environment_config(environment_name: str = None) -> Dict[str, Any]:
    """Get configuration for specified environment."""
    import os
    
    if environment_name is None:
        environment_name = os.getenv("ENVIRONMENT", "development")
    
    try:
        environment = Environment(environment_name)
        return ConfigProfiles.get_profile(environment)
    except ValueError:
        # Invalid environment name, return empty dict
        return {}


def validate_current_environment() -> Dict[str, Any]:
    """Validate configuration for current environment."""
    import os
    
    environment_name = os.getenv("ENVIRONMENT", "development")
    
    try:
        environment = Environment(environment_name)
        return ConfigProfiles.validate_environment_specific_config(environment)
    except ValueError:
        return {
            "environment": environment_name,
            "valid": False,
            "errors": [f"Invalid environment name: {environment_name}"],
            "warnings": []
        }