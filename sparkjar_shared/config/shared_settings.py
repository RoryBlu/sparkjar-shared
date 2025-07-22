"""
SparkJAR Crew Configuration
Vanilla CrewAI with OpenAI and MCP support
"""

from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Import configuration validator for startup validation
from .config_validator import validate_config_on_startup, get_config_summary

# OpenAI Configuration (Native CrewAI Support)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Supabase Database (Multi-tenant) - Two connection types
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

# Direct connection (Port 5432) - For admin, migrations, schema changes, development
DATABASE_URL_DIRECT = os.getenv(
    "DATABASE_URL_DIRECT",
    "postgresql+asyncpg://user:password@localhost:5432/sparkjar_crew",
)

# Pooled connection (Port 6543) - For production API, high-concurrency operations
DATABASE_URL_POOLED = os.getenv(
    "DATABASE_URL_POOLED",
    "postgresql+asyncpg://user:password@localhost:6543/sparkjar_crew",
)

# Default DATABASE_URL (backwards compatibility) - defaults to direct connection
DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL_DIRECT)

# ChromaDB for Real-time RAG (Railway)
# Default to Railway internal service for production
CHROMA_URL = os.getenv("CHROMA_URL", "http://chroma-gjdq.railway.internal:8000")
CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma-gjdq.railway.internal")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_SERVER_AUTHN_CREDENTIALS = os.getenv("CHROMA_SERVER_AUTHN_CREDENTIALS")
CHROMA_SERVER_AUTHN_PROVIDER = os.getenv(
    "CHROMA_SERVER_AUTHN_PROVIDER",
    "chromadb.auth.token_authn.TokenAuthenticationServerProvider",
)

# CrewAI Memory Storage (SQLite files for agent memory)
CREWAI_MEMORY_DIR = os.getenv("CREWAI_MEMORY_DIR", "./local_crew_memory")

# Embeddings Service (Railway)
EMBEDDINGS_API_URL = os.getenv(
    "EMBEDDINGS_API_URL", "https://embeddings-api-production.up.railway.app"
)
EMBEDDINGS_API_KEY = os.getenv("EMBEDDINGS_API_KEY")

# MCP Servers (Railway)
MCP_SERVERS_CONFIG_PATH = os.getenv("MCP_SERVERS_CONFIG_PATH", "mcp_servers.json")
MCP_REGISTRY_URL = os.getenv(
    "MCP_REGISTRY_URL", "https://mcp-registry-production.up.railway.app"
)

# MCP Registry Configuration
MCP_REGISTRY_ENABLED = os.getenv("MCP_REGISTRY_ENABLED", "true").lower() == "true"
MCP_REGISTRY_HEALTH_CHECK_INTERVAL = int(
    os.getenv("MCP_REGISTRY_HEALTH_CHECK_INTERVAL", "60")
)
MCP_REGISTRY_CACHE_TTL = int(os.getenv("MCP_REGISTRY_CACHE_TTL", "300"))
MCP_REGISTRY_UNHEALTHY_THRESHOLD = int(
    os.getenv("MCP_REGISTRY_UNHEALTHY_THRESHOLD", "3")
)
MCP_REGISTRY_CLEANUP_INTERVAL = int(os.getenv("MCP_REGISTRY_CLEANUP_INTERVAL", "300"))

# FastAPI Settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Token Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", API_SECRET_KEY)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Environment-based token settings
TOKEN_DEFAULT_EXPIRY_HOURS = int(os.getenv("TOKEN_DEFAULT_EXPIRY_HOURS", "24"))
TOKEN_MAX_EXPIRY_HOURS = int(os.getenv("TOKEN_MAX_EXPIRY_HOURS", "168"))  # 1 week
TOKEN_INTERNAL_EXPIRY_HOURS = int(os.getenv("TOKEN_INTERNAL_EXPIRY_HOURS", "168"))  # 1 week for internal services

# Scope configuration
TOKEN_AVAILABLE_SCOPES = os.getenv("TOKEN_AVAILABLE_SCOPES", "sparkjar_internal,admin,user,read_only,crew_execute").split(",")
TOKEN_DEFAULT_SCOPES = os.getenv("TOKEN_DEFAULT_SCOPES", "sparkjar_internal").split(",")

# Environment-specific token restrictions
if ENVIRONMENT == "production":
    TOKEN_DEFAULT_EXPIRY_HOURS = int(os.getenv("TOKEN_DEFAULT_EXPIRY_HOURS", "8"))  # 8 hours in production
    TOKEN_MAX_EXPIRY_HOURS = int(os.getenv("TOKEN_MAX_EXPIRY_HOURS", "24"))  # 1 day max in production
    TOKEN_DEFAULT_SCOPES = os.getenv("TOKEN_DEFAULT_SCOPES", "sparkjar_internal").split(",")
