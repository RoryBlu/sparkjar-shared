"""SparkJAR Shared Utilities Package"""

# Logging utilities
from .crew_logger import CrewLogger
from .enhanced_crew_logger import EnhancedCrewLogger
from .simple_crew_logger import SimpleCrewLogger
from .standalone_logger import StandaloneLogger

# Client utilities
from .chroma_client import ChromaClient
from .embedding_client import EmbeddingClient
from .ocr_client import OCRClient

# Other utilities
from .secret_manager import SecretManager
from .google_search import GoogleSearchTool
from .crew_config_admin import CrewConfigAdmin

# Re-export existing utilities
from .logging_config import setup_logging
from .retry_utils import retry_with_backoff
from .vector_search import search_vectors

__all__ = [
    # Logging
    "CrewLogger",
    "EnhancedCrewLogger",
    "SimpleCrewLogger",
    "StandaloneLogger",
    "setup_logging",
    
    # Clients
    "ChromaClient",
    "EmbeddingClient",
    "OCRClient",
    
    # Other
    "SecretManager",
    "GoogleSearchTool",
    "CrewConfigAdmin",
    "retry_with_backoff",
    "search_vectors",
]
