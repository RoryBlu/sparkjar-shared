"""
Admin tools for validating and managing CrewAI configurations.
Ensures all JSON configurations conform to schemas before database insertion.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from database.connection import get_direct_session
from database.crew_config_model import CrewConfig
from database.models import ObjectSchema
from services.json_validator import validate_json_against_schema
from sqlalchemy import select

logger = logging.getLogger(__name__)

class CrewConfigAdmin:
    """
    Admin interface for managing crew configurations with schema validation.
    """
    
    async def validate_and_insert_config(
        self, 
        name: str, 
        config_type: str, 
        config_data: Dict[str, Any],
        schema_name: str,
        description: Optional[str] = None,
        version: str = "1.0"
    ) -> str:
        """
        Validate and insert a crew configuration.
        
        Args:
            name: Unique name for the configuration
            config_type: Type of config ('agent', 'task', 'crew')
            config_data: The configuration JSON data
            schema_name: Name of the schema to validate against
            description: Optional description
            version: Configuration version
            
        Returns:
            Configuration ID if successful
            
        Raises:
            ValueError: If validation fails or configuration already exists
        """
        logger.info(f"Validating and inserting {config_type} config: {name}")
        
        # Check if configuration already exists
        existing = await self._get_config(name, config_type)
        if existing:
            raise ValueError(f"Configuration '{name}' of type '{config_type}' already exists")
        
        # Validate against schema
        validation_result = await self._validate_config(config_data, schema_name)
        if not validation_result["valid"]:
            error_msg = "; ".join(validation_result["errors"])
            raise ValueError(f"Schema validation failed: {error_msg}")
        
        # Insert into database
        config_id = await self._insert_config(
            name=name,
            config_type=config_type,
            config_data=config_data,
            schema_name=schema_name,
            description=description,
            version=version
        )
        
        logger.info(f"Successfully inserted config '{name}' with ID: {config_id}")
        return config_id
    
    async def update_config(
        self,
        name: str,
        config_type: str,
        config_data: Dict[str, Any],
        schema_name: Optional[str] = None
    ) -> bool:
        """
        Update an existing configuration after validation.
        
        Args:
            name: Name of the configuration to update
            config_type: Type of configuration
            config_data: New configuration data
            schema_name: Schema to validate against (optional, uses existing if not provided)
            
        Returns:
            True if update successful
            
        Raises:
            ValueError: If validation fails or configuration not found
        """
        logger.info(f"Updating {config_type} config: {name}")
        
        # Get existing configuration
        existing = await self._get_config(name, config_type)
        if not existing:
            raise ValueError(f"Configuration '{name}' of type '{config_type}' not found")
        
        # Use existing schema if not provided
        if not schema_name:
            schema_name = existing.schema_name
        
        # Validate against schema
        validation_result = await self._validate_config(config_data, schema_name)
        if not validation_result["valid"]:
            error_msg = "; ".join(validation_result["errors"])
            raise ValueError(f"Schema validation failed: {error_msg}")
        
        # Update in database
        async with get_direct_session() as session:
            existing.config_data = config_data
            existing.schema_name = schema_name
            await session.commit()
        
        logger.info(f"Successfully updated config '{name}'")
        return True
    
    async def validate_config_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Validate a JSON configuration file against its schema.
        
        Args:
            file_path: Path to the JSON configuration file
            
        Returns:
            Validation result dictionary
        """
        if not file_path.exists():
            return {"valid": False, "errors": [f"File not found: {file_path}"]}
        
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            return {"valid": False, "errors": [f"Invalid JSON: {e}"]}
        
        # Extract schema name from config or filename
        schema_name = config_data.get("schema_name") or file_path.stem
        
        return await self._validate_config(config_data, schema_name)
    
    async def list_configs(
        self, 
        config_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all configurations, optionally filtered by type.
        
        Args:
            config_type: Optional filter by configuration type
            
        Returns:
            List of configuration summaries
        """
        async with get_direct_session() as session:
            query = select(CrewConfig)
            if config_type:
                query = query.where(CrewConfig.config_type == config_type)
            
            result = await session.execute(query.order_by(CrewConfig.name))
            configs = result.scalars().all()
            
            return [
                {
                    "id": str(config.id),
                    "name": config.name,
                    "config_type": config.config_type,
                    "schema_name": config.schema_name,
                    "version": config.version,
                    "description": config.description,
                    "created_at": config.created_at.isoformat(),
                    "updated_at": config.updated_at.isoformat()
                }
                for config in configs
            ]
    
    async def _get_config(self, name: str, config_type: str) -> Optional[CrewConfig]:
        """Get a configuration by name and type."""
        async with get_direct_session() as session:
            result = await session.execute(
                select(CrewConfig)
                .where(CrewConfig.name == name)
                .where(CrewConfig.config_type == config_type)
            )
            return result.scalar_one_or_none()
    
    async def _validate_config(self, config_data: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
        """Validate configuration data against schema."""
        try:
            return await validate_json_against_schema(config_data, schema_name)
        except Exception as e:
            return {"valid": False, "errors": [f"Validation error: {str(e)}"]}
    
    async def _insert_config(
        self,
        name: str,
        config_type: str,
        config_data: Dict[str, Any],
        schema_name: str,
        description: Optional[str] = None,
        version: str = "1.0"
    ) -> str:
        """Insert a new configuration into the database."""
        async with get_direct_session() as session:
            config = CrewConfig(
                name=name,
                config_type=config_type,
                config_data=config_data,
                schema_name=schema_name,
                description=description,
                version=version
            )
            
            session.add(config)
            await session.commit()
            
            return str(config.id)

# Convenience functions
async def validate_and_insert_config(**kwargs) -> str:
    """Convenience function for validating and inserting configurations."""
    admin = CrewConfigAdmin()
    return await admin.validate_and_insert_config(**kwargs)

async def validate_config_directory(configs_dir: Path) -> Dict[str, Any]:
    """
    Validate all JSON files in a directory.
    
    Args:
        configs_dir: Directory containing JSON configuration files
        
    Returns:
        Summary of validation results
    """
    admin = CrewConfigAdmin()
    results = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "errors": []
    }
    
    if not configs_dir.exists():
        results["errors"].append(f"Directory not found: {configs_dir}")
        return results
    
    for json_file in configs_dir.glob("*.json"):
        results["total"] += 1
        validation_result = await admin.validate_config_file(json_file)
        
        if validation_result["valid"]:
            results["valid"] += 1
            logger.info(f"✅ {json_file.name}: Valid")
        else:
            results["invalid"] += 1
            error_msg = f"❌ {json_file.name}: {'; '.join(validation_result['errors'])}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
    
    return results

if __name__ == "__main__":
    # CLI interface for admin operations
    import sys
    
    async def main():
        if len(sys.argv) < 2:
            logger.info("Usage: python crew_config_admin.py <command> [args...]")
            logger.info("Commands:")
            logger.info("  validate-dir <directory>  - Validate all JSON files in directory")
            logger.info("  list [type]               - List configurations")
            return
        
        command = sys.argv[1]
        admin = CrewConfigAdmin()
        
        if command == "validate-dir":
            if len(sys.argv) < 3:
                logger.info("Usage: validate-dir <directory>")
                return
            
            configs_dir = Path(sys.argv[2])
            results = await validate_config_directory(configs_dir)
            
            logger.info(f"Validation Results:")
            logger.info(f"  Total files: {results['total']}")
            logger.info(f"  Valid: {results['valid']}")
            logger.info(f"  Invalid: {results['invalid']}")
            
            if results["errors"]:
                logger.error("\nErrors:")
                for error in results["errors"]:
                    logger.error(f"  {error}")
        
        elif command == "list":
            config_type = sys.argv[2] if len(sys.argv) > 2 else None
            configs = await admin.list_configs(config_type)
            
            logger.info(f"Configurations ({len(configs)}):")
            for config in configs:
                logger.info(f"  {config['name']} ({config['config_type']}) - {config['description'] or 'No description'}")
        
        else:
            logger.info(f"Unknown command: {command}")
    
    asyncio.run(main())