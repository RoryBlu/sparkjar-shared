"""
Startup Configuration Validator
Provides a simple interface for services to validate configuration on startup
"""

import os
import sys
import logging
from typing import Dict, Any, Optional
from pathlib import Path

# Imports from shared modules are handled by proper Python packaging

from sparkjar_shared.config.config_validator import validate_config_on_startup, ConfigValidationError
from sparkjar_shared.config.profiles import validate_current_environment


class StartupValidator:
    """Handles configuration validation during service startup."""
    
    def __init__(self, service_name: str, logger: Optional[logging.Logger] = None):
        """Initialize startup validator for a specific service.
        
        Args:
            service_name: Name of the service (for logging)
            logger: Optional logger instance
        """
        self.service_name = service_name
        self.logger = logger or logging.getLogger(f"{service_name}.config")
        self.environment = os.getenv("ENVIRONMENT", "development")
    
    def validate_and_exit_on_failure(self, additional_checks: Optional[Dict[str, Any]] = None) -> None:
        """Validate configuration and exit process if validation fails.
        
        Args:
            additional_checks: Optional service-specific validation checks
        """
        try:
            is_valid = self.validate_configuration(additional_checks)
            if not is_valid:
                self.logger.error(f"❌ {self.service_name} configuration validation failed")
                sys.exit(1)
        except ConfigValidationError as e:
            self.logger.error(f"❌ {self.service_name} configuration validation failed: {str(e)}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"❌ {self.service_name} configuration validation error: {str(e)}")
            sys.exit(1)
    
    def validate_configuration(self, additional_checks: Optional[Dict[str, Any]] = None) -> bool:
        """Validate configuration and return success status.
        
        Args:
            additional_checks: Optional service-specific validation checks
            
        Returns:
            True if validation passes, False otherwise
        """
        self.logger.info(f"🔍 Validating {self.service_name} configuration...")
        self.logger.info(f"Environment: {self.environment}")
        
        validation_results = []
        
        # Run centralized validation
        try:
            result = validate_config_on_startup(fail_fast=False)
            validation_results.append(("Core Configuration", result.is_valid, result.errors, result.warnings))
            
            if result.is_valid:
                self.logger.info("✅ Core configuration validation passed")
            else:
                self.logger.error("❌ Core configuration validation failed")
                for error in result.errors:
                    self.logger.error(f"  • {error}")
            
            # Log warnings
            for warning in result.warnings:
                self.logger.warning(f"⚠️  {warning}")
                
        except Exception as e:
            validation_results.append(("Core Configuration", False, [str(e)], []))
            self.logger.error(f"❌ Core configuration validation error: {str(e)}")
        
        # Run environment-specific validation
        try:
            env_result = validate_current_environment()
            validation_results.append(("Environment Configuration", env_result["valid"], env_result.get("errors", []), env_result.get("warnings", [])))
            
            if env_result["valid"]:
                self.logger.info(f"✅ {self.environment} environment validation passed")
            else:
                self.logger.error(f"❌ {self.environment} environment validation failed")
                for error in env_result.get("errors", []):
                    self.logger.error(f"  • {error}")
            
            # Log environment warnings
            for warning in env_result.get("warnings", []):
                self.logger.warning(f"⚠️  {warning}")
                
        except Exception as e:
            validation_results.append(("Environment Configuration", False, [str(e)], []))
            self.logger.error(f"❌ Environment configuration validation error: {str(e)}")
        
        # Run additional service-specific checks
        if additional_checks:
            try:
                service_valid, service_errors, service_warnings = self._run_additional_checks(additional_checks)
                validation_results.append((f"{self.service_name} Specific", service_valid, service_errors, service_warnings))
                
                if service_valid:
                    self.logger.info(f"✅ {self.service_name} specific validation passed")
                else:
                    self.logger.error(f"❌ {self.service_name} specific validation failed")
                    for error in service_errors:
                        self.logger.error(f"  • {error}")
                
                # Log service-specific warnings
                for warning in service_warnings:
                    self.logger.warning(f"⚠️  {warning}")
                    
            except Exception as e:
                validation_results.append((f"{self.service_name} Specific", False, [str(e)], []))
                self.logger.error(f"❌ {self.service_name} specific validation error: {str(e)}")
        
        # Determine overall validation status
        overall_valid = all(result[1] for result in validation_results)
        
        if overall_valid:
            self.logger.info(f"🎉 {self.service_name} configuration validation completed successfully")
        else:
            self.logger.error(f"💥 {self.service_name} configuration validation failed")
        
        return overall_valid
    
    def _run_additional_checks(self, checks: Dict[str, Any]) -> tuple[bool, list, list]:
        """Run additional service-specific validation checks.
        
        Args:
            checks: Dictionary of check name to validation function or value
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        for check_name, check_config in checks.items():
            try:
                if callable(check_config):
                    # Function-based check
                    result = check_config()
                    if isinstance(result, bool):
                        if not result:
                            errors.append(f"{check_name} validation failed")
                    elif isinstance(result, dict):
                        if not result.get("valid", True):
                            errors.extend(result.get("errors", [f"{check_name} validation failed"]))
                        warnings.extend(result.get("warnings", []))
                    else:
                        errors.append(f"{check_name} returned unexpected result type")
                
                elif isinstance(check_config, dict):
                    # Configuration-based check
                    required = check_config.get("required", True)
                    env_var = check_config.get("env_var")
                    validator = check_config.get("validator")
                    
                    if env_var:
                        value = os.getenv(env_var)
                        if required and not value:
                            errors.append(f"Required environment variable {env_var} is missing")
                        elif value and validator and not validator(value):
                            errors.append(f"Environment variable {env_var} failed validation")
                
                else:
                    errors.append(f"Invalid check configuration for {check_name}")
                    
            except Exception as e:
                errors.append(f"Error running check {check_name}: {str(e)}")
        
        return len(errors) == 0, errors, warnings


def validate_service_startup(service_name: str, 
                           additional_checks: Optional[Dict[str, Any]] = None,
                           exit_on_failure: bool = True,
                           logger: Optional[logging.Logger] = None) -> bool:
    """Convenience function to validate service configuration on startup.
    
    Args:
        service_name: Name of the service
        additional_checks: Optional service-specific validation checks
        exit_on_failure: Whether to exit process on validation failure
        logger: Optional logger instance
        
    Returns:
        True if validation passes, False otherwise (only if exit_on_failure=False)
    """
    validator = StartupValidator(service_name, logger)
    
    if exit_on_failure:
        validator.validate_and_exit_on_failure(additional_checks)
        return True  # Will only reach here if validation passes
    else:
        return validator.validate_configuration(additional_checks)


# Common validation checks that services can use
class CommonChecks:
    """Common validation checks for services."""
    
    @staticmethod
    def database_connection_check() -> Dict[str, Any]:
        """Check database connection configuration."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return {"valid": False, "errors": ["DATABASE_URL is required"]}
        
        if not database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
            return {"valid": False, "errors": ["DATABASE_URL must be a PostgreSQL connection string"]}
        
        return {"valid": True}
    
    @staticmethod
    def openai_api_key_check() -> Dict[str, Any]:
        """Check OpenAI API key configuration."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"valid": False, "errors": ["OPENAI_API_KEY is required"]}
        
        if not api_key.startswith("sk-"):
            return {"valid": False, "errors": ["OPENAI_API_KEY must start with 'sk-'"]}
        
        return {"valid": True}
    
    @staticmethod
    def secret_key_check(min_length: int = 32) -> Dict[str, Any]:
        """Check secret key configuration."""
        secret_key = os.getenv("API_SECRET_KEY") or os.getenv("SECRET_KEY")
        if not secret_key:
            return {"valid": False, "errors": ["API_SECRET_KEY or SECRET_KEY is required"]}
        
        if len(secret_key) < min_length:
            return {"valid": False, "errors": [f"Secret key must be at least {min_length} characters long"]}
        
        # Check for development default in production
        if os.getenv("ENVIRONMENT") == "production" and "dev-secret" in secret_key.lower():
            return {"valid": False, "errors": ["Development secret key detected in production environment"]}
        
        return {"valid": True}
    
    @staticmethod
    def port_availability_check(port_env_var: str, default_port: int) -> Dict[str, Any]:
        """Check if port configuration is valid."""
        try:
            port = int(os.getenv(port_env_var, str(default_port)))
            if not (1 <= port <= 65535):
                return {"valid": False, "errors": [f"{port_env_var} must be between 1 and 65535"]}
            return {"valid": True}
        except ValueError:
            return {"valid": False, "errors": [f"{port_env_var} must be a valid integer"]}
    
    @staticmethod
    def chroma_connection_check() -> Dict[str, Any]:
        """Check ChromaDB connection configuration."""
        chroma_url = os.getenv("CHROMA_URL")
        if not chroma_url:
            return {"valid": False, "errors": ["CHROMA_URL is required for vector storage"]}
        
        warnings = []
        if os.getenv("ENVIRONMENT") == "production" and "localhost" in chroma_url:
            warnings.append("ChromaDB URL contains localhost in production environment")
        
        return {"valid": True, "warnings": warnings}