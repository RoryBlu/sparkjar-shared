#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Usage examples for the enhanced SparkJAR logging system.

This file demonstrates how to use the new centralized logging system
with automatic sensitive data sanitization and database storage.
"""

import sys
import os

from sparkjar_crew.shared.utils.logging_config import (
    create_crew_api_logger,
    create_memory_service_logger,
    create_mcp_registry_logger,
    create_script_logger,
    create_sparkjar_logger
)

# Example 1: Basic service logging
def example_service_logging():
    """Example of how to set up logging for different services."""
    
    # For crew-api service (with database logging if session factory available)
    # crew_logger = create_crew_api_logger(db_session_factory=your_db_session_factory)
    crew_logger = create_crew_api_logger()  # Without database for this example
    
    # For memory-service
    memory_logger = create_memory_service_logger()
    
    # For mcp-registry service
    mcp_logger = create_mcp_registry_logger()
    
    # For utility scripts
    script_logger = create_script_logger("my_script")
    
    # Basic logging
    crew_logger.info("Crew API service started")
    memory_logger.info("Memory service initialized")
    mcp_logger.info("MCP registry service ready")
    script_logger.info("Script execution started")

# Example 2: Logging with context and automatic sanitization
def example_context_logging():
    """Example of logging with context data that gets automatically sanitized."""
    
    logger = create_script_logger("context_example")
    
    # This context contains sensitive data that will be automatically sanitized
    context = {
        "user_id": "user-12345",
        "action": "login",
        "api_key": "sk-1234567890abcdef",  # Will be redacted
        "database_url": "postgresql://user:password@localhost/db",  # Will be sanitized
        "safe_data": "this will remain unchanged"
    }
    
    logger.info("User performed action", context=context)
    
    # The log output will show sanitized versions of sensitive data

# Example 3: Crew execution logging
def example_crew_logging():
    """Example of structured crew execution logging."""
    
    logger = create_crew_api_logger()
    
    # Log crew execution events with structured context
    logger.log_crew_execution(
        job_id="job-abc123",
        crew_name="data-analysis-crew",
        status="started",
        client_id="client-456",
        user_id="user-789",
        additional_context={
            "input_size": "1.2MB",
            "expected_duration": "5 minutes"
        }
    )
    
    # Log crew completion
    logger.log_crew_execution(
        job_id="job-abc123",
        crew_name="data-analysis-crew",
        status="completed",
        client_id="client-456",
        user_id="user-789",
        additional_context={
            "output_size": "500KB",
            "actual_duration": "4.5 minutes"
        }
    )
    
    # Log crew error
    logger.log_crew_execution(
        job_id="job-def456",
        crew_name="report-generation-crew",
        status="failed",
        client_id="client-456",
        user_id="user-789",
        error="Failed to connect to external API",
        additional_context={
            "retry_count": 3,
            "last_error_code": "CONNECTION_TIMEOUT"
        }
    )

# Example 4: API request logging
def example_api_logging():
    """Example of API request logging with performance metrics."""
    
    logger = create_crew_api_logger()
    
    # Log successful API requests
    logger.log_api_request(
        method="POST",
        endpoint="/api/crews/execute",
        status_code=200,
        client_id="client-123",
        user_id="user-456",
        ip_address="192.168.1.100",
        duration_ms=1250.5,
        additional_context={
            "crew_type": "data-analysis",
            "payload_size": "2.1MB"
        }
    )
    
    # Log failed API requests
    logger.log_api_request(
        method="GET",
        endpoint="/api/crews/status",
        status_code=404,
        client_id="client-123",
        user_id="user-456",
        ip_address="192.168.1.100",
        duration_ms=45.2,
        additional_context={
            "error": "Job not found",
            "job_id": "nonexistent-job"
        }
    )

# Example 5: Custom logger configuration
def example_custom_logger():
    """Example of creating a custom logger with specific settings."""
    
    # Create a logger with custom settings
    custom_logger = create_sparkjar_logger(
        service_name="custom-service",
        level="DEBUG",  # More verbose logging
        db_session_factory=None,  # No database logging
        sanitize_logs=True,  # Enable sanitization
        redact_emails=True,  # Redact email addresses
        redact_phones=True,  # Redact phone numbers
        redact_ips=True  # Redact IP addresses
    )
    
    # This message contains various types of sensitive data
    sensitive_message = (
        "Processing user data: email=user@example.com, "
        "phone=555-123-4567, ip=192.168.1.100, "
        "api_key=sk-1234567890abcdef"
    )
    
    custom_logger.info(sensitive_message)
    # Output will have all sensitive data redacted

# Example 6: Error logging with context
def example_error_logging():
    """Example of error logging with detailed context."""
    
    logger = create_crew_api_logger()
    
    try:
        # Simulate an operation that might fail
        raise ValueError("Database connection failed")
    except Exception as e:
        # Log the error with context
        error_context = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "operation": "database_connection",
            "retry_count": 3,
            "database_url": "postgresql://user:secret@db.example.com/prod"  # Will be sanitized
        }
        
        logger.error(
            f"Operation failed: {str(e)}", 
            context=error_context,
            client_id="client-123"
        )

if __name__ == "__main__":
    logger.info("=== SparkJAR Logging System Usage Examples ===")
    logger.info()
    
    logger.info("1. Basic service logging:")
    example_service_logging()
    logger.info()
    
    logger.info("2. Context logging with sanitization:")
    example_context_logging()
    logger.info()
    
    logger.info("3. Crew execution logging:")
    example_crew_logging()
    logger.info()
    
    logger.info("4. API request logging:")
    example_api_logging()
    logger.info()
    
    logger.info("5. Custom logger configuration:")
    example_custom_logger()
    logger.info()
    
    logger.error("6. Error logging with context:")
    example_error_logging()
    logger.info()
    
    logger.info("✅ All examples completed successfully!")