elif ENVIRONMENT == "staging":
    TOKEN_DEFAULT_EXPIRY_HOURS = int(os.getenv("TOKEN_DEFAULT_EXPIRY_HOURS", "24"))  # 1 day in staging
    TOKEN_MAX_EXPIRY_HOURS = int(os.getenv("TOKEN_MAX_EXPIRY_HOURS", "72"))  # 3 days max in staging
elif ENVIRONMENT == "development":
    TOKEN_DEFAULT_EXPIRY_HOURS = int(os.getenv("TOKEN_DEFAULT_EXPIRY_HOURS", "168"))  # 1 week in development
    TOKEN_MAX_EXPIRY_HOURS = int(os.getenv("TOKEN_MAX_EXPIRY_HOURS", "720"))  # 30 days max in development
    TOKEN_DEFAULT_SCOPES = os.getenv("TOKEN_DEFAULT_SCOPES", "sparkjar_internal,admin,user").split(",")

# CrewAI Configuration (Vanilla OpenAI)
CREWAI_CONFIG = {
    "default_llm": "gpt-4o",  # CrewAI will use OpenAI by default
    "max_concurrent_jobs": 10,
    "job_timeout": 300,  # 5 minutes
}

# Embedding Configuration
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "custom")  # "custom" or "openai"

# OpenAI Embeddings Configuration
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_EMBEDDING_DIMENSION = int(os.getenv("OPENAI_EMBEDDING_DIMENSION", "1536"))

# Custom Embeddings Configuration  
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "Alibaba-NLP/gte-multilingual-base")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))



# Optional configuration
OPTIONAL_CONFIG = {
    "supabase_enabled": bool(SUPABASE_URL and SUPABASE_SECRET_KEY),
    "chroma_enabled": bool(CHROMA_URL),
    "mcp_enabled": (
        os.path.exists(MCP_SERVERS_CONFIG_PATH) if MCP_SERVERS_CONFIG_PATH else False
    ),
}

# Startup validation and configuration summary
def run_startup_validation(fail_fast: bool = True) -> bool:
    """Run comprehensive startup validation."""
    try:
        # Run centralized validation
        result = validate_config_on_startup(fail_fast=False)
        
        # Run environment-specific validation
        from .profiles import validate_current_environment
        env_result = validate_current_environment()
        
        # Setup logging for validation results
        if ENVIRONMENT == "development":
            logging.basicConfig(level=logging.INFO)
        
        logger = logging.getLogger(__name__)
        logger.info("🚀 SparkJAR Crew Configuration Validation")
        logger.info(f"Environment: {ENVIRONMENT}")
        
        # Log centralized validation results
        if result.is_valid:
            logger.info("✅ Core configuration validation passed")
        else:
            logger.error("❌ Core configuration validation failed")
            for error in result.errors:
                logger.error(f"  • {error}")
        
        # Log environment-specific validation results
        if env_result["valid"]:
            logger.info(f"✅ {ENVIRONMENT} environment validation passed")
        else:
            logger.error(f"❌ {ENVIRONMENT} environment validation failed")
            for error in env_result["errors"]:
                logger.error(f"  • {error}")
        
        # Log warnings
        all_warnings = result.warnings + env_result["warnings"]
        for warning in all_warnings:
            logger.warning(f"⚠️  {warning}")
        
        # Log service status
        logger.info(f"OpenAI API Key: {'✅ Set' if OPENAI_API_KEY else '❌ Missing'}")
        logger.info(f"Database Direct URL: {'✅ Set' if DATABASE_URL_DIRECT else '❌ Missing'}")
        logger.info(f"Database Pooled URL: {'✅ Set' if DATABASE_URL_POOLED else '❌ Missing'}")
        logger.info(f"Supabase: {'✅ Enabled' if OPTIONAL_CONFIG['supabase_enabled'] else '⚠️ Disabled'}")
        logger.info(f"ChromaDB: {'✅ Enabled' if OPTIONAL_CONFIG['chroma_enabled'] else '⚠️ Disabled'}")
        logger.info(f"MCP: {'✅ Enabled' if OPTIONAL_CONFIG['mcp_enabled'] else '⚠️ Disabled'}")
        
        # Determine overall validation status
        overall_valid = result.is_valid and env_result["valid"]
        
        if fail_fast and not overall_valid:
            all_errors = result.errors + env_result["errors"]
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(all_errors))
        
        return overall_valid
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Configuration validation error: {str(e)}")
        if fail_fast:
            raise
        return False

# Enhanced validation function for backward compatibility
def validate_config() -> bool:
    """Validate required configuration variables using centralized validator."""
    return run_startup_validation(fail_fast=True)

# Run startup validation on import (can be disabled by setting SKIP_CONFIG_VALIDATION=true)
if not os.getenv("SKIP_CONFIG_VALIDATION", "").lower() == "true":
    try:
        run_startup_validation(fail_fast=True)
    except Exception as e:
        # In development, log the error but don't fail
        if ENVIRONMENT == "development":
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️  Configuration validation failed (continuing in development mode): {str(e)}")
        else:
            # In staging/production, fail fast
            raise
