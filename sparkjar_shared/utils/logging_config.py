"""Centralized logging configuration for SparkJAR Crew services."""
import logging
import sys
from typing import Optional, Dict, Any, List
import os
import uuid
import re
from datetime import datetime
import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

class SensitiveDataSanitizer:
    """
    Sanitizes sensitive data from log messages to prevent security leaks.
    
    This class automatically detects and redacts:
    - API keys and tokens
    - JWT tokens
    - Database URLs with credentials
    - Email addresses (optional)
    - Credit card numbers
    - Social security numbers
    - Phone numbers (optional)
    - IP addresses (optional)
    """
    
    def __init__(self, 
                 redact_emails: bool = False,
                 redact_phones: bool = False,
                 redact_ips: bool = False):
        """
        Initialize the sanitizer with configuration options.
        
        Args:
            redact_emails: Whether to redact email addresses
            redact_phones: Whether to redact phone numbers
            redact_ips: Whether to redact IP addresses
        """
        self.redact_emails = redact_emails
        self.redact_phones = redact_phones
        self.redact_ips = redact_ips
        
        # Compile regex patterns for better performance
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for sensitive data detection."""
        
        # API Keys and Tokens (various formats)
        self.api_key_patterns = [
            re.compile(r'\b[Aa]pi[_-]?[Kk]ey["\s]*[:=]["\s]*([A-Za-z0-9_\-]{20,})', re.IGNORECASE),
            re.compile(r'\b[Tt]oken["\s]*[:=]["\s]*([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE),
            re.compile(r'\b[Ss]ecret[_-]?[Kk]ey["\s]*[:=]["\s]*([A-Za-z0-9_\-]{20,})', re.IGNORECASE),
            re.compile(r'\b[Aa]ccess[_-]?[Tt]oken["\s]*[:=]["\s]*([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE),
            re.compile(r'\bBearer\s+([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE),
            re.compile(r'\bAuthorization["\s]*[:=]["\s]*Bearer\s+([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE),
        ]
        
        # JWT Tokens
        self.jwt_pattern = re.compile(r'\beyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*')
        
        # Database URLs with credentials
        self.db_url_pattern = re.compile(
            r'(postgresql|mysql|sqlite|mongodb)://([^:]+):([^@]+)@([^/]+)',
            re.IGNORECASE
        )
        
        # Credit Card Numbers (basic pattern)
        self.credit_card_pattern = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
        
        # Social Security Numbers
        self.ssn_pattern = re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b')
        
        # Email addresses (if enabled)
        if self.redact_emails:
            self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # Phone numbers (if enabled)
        if self.redact_phones:
            self.phone_pattern = re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b')
        
        # IP addresses (if enabled)
        if self.redact_ips:
            self.ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
        
        # Common environment variable patterns
        self.env_var_patterns = [
            re.compile(r'([A-Z_]+_KEY|[A-Z_]+_SECRET|[A-Z_]+_TOKEN|[A-Z_]+_PASSWORD)["\s]*[:=]["\s]*([^\s"\']+)', re.IGNORECASE),
            re.compile(r'(DATABASE_URL|REDIS_URL|MONGODB_URI)["\s]*[:=]["\s]*([^\s"\']+)', re.IGNORECASE),
        ]
    
    def sanitize(self, text: str) -> str:
        """
        Sanitize sensitive data from the given text.
        
        Args:
            text: The text to sanitize
            
        Returns:
            Sanitized text with sensitive data redacted
        """
        if not isinstance(text, str):
            # Convert to string if not already
            text = str(text)
        
        # Sanitize API keys and tokens
        for pattern in self.api_key_patterns:
            text = pattern.sub(lambda m: f"{m.group(0).split('=')[0] if '=' in m.group(0) else m.group(0).split(':')[0]}=***REDACTED***", text)
        
        # Sanitize JWT tokens
        text = self.jwt_pattern.sub('***JWT_TOKEN_REDACTED***', text)
        
        # Sanitize database URLs
        text = self.db_url_pattern.sub(r'\1://***USER***:***PASSWORD***@\4', text)
        
        # Sanitize credit card numbers
        text = self.credit_card_pattern.sub('***CREDIT_CARD_REDACTED***', text)
        
        # Sanitize SSNs
        text = self.ssn_pattern.sub('***SSN_REDACTED***', text)
        
        # Sanitize environment variables
        for pattern in self.env_var_patterns:
            text = pattern.sub(r'\1=***REDACTED***', text)
        
        # Optional sanitizations
        if self.redact_emails and hasattr(self, 'email_pattern'):
            text = self.email_pattern.sub('***EMAIL_REDACTED***', text)
        
        if self.redact_phones and hasattr(self, 'phone_pattern'):
            text = self.phone_pattern.sub('***PHONE_REDACTED***', text)
        
        if self.redact_ips and hasattr(self, 'ip_pattern'):
            text = self.ip_pattern.sub('***IP_REDACTED***', text)
        
        return text
    
    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize a dictionary, handling nested structures.
        
        Args:
            data: Dictionary to sanitize
            
        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            # Check if key suggests sensitive data
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in ['password', 'secret', 'token', 'key', 'auth']):
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, str):
                sanitized[key] = self.sanitize(value)
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self.sanitize_dict(item) if isinstance(item, dict) else 
                                self.sanitize(item) if isinstance(item, str) else item 
                                for item in value]
            else:
                sanitized[key] = value
        
        return sanitized

class SparkJarLogger:
    """
    Enhanced logger with automatic sensitive data sanitization and structured logging.
    
    This logger provides:
    - Automatic sanitization of sensitive data
    - Structured logging with consistent format
    - Database logging support
    - Context-aware logging for crew operations
    """
    
    def __init__(self, 
                 name: str, 
                 level: str = "INFO",
                 db_session_factory=None,
                 sanitize_logs: bool = True,
                 redact_emails: bool = False,
                 redact_phones: bool = False,
                 redact_ips: bool = False):
        """
        Initialize the SparkJar logger.
        
        Args:
            name: Logger name (usually service name)
            level: Logging level
            db_session_factory: Database session factory for database logging
            sanitize_logs: Whether to sanitize sensitive data
            redact_emails: Whether to redact email addresses
            redact_phones: Whether to redact phone numbers
            redact_ips: Whether to redact IP addresses
        """
        self.name = name
        self.sanitize_logs = sanitize_logs
        
        # Initialize sanitizer if enabled
        if sanitize_logs:
            self.sanitizer = SensitiveDataSanitizer(
                redact_emails=redact_emails,
                redact_phones=redact_phones,
                redact_ips=redact_ips
            )
        
        # Set up the underlying logger
        if db_session_factory:
            self.logger = setup_database_logging(name, db_session_factory, level)
        else:
            self.logger = setup_logging(name, level)
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitize a log message if sanitization is enabled."""
        if self.sanitize_logs and hasattr(self, 'sanitizer'):
            return self.sanitizer.sanitize(message)
        return message
    
    def _sanitize_context(self, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Sanitize context data if sanitization is enabled."""
        if context and self.sanitize_logs and hasattr(self, 'sanitizer'):
            return self.sanitizer.sanitize_dict(context)
        return context
    
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log debug message with automatic sanitization."""
        sanitized_message = self._sanitize_message(message)
        sanitized_context = self._sanitize_context(context)
        
        if sanitized_context:
            kwargs['context'] = sanitized_context
        
        self.logger.debug(sanitized_message, extra=kwargs)
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log info message with automatic sanitization."""
        sanitized_message = self._sanitize_message(message)
        sanitized_context = self._sanitize_context(context)
        
        if sanitized_context:
            kwargs['context'] = sanitized_context
        
        self.logger.info(sanitized_message, extra=kwargs)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log warning message with automatic sanitization."""
        sanitized_message = self._sanitize_message(message)
        sanitized_context = self._sanitize_context(context)
        
        if sanitized_context:
            kwargs['context'] = sanitized_context
        
        self.logger.warning(sanitized_message, extra=kwargs)
    
    def error(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log error message with automatic sanitization."""
        sanitized_message = self._sanitize_message(message)
        sanitized_context = self._sanitize_context(context)
        
        if sanitized_context:
            kwargs['context'] = sanitized_context
        
        self.logger.error(sanitized_message, extra=kwargs)
    
    def critical(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log critical message with automatic sanitization."""
        sanitized_message = self._sanitize_message(message)
        sanitized_context = self._sanitize_context(context)
        
        if sanitized_context:
            kwargs['context'] = sanitized_context
        
        self.logger.critical(sanitized_message, extra=kwargs)
    
    def log_crew_execution(self, 
                          job_id: str, 
                          crew_name: str, 
                          status: str,
                          client_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          error: Optional[str] = None,
                          additional_context: Optional[Dict[str, Any]] = None):
        """Log crew execution with structured context."""
        context = {
            'job_id': job_id,
            'crew_name': crew_name,
            'status': status,
            'event_type': 'crew_execution'
        }
        
        if error:
            context['error'] = error
        
        if additional_context:
            context.update(additional_context)
        
        level_method = self.error if error else self.info
        message = f"Crew {crew_name} execution {status}"
        if error:
            message += f": {error}"
        
        level_method(message, context=context, client_id=client_id, user_id=user_id)
    
    def log_api_request(self,
                       method: str,
                       endpoint: str,
                       status_code: int,
                       client_id: Optional[str] = None,
                       user_id: Optional[str] = None,
                       ip_address: Optional[str] = None,
                       duration_ms: Optional[float] = None,
                       additional_context: Optional[Dict[str, Any]] = None):
        """Log API request with structured context."""
        context = {
            'method': method,
            'endpoint': endpoint,
            'status_code': status_code,
            'event_type': 'api_request'
        }
        
        if duration_ms:
            context['duration_ms'] = duration_ms
        
        if additional_context:
            context.update(additional_context)
        
        level_method = self.warning if status_code >= 400 else self.info
        message = f"{method} {endpoint} - {status_code}"
        if duration_ms:
            message += f" ({duration_ms:.2f}ms)"
        
        level_method(message, context=context, client_id=client_id, user_id=user_id, ip_address=ip_address)

def setup_logging(
    service_name: str,
    level: str = "INFO",
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging for a service with consistent formatting.
    
    Args:
        service_name: Name of the service (e.g., 'crew-api', 'memory-service')
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string (optional)
    
    Returns:
        Configured logger instance
    """
    # Default format
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(filename)s:%(lineno)d] - %(message)s"
        )
    
    # Get log level from environment or use provided level
    log_level = os.getenv("LOG_LEVEL", level).upper()
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Module name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

# Configure third-party library logging levels
def configure_third_party_logging():
    """Configure logging levels for third-party libraries to reduce noise."""
    # Reduce noise from common libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

# Service-specific logger setup functions
def setup_crew_api_logging() -> logging.Logger:
    """Set up logging for crew-api service."""
    configure_third_party_logging()
    return setup_logging("crew-api")

def setup_memory_service_logging() -> logging.Logger:
    """Set up logging for memory-service."""
    configure_third_party_logging()
    return setup_logging("memory-service")

def setup_mcp_registry_logging() -> logging.Logger:
    """Set up logging for mcp-registry service."""
    configure_third_party_logging()
    return setup_logging("mcp-registry")

def setup_script_logging(script_name: str) -> logging.Logger:
    """Set up logging for utility scripts."""
    return setup_logging(f"script.{script_name}", level="INFO")

class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler that writes to appropriate database tables.
    
    Routes logs to:
    - system_logs table for general system operations
    - crew_job_event table for crew-specific operations
    """
    
    def __init__(self, db_session_factory, source: str, log_type: str = "system"):
        """
        Initialize the database log handler.
        
        Args:
            db_session_factory: Database session factory
            source: Source service name
            log_type: Type of logging ("system" or "crew")
        """
        super().__init__()
        self.db_session_factory = db_session_factory
        self.source = source
        self.log_type = log_type
        self.trace_id = str(uuid.uuid4())
        
        # Initialize sanitizer for database logging
        self.sanitizer = SensitiveDataSanitizer()
    
    def emit(self, record):
        """Emit a log record to the appropriate database table."""
        try:
            # Sanitize the log message and context
            sanitized_message = self.sanitizer.sanitize(self.format(record))
            
            # Determine if this is a crew-related log
            is_crew_log = (
                hasattr(record, 'context') and 
                isinstance(record.context, dict) and 
                record.context.get('event_type') == 'crew_execution'
            )
            
            if is_crew_log and hasattr(record, 'context'):
                # Route to crew_job_event table
                self._emit_crew_log(record, sanitized_message)
            else:
                # Route to system_logs table
                self._emit_system_log(record, sanitized_message)
                
        except Exception:
            # Don't let logging errors break the application
            self.handleError(record)
    
    def _emit_crew_log(self, record, sanitized_message):
        """Emit a crew-specific log to crew_job_event table."""
        try:
            context = getattr(record, 'context', {})
            job_id = context.get('job_id')
            
            if job_id:
                event_data = {
                    'level': record.levelname,
                    'message': sanitized_message,
                    'source': self.source,
                    'trace_id': self.trace_id
                }
                
                # Add sanitized context
                if context:
                    sanitized_context = self.sanitizer.sanitize_dict(context)
                    event_data.update(sanitized_context)
                
                # Add user info if available
                if hasattr(record, 'client_id'):
                    event_data['client_id'] = record.client_id
                if hasattr(record, 'user_id'):
                    event_data['user_id'] = record.user_id
                if hasattr(record, 'ip_address'):
                    event_data['ip_address'] = record.ip_address
                
                crew_log_data = {
                    'job_id': job_id,
                    'event_type': f"log_{record.levelname.lower()}",
                    'event_data': event_data,
                    'event_time': datetime.utcnow()
                }
                
                # Insert into crew_job_event table
                asyncio.create_task(self._insert_crew_log(crew_log_data))
            else:
                # Fallback to system logs if no job_id
                self._emit_system_log(record, sanitized_message)
                
        except Exception:
            # Fallback to system logs on error
            self._emit_system_log(record, sanitized_message)
    
    def _emit_system_log(self, record, sanitized_message):
        """Emit a system log to system_logs table."""
        try:
            # Create log entry data
            log_data = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow(),
                'source': self.source,
                'level': record.levelname,
                'message': sanitized_message,
                'trace_id': self.trace_id,
                'created_at': datetime.utcnow()
            }
            
            # Add sanitized context if available
            if hasattr(record, 'context') and record.context:
                sanitized_context = self.sanitizer.sanitize_dict(record.context)
                log_data['context'] = sanitized_context
            
            # Add user info if available
            if hasattr(record, 'client_id'):
                log_data['client_id'] = record.client_id
            if hasattr(record, 'user_id'):
                log_data['user_id'] = record.user_id
            if hasattr(record, 'ip_address'):
                log_data['ip_address'] = record.ip_address
            
            # Insert into database asynchronously
            asyncio.create_task(self._insert_system_log(log_data))
            
        except Exception:
            self.handleError(record)
    
    async def _insert_crew_log(self, log_data):
        """Insert crew log entry into crew_job_event table."""
        try:
            async with self.db_session_factory() as session:
                await session.execute(
                    text("""
                        INSERT INTO crew_job_event 
                        (job_id, event_type, event_data, event_time)
                        VALUES 
                        (:job_id, :event_type, :event_data, :event_time)
                    """),
                    log_data
                )
                await session.commit()
        except Exception:
            # Silently fail - don't let database logging errors break the app
            pass
    
    async def _insert_system_log(self, log_data):
        """Insert system log entry into system_logs table."""
        try:
            async with self.db_session_factory() as session:
                await session.execute(
                    text("""
                        INSERT INTO system_logs 
                        (id, timestamp, source, level, message, context, 
                         client_id, user_id, trace_id, ip_address, created_at)
                        VALUES 
                        (:id, :timestamp, :source, :level, :message, :context,
                         :client_id, :user_id, :trace_id, :ip_address, :created_at)
                    """),
                    log_data
                )
                await session.commit()
        except Exception:
            # Silently fail - don't let database logging errors break the app
            pass

def setup_database_logging(
    service_name: str,
    db_session_factory,
    level: str = "INFO"
) -> logging.Logger:
    """
    Set up logging with both console and database handlers.
    
    Args:
        service_name: Name of the service
        db_session_factory: Async database session factory
        level: Logging level
    
    Returns:
        Configured logger with database logging
    """
    # Set up basic logging first
    logger = setup_logging(service_name, level)
    
    # Add database handler
    db_handler = DatabaseLogHandler(db_session_factory, service_name)
    db_handler.setLevel(getattr(logging, level.upper()))
    
    # Use same formatter as console
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[%(filename)s:%(lineno)d] - %(message)s"
    )
    db_handler.setFormatter(formatter)
    
    logger.addHandler(db_handler)
    
    return logger

def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """
    Log a message with additional context that will be stored in the database.
    
    Args:
        logger: Logger instance
        level: Log level (info, warning, error, etc.)
        message: Log message
        context: Additional context data (will be stored as JSON)
        client_id: Client ID for user-specific logging
        user_id: User ID for user-specific logging
        ip_address: IP address for request tracking
    """
    # Create a log record with extra attributes
    extra = {}
    if context:
        extra['context'] = context
    if client_id:
        extra['client_id'] = client_id
    if user_id:
        extra['user_id'] = user_id
    if ip_address:
        extra['ip_address'] = ip_address
    
    # Log with the specified level
    log_method = getattr(logger, level.lower())
    log_method(message, extra=extra)

# Convenience functions for common logging patterns
def log_crew_execution(
    logger: logging.Logger,
    job_id: str,
    crew_name: str,
    status: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    error: Optional[str] = None
):
    """Log crew execution events."""
    context = {
        'job_id': job_id,
        'crew_name': crew_name,
        'status': status
    }
    if error:
        context['error'] = error
    
    level = 'error' if error else 'info'
    message = f"Crew {crew_name} execution {status}"
    if error:
        message += f": {error}"
    
    log_with_context(
        logger, level, message, context, client_id, user_id
    )

def log_api_request(
    logger: logging.Logger,
    method: str,
    endpoint: str,
    status_code: int,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    duration_ms: Optional[float] = None
):
    """Log API request events."""
    context = {
        'method': method,
        'endpoint': endpoint,
        'status_code': status_code
    }
    if duration_ms:
        context['duration_ms'] = duration_ms
    
    level = 'warning' if status_code >= 400 else 'info'
    message = f"{method} {endpoint} - {status_code}"
    if duration_ms:
        message += f" ({duration_ms:.2f}ms)"
    
    log_with_context(
        logger, level, message, context, client_id, user_id, ip_address
    )

# Enhanced service-specific logger factory functions
def create_sparkjar_logger(
    service_name: str,
    level: str = "INFO",
    db_session_factory=None,
    sanitize_logs: bool = True,
    redact_emails: bool = False,
    redact_phones: bool = False,
    redact_ips: bool = False
) -> SparkJarLogger:
    """
    Create a SparkJarLogger instance with enhanced features.
    
    Args:
        service_name: Name of the service
        level: Logging level
        db_session_factory: Database session factory for database logging
        sanitize_logs: Whether to sanitize sensitive data
        redact_emails: Whether to redact email addresses
        redact_phones: Whether to redact phone numbers
        redact_ips: Whether to redact IP addresses
    
    Returns:
        Configured SparkJarLogger instance
    """
    configure_third_party_logging()
    return SparkJarLogger(
        name=service_name,
        level=level,
        db_session_factory=db_session_factory,
        sanitize_logs=sanitize_logs,
        redact_emails=redact_emails,
        redact_phones=redact_phones,
        redact_ips=redact_ips
    )

def create_crew_api_logger(db_session_factory=None) -> SparkJarLogger:
    """Create a SparkJarLogger for crew-api service."""
    return create_sparkjar_logger(
        service_name="crew-api",
        level=os.getenv("LOG_LEVEL", "INFO"),
        db_session_factory=db_session_factory,
        sanitize_logs=True,
        redact_emails=False,
        redact_phones=True,
        redact_ips=False
    )

def create_memory_service_logger(db_session_factory=None) -> SparkJarLogger:
    """Create a SparkJarLogger for memory-service."""
    return create_sparkjar_logger(
        service_name="memory-service",
        level=os.getenv("LOG_LEVEL", "INFO"),
        db_session_factory=db_session_factory,
        sanitize_logs=True,
        redact_emails=False,
        redact_phones=True,
        redact_ips=False
    )

def create_mcp_registry_logger(db_session_factory=None) -> SparkJarLogger:
    """Create a SparkJarLogger for mcp-registry service."""
    return create_sparkjar_logger(
        service_name="mcp-registry",
        level=os.getenv("LOG_LEVEL", "INFO"),
        db_session_factory=db_session_factory,
        sanitize_logs=True,
        redact_emails=False,
        redact_phones=True,
        redact_ips=False
    )

def create_script_logger(script_name: str) -> SparkJarLogger:
    """Create a SparkJarLogger for utility scripts."""
    return create_sparkjar_logger(
        service_name=f"script.{script_name}",
        level=os.getenv("LOG_LEVEL", "INFO"),
        db_session_factory=None,  # Scripts typically don't need database logging
        sanitize_logs=True,
        redact_emails=False,
        redact_phones=True,
        redact_ips=False
    )