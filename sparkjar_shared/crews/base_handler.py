"""
Base class for all crew handlers.
Defines the interface and common functionality for crew execution.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from uuid import UUID
import logging
import jsonschema
from jsonschema import ValidationError as JsonSchemaValidationError

logger = logging.getLogger(__name__)

class BaseCrewHandler(ABC):
    """
    Abstract base class for all crew handlers.
    Each crew type should extend this class and implement the execute method.
    """
    
    def __init__(self, job_id: Optional[UUID] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.job_id = job_id
        self.simple_logger = None
        self.crew_logger = None
        if job_id:
            self._initialize_loggers(job_id)
    
    def _initialize_loggers(self, job_id: UUID):
        """Initialize logging systems."""
        # Import here to avoid circular imports
        from .simple_crew_logger import SimpleCrewLogger
        from .crew_logger import CrewExecutionLogger
        
        self.simple_logger = SimpleCrewLogger(job_id)
        self.crew_logger = CrewExecutionLogger(str(job_id))
    
    def set_job_id(self, job_id: UUID):
        """Set job ID and initialize loggers."""
        self.job_id = job_id
        self._initialize_loggers(job_id)
    
    @abstractmethod
    async def execute(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the crew with the provided request data.
        
        Args:
            request_data: Job request data including all parameters
            
        Returns:
            Dictionary containing execution results
            
        Raises:
            Exception: If execution fails
        """
        pass
    
    def validate_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate the request data before execution.
        Override in subclasses for specific validation logic.
        
        Args:
            request_data: Request data to validate
            
        Returns:
            True if valid, raises Exception if invalid
        """
        # Basic validation - ensure required fields exist
        required_fields = ["job_key", "client_user_id", "actor_type", "actor_id"]
        
        for field in required_fields:
            if field not in request_data:
                raise ValueError(f"Missing required field: {field}")
        
        return True
    
    def get_job_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about this job type.
        Override in subclasses to provide specific information.
        
        Returns:
            Dictionary with job type metadata
        """
        return {
            "handler_class": self.__class__.__name__,
            "description": self.__class__.__doc__ or "No description available"
        }
    
    async def cleanup(self):
        """
        Cleanup resources after job execution.
        Override in subclasses if cleanup is needed.
        """
        pass
    
    def log_execution_start(self, request_data: Dict[str, Any]):
        """Log the start of job execution."""
        self.logger.info(
            f"Starting execution for job_key: {request_data.get('job_key')}, "
            f"user: {request_data.get('client_user_id')}"
        )
        if self.simple_logger:
            from .simple_crew_logger import SimpleCrewLogger
            self.simple_logger.log_event(
                SimpleCrewLogger.CREW_START,
                {
                    'job_key': request_data.get('job_key'),
                    'client_user_id': request_data.get('client_user_id'),
                    'actor_type': request_data.get('actor_type'),
                    'actor_id': request_data.get('actor_id'),
                    'handler': self.__class__.__name__
                }
            )
    
    def log_execution_complete(self, result: Dict[str, Any]):
        """Log the completion of job execution."""
        self.logger.info(f"Execution completed successfully")
        if self.simple_logger:
            from .simple_crew_logger import SimpleCrewLogger
            self.simple_logger.log_event(
                SimpleCrewLogger.CREW_COMPLETE,
                {
                    'success': True,
                    'handler': self.__class__.__name__
                }
            )
    
    def log_execution_error(self, error: Exception):
        """Log execution errors."""
        self.logger.error(f"Execution failed: {str(error)}", exc_info=True)
        if self.simple_logger:
            from .simple_crew_logger import SimpleCrewLogger
            self.simple_logger.log_event(
                SimpleCrewLogger.ERROR_OCCURRED,
                {
                    'error_type': type(error).__name__,
                    'error_message': str(error),
                    'error_traceback': self._get_traceback(error)
                }
            )

    def _get_traceback(self, error: Exception) -> str:
        """Get formatted traceback from exception."""
        import traceback
        return ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    
    async def execute_crew_with_logging(self, crew_function, *args, **kwargs):
        """
        Execute a crew function with full logging capture.
        
        Args:
            crew_function: The function that kicks off the crew (e.g., crew.kickoff)
            *args, **kwargs: Arguments to pass to the crew function
            
        Returns:
            The result from the crew function
        """
        if not self.simple_logger:
            # Fallback to direct execution if no logger
            return crew_function(*args, **kwargs)
        
        # Execute the crew function and capture stdout
        import asyncio
        import sys
        import io
        from contextlib import redirect_stdout, redirect_stderr
        
        loop = asyncio.get_event_loop()
        
        def run_and_capture():
            """Run crew and capture all output."""
            # Capture stdout/stderr
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                try:
                    # Execute the crew function
                    result = crew_function(*args, **kwargs)
                    return result, stdout_buffer.getvalue(), stderr_buffer.getvalue()
                except Exception as e:
                    # Still return the captured output even on error
                    return e, stdout_buffer.getvalue(), stderr_buffer.getvalue()
        
        # Run in executor
        execution_result = await loop.run_in_executor(None, run_and_capture)
        
        # Unpack results
        result_or_error, stdout_content, stderr_content = execution_result
        
        # Parse the captured output
        if stdout_content:
            # Print to real stdout so we can see it
            sys.stdout.write(stdout_content)
            sys.stdout.flush()
            # Parse for events
            self.simple_logger.parse_output(stdout_content)
        
        if stderr_content:
            # Print to real stderr
            sys.stderr.write(stderr_content)
            sys.stderr.flush()
            # Parse error output
            self.simple_logger.parse_output(stderr_content)
        
        # Re-raise exception if there was one
        if isinstance(result_or_error, Exception):
            raise result_or_error
        
        return result_or_error
    
    async def save_crew_events(self):
        """
        Save all collected events to the database.
        Call this after crew execution completes.
        """
        if not self.simple_logger:
            return
        
        events = self.simple_logger.get_all_events()
        if not events:
            return
        
        # Save events to database - skip in standalone mode
        self.logger.info("Skipping database save in standalone mode")
        return
        
    
    async def validate_crew_context(self, request_data: Dict[str, Any], context_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate request data against crew-level context schema.
        
        Args:
            request_data: The incoming request data
            context_schema: JSON schema from crew config
            
        Returns:
            Validated context data
            
        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate against schema
            jsonschema.validate(request_data, context_schema)
            
            # Extract only the fields defined in the schema
            if "properties" in context_schema:
                validated_context = {}
                for field_name in context_schema["properties"].keys():
                    if field_name in request_data:
                        validated_context[field_name] = request_data[field_name]
                return validated_context
            else:
                return request_data
                
        except JsonSchemaValidationError as e:
            raise ValueError(f"Context validation failed: {e.message}")
        except Exception as e:
            raise ValueError(f"Context validation error: {str(e)}")