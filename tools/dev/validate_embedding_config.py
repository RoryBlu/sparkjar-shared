#!/usr/bin/env python3
"""
Validate embedding model configuration and consistency with object_embeddings table.
This script provides comprehensive validation for the embedding configuration system.
"""

import asyncio
import argparse
import sys
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from shared.config.embedding_config import get_embedding_config_manager, validate_embedding_config
from shared.config.shared_settings import DATABASE_URL_DIRECT, ENVIRONMENT

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

async def create_db_session() -> AsyncSession:
    """Create database session for validation."""
    try:
        engine = create_async_engine(DATABASE_URL_DIRECT, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return async_session()
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        raise

async def validate_embedding_consistency() -> Dict[str, Any]:
    """Validate embedding model consistency with database."""
    logger.info("🔍 Starting embedding configuration validation...")
    
    validation_results = {
        "config_validation": {"valid": False, "errors": []},
        "database_validation": {"valid": False, "errors": []},
        "consistency_validation": {"valid": False, "errors": []},
        "overall_valid": False
    }
    
    try:
        # 1. Validate basic embedding configuration
        logger.info("📋 Validating basic embedding configuration...")
        config_valid = validate_embedding_config()
        validation_results["config_validation"]["valid"] = config_valid
        
        if config_valid:
            logger.info("✅ Basic embedding configuration is valid")
        else:
            logger.error("❌ Basic embedding configuration is invalid")
            validation_results["config_validation"]["errors"].append("Basic configuration validation failed")
        
        # 2. Create database session and validate with database
        logger.info("🗄️  Connecting to database for consistency validation...")
        db_session = await create_db_session()
        
        try:
            # Get embedding config manager with database session
            manager = get_embedding_config_manager(db_session)
            
            # 3. Validate consistency with database
            logger.info("🔄 Validating consistency with object_embeddings table...")
            consistency_result = await manager.validate_consistency_with_database()
            validation_results["database_validation"] = consistency_result
            
            if consistency_result["valid"]:
                logger.info("✅ Database consistency validation passed")
            else:
                logger.error("❌ Database consistency validation failed")
                for error in consistency_result["errors"]:
                    logger.error(f"  • {error}")
            
            # 4. Get database statistics
            logger.info("📊 Getting database model statistics...")
            stats = await manager.get_database_model_stats()
            
            if "error" not in stats:
                logger.info(f"📈 Database statistics:")
                logger.info(f"  Total embeddings: {stats['total_embeddings']}")
                logger.info(f"  Current model usage: {stats['current_model_usage']}")
                logger.info(f"  Models in database:")
                for model_info in stats["models"]:
                    current_indicator = " (CURRENT)" if model_info["is_current"] else ""
                    logger.info(f"    - {model_info['model']} ({model_info['dimension']}d): {model_info['count']} embeddings{current_indicator}")
            else:
                logger.warning(f"⚠️  Could not get database statistics: {stats['error']}")
            
            # 5. Get environment profile
            logger.info("🌍 Current environment profile:")
            profile = manager.get_environment_profile()
            logger.info(f"  Environment: {profile['environment']}")
            logger.info(f"  Provider: {profile['provider']}")
            logger.info(f"  Current model: {profile['current_model']['name']} ({profile['current_model']['dimension']}d)")
            logger.info(f"  Supported models: {len(profile['supported_models'])}")
            
        finally:
            await db_session.close()
        
        # 6. Overall validation result
        validation_results["overall_valid"] = (
            validation_results["config_validation"]["valid"] and 
            validation_results["database_validation"]["valid"]
        )
        
        if validation_results["overall_valid"]:
            logger.info("🎉 Overall embedding configuration validation PASSED")
        else:
            logger.error("💥 Overall embedding configuration validation FAILED")
        
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ Validation failed with exception: {e}")
        validation_results["consistency_validation"]["errors"].append(str(e))
        return validation_results

async def show_embedding_profile():
    """Show current embedding configuration profile."""
    logger.info("📋 Current Embedding Configuration Profile")
    logger.info("=" * 50)
    
    try:
        manager = get_embedding_config_manager()
        
        # Current model configuration
        current_config = manager.get_current_model_config()
        logger.info(f"Current Model: {current_config.name}")
        logger.info(f"Provider: {current_config.provider.value}")
        logger.info(f"Dimension: {current_config.dimension}")
        logger.info(f"Description: {current_config.description}")
        logger.info(f"Max Tokens: {current_config.max_tokens}")
        logger.info(f"Cost per 1K tokens: ${current_config.cost_per_1k_tokens}")
        logger.info("")
        
        # Environment profile
        profile = manager.get_environment_profile()
        logger.info(f"Environment: {profile['environment']}")
        logger.info(f"Provider Setting: {profile['provider']}")
        logger.info("")
        
        # Supported models
        logger.info("Supported Models:")
        for model in profile['supported_models']:
            default_indicator = " (DEFAULT)" if model['is_default'] else ""
            logger.info(f"  - {model['name']} ({model['provider']}, {model['dimension']}d){default_indicator}")
        
    except Exception as e:
        logger.error(f"Failed to show embedding profile: {e}")

async def validate_model_dimension(model_name: str, dimension: int):
    """Validate a specific model and dimension combination."""
    logger.info(f"🔍 Validating model '{model_name}' with dimension {dimension}")
    
    try:
        manager = get_embedding_config_manager()
        is_valid = manager.validate_model_dimension(model_name, dimension)
        
        if is_valid:
            logger.info(f"✅ Model '{model_name}' with dimension {dimension} is valid")
        else:
            logger.error(f"❌ Model '{model_name}' with dimension {dimension} is invalid")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Failed to validate model dimension: {e}")
        return False

def main():
    """Command-line interface for embedding validation."""
    parser = argparse.ArgumentParser(description="Validate embedding configuration and consistency")
    parser.add_argument("--profile", action="store_true", help="Show current embedding profile")
    parser.add_argument("--validate-model", help="Validate specific model name")
    parser.add_argument("--validate-dimension", type=int, help="Validate specific dimension (use with --validate-model)")
    parser.add_argument("--full-validation", action="store_true", help="Run full validation including database consistency")
    parser.add_argument("--config-only", action="store_true", help="Validate configuration only (no database)")
    
    args = parser.parse_args()
    
    try:
        if args.profile:
            asyncio.run(show_embedding_profile())
            return
        
        if args.validate_model:
            dimension = args.validate_dimension or 1536  # Default to OpenAI dimension
            result = asyncio.run(validate_model_dimension(args.validate_model, dimension))
            sys.exit(0 if result else 1)
        
        if args.config_only:
            logger.info("🔍 Running configuration-only validation...")
            result = validate_embedding_config()
            if result:
                logger.info("✅ Configuration validation passed")
                sys.exit(0)
            else:
                logger.error("❌ Configuration validation failed")
                sys.exit(1)
        
        # Default: run full validation
        if args.full_validation or not any([args.profile, args.validate_model, args.config_only]):
            logger.info("🔍 Running full embedding validation...")
            results = asyncio.run(validate_embedding_consistency())
            
            if results["overall_valid"]:
                logger.info("🎉 All validations passed!")
                sys.exit(0)
            else:
                logger.error("💥 Validation failed!")
                sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()