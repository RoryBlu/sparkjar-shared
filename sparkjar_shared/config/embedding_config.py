"""
Centralized embedding model configuration management.
Provides single source of truth for embedding models using object_embeddings table.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from shared.database.models import ObjectEmbeddings

logger = logging.getLogger(__name__)

class EmbeddingProvider(Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    CUSTOM = "custom"

@dataclass
class EmbeddingModelConfig:
    """Configuration for an embedding model."""
    name: str
    provider: EmbeddingProvider
    dimension: int
    description: str
    max_tokens: int = 8192
    cost_per_1k_tokens: float = 0.0
    is_default: bool = False

class EmbeddingConfigManager:
    """
    Manages embedding model configuration with validation against object_embeddings table.
    Provides single source of truth for embedding models across all services.
    """
    
    # Supported embedding models configuration
    SUPPORTED_MODELS = {
        "text-embedding-3-small": EmbeddingModelConfig(
            name="text-embedding-3-small",
            provider=EmbeddingProvider.OPENAI,
            dimension=1536,
            description="OpenAI's latest small embedding model with high performance",
            max_tokens=8192,
            cost_per_1k_tokens=0.00002,
            is_default=True
        ),
        "text-embedding-ada-002": EmbeddingModelConfig(
            name="text-embedding-ada-002",
            provider=EmbeddingProvider.OPENAI,
            dimension=1536,
            description="OpenAI's previous generation embedding model",
            max_tokens=8192,
            cost_per_1k_tokens=0.0001
        ),
        "gte-multilingual-base": EmbeddingModelConfig(
            name="gte-multilingual-base",
            provider=EmbeddingProvider.CUSTOM,
            dimension=768,
            description="Alibaba's multilingual embedding model",
            max_tokens=512,
            cost_per_1k_tokens=0.0  # Self-hosted
        )
    }
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session
        self._load_environment_config()
    
    def _load_environment_config(self):
        """Load embedding configuration from environment variables."""
        # Primary embedding provider
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        
        # OpenAI configuration
        self.openai_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.openai_dimension = int(os.getenv("OPENAI_EMBEDDING_DIMENSION", "1536"))
        
        # Custom embedding configuration
        self.custom_model = os.getenv("EMBEDDING_MODEL", "gte-multilingual-base")
        self.custom_dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))
        
        # Environment-based defaults
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        logger.info(f"Loaded embedding config - Provider: {self.embedding_provider}")
    
    def get_current_model_config(self) -> EmbeddingModelConfig:
        """Get the current embedding model configuration based on environment."""
        if self.embedding_provider == "openai":
            model_name = self.openai_model
        else:
            model_name = self.custom_model
        
        if model_name not in self.SUPPORTED_MODELS:
            logger.warning(f"Unknown model {model_name}, falling back to default")
            model_name = "text-embedding-3-small"
        
        return self.SUPPORTED_MODELS[model_name]
    
    def get_model_config(self, model_name: str) -> Optional[EmbeddingModelConfig]:
        """Get configuration for a specific model."""
        return self.SUPPORTED_MODELS.get(model_name)
    
    def list_supported_models(self) -> List[EmbeddingModelConfig]:
        """List all supported embedding models."""
        return list(self.SUPPORTED_MODELS.values())
    
    def validate_model_dimension(self, model_name: str, dimension: int) -> bool:
        """Validate that a model name matches its expected dimension."""
        config = self.get_model_config(model_name)
        if not config:
            logger.error(f"Unknown embedding model: {model_name}")
            return False
        
        if config.dimension != dimension:
            logger.error(f"Dimension mismatch for {model_name}: expected {config.dimension}, got {dimension}")
            return False
        
        return True
    
    async def validate_consistency_with_database(self) -> Dict[str, any]:
        """
        Validate embedding model consistency against object_embeddings table.
        
        Returns:
            Dictionary with validation results and inconsistencies found
        """
        if not self.db:
            logger.warning("No database session provided, skipping database validation")
            return {"valid": True, "warnings": ["Database validation skipped - no session"]}
        
        try:
            # Get all unique model/dimension combinations from database
            query = select(
                distinct(ObjectEmbeddings.embedding_model),
                ObjectEmbeddings.embedding_dimension
            ).where(
                ObjectEmbeddings.embedding_model.isnot(None)
            )
            
            result = await self.db.execute(query)
            db_models = result.fetchall()
            
            validation_result = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "database_models": [],
                "unsupported_models": [],
                "dimension_mismatches": []
            }
            
            for model_name, dimension in db_models:
                validation_result["database_models"].append({
                    "model": model_name,
                    "dimension": dimension
                })
                
                # Check if model is supported
                config = self.get_model_config(model_name)
                if not config:
                    validation_result["unsupported_models"].append(model_name)
                    validation_result["errors"].append(f"Unsupported model in database: {model_name}")
                    validation_result["valid"] = False
                    continue
                
                # Check dimension consistency
                if config.dimension != dimension:
                    validation_result["dimension_mismatches"].append({
                        "model": model_name,
                        "expected_dimension": config.dimension,
                        "actual_dimension": dimension
                    })
                    validation_result["errors"].append(
                        f"Dimension mismatch for {model_name}: expected {config.dimension}, found {dimension}"
                    )
                    validation_result["valid"] = False
            
            # Check if current model is being used
            current_config = self.get_current_model_config()
            current_in_db = any(model_name == current_config.name for model_name, _ in db_models)
            
            if db_models and not current_in_db:
                validation_result["warnings"].append(
                    f"Current model {current_config.name} not found in database. "
                    "Consider running embedding generation for consistency."
                )
            
            # Log validation results
            if validation_result["valid"]:
                logger.info("✅ Embedding model consistency validation passed")
            else:
                logger.error("❌ Embedding model consistency validation failed")
                for error in validation_result["errors"]:
                    logger.error(f"  • {error}")
            
            for warning in validation_result["warnings"]:
                logger.warning(f"⚠️  {warning}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to validate embedding consistency: {e}")
            return {
                "valid": False,
                "errors": [f"Database validation failed: {str(e)}"],
                "warnings": [],
                "database_models": [],
                "unsupported_models": [],
                "dimension_mismatches": []
            }
    
    async def get_database_model_stats(self) -> Dict[str, any]:
        """Get statistics about embedding models used in the database."""
        if not self.db:
            return {"error": "No database session provided"}
        
        try:
            # Count embeddings by model
            query = select(
                ObjectEmbeddings.embedding_model,
                ObjectEmbeddings.embedding_dimension,
                func.count().label('count')
            ).group_by(
                ObjectEmbeddings.embedding_model,
                ObjectEmbeddings.embedding_dimension
            ).order_by(
                func.count().desc()
            )
            
            result = await self.db.execute(query)
            model_stats = result.fetchall()
            
            stats = {
                "total_embeddings": 0,
                "models": [],
                "current_model_usage": 0
            }
            
            current_config = self.get_current_model_config()
            
            for model_name, dimension, count in model_stats:
                stats["total_embeddings"] += count
                stats["models"].append({
                    "model": model_name,
                    "dimension": dimension,
                    "count": count,
                    "is_current": model_name == current_config.name
                })
                
                if model_name == current_config.name:
                    stats["current_model_usage"] = count
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database model stats: {e}")
            return {"error": str(e)}
    
    def get_environment_profile(self) -> Dict[str, any]:
        """Get embedding configuration profile for current environment."""
        current_config = self.get_current_model_config()
        
        profile = {
            "environment": self.environment,
            "provider": self.embedding_provider,
            "current_model": {
                "name": current_config.name,
                "provider": current_config.provider.value,
                "dimension": current_config.dimension,
                "description": current_config.description
            },
            "supported_models": [
                {
                    "name": config.name,
                    "provider": config.provider.value,
                    "dimension": config.dimension,
                    "is_default": config.is_default
                }
                for config in self.SUPPORTED_MODELS.values()
            ]
        }
        
        return profile

# Global instance for easy access
_embedding_config_manager = None

def get_embedding_config_manager(db_session: Optional[AsyncSession] = None) -> EmbeddingConfigManager:
    """Get the global embedding configuration manager instance."""
    global _embedding_config_manager
    
    if _embedding_config_manager is None or db_session is not None:
        _embedding_config_manager = EmbeddingConfigManager(db_session)
    
    return _embedding_config_manager

def validate_embedding_config() -> bool:
    """Validate embedding configuration without database access."""
    try:
        manager = get_embedding_config_manager()
        current_config = manager.get_current_model_config()
        
        logger.info(f"✅ Embedding configuration valid - Using {current_config.name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding configuration validation failed: {e}")
        return False