"""
CrewAI execution logger that captures verbose output and stores it in crew_job_event table.
Intercepts CrewAI's logging and streams it to the database for full execution tracking.
"""
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
from io import StringIO
import uuid
import asyncio

# Import database models when available
try:
    from ..database.connection import get_direct_session
    from ..database.models import CrewJobEvent
    HAS_DATABASE = True
except ImportError:
    # Placeholder classes for standalone mode
    class CrewJobEvent:
        pass
    
    def get_direct_session():
        raise NotImplementedError("Database not available in standalone mode")
    
    HAS_DATABASE = False

class CrewLogHandler(logging.Handler):
    """
    Custom logging handler that captures CrewAI logs and stores them in the database.
    """
    
    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
        self.buffer = []
        
    def emit(self, record):
        """Capture log record and buffer it for database storage."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": getattr(record, 'module', None),
                "function": getattr(record, 'funcName', None),
                "line": getattr(record, 'lineno', None)
            }
            
            # Add exception info if present
            if record.exc_info:
                log_entry["exception"] = self.format(record)
            
            self.buffer.append(log_entry)
            
        except Exception:
            # Fail silently to avoid breaking crew execution
            pass
    
    async def flush_to_db(self):
        """Flush buffered logs to the crew_job_event table."""
        if not self.buffer or not HAS_DATABASE:
            return
            
        try:
            async with get_direct_session() as session:
                # Store all buffered logs as a single event
                event = CrewJobEvent(
                    job_id=self.job_id,
                    event_type="crew_execution_logs",
                    event_data={
                        "log_entries": self.buffer,
                        "total_entries": len(self.buffer),
                        "captured_at": datetime.utcnow().isoformat()
                    },
                    event_time=datetime.utcnow()
                )
                
                session.add(event)
                await session.commit()
                
                # Clear buffer after successful storage
                self.buffer.clear()
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to flush crew logs to database: {e}")

class CrewExecutionLogger:
    """
    Main class for managing CrewAI execution logging.
    Provides context managers and utility functions for capturing crew logs.
    """
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.handler = None
        self.original_handlers = {}
        
    @asynccontextmanager
    async def capture_crew_logs(self, log_level: str = "INFO"):
        """
        Async context manager that captures all CrewAI-related logs during crew execution.
        
        Args:
            log_level: Minimum log level to capture (DEBUG, INFO, WARNING, ERROR)
            
        Usage:
            async with logger.capture_crew_logs():
                result = crew.kickoff(inputs=inputs)
        """
        # Set up log handler
        self.handler = CrewLogHandler(self.job_id)
        self.handler.setLevel(getattr(logging, log_level.upper()))
        
        # Define CrewAI-related loggers to capture
        crew_loggers = [
            "crewai",
            "crewai.crew",
            "crewai.agent", 
            "crewai.task",
            "crewai.tools",
            "crewai.memory",
            "langchain",
            "openai"
        ]
        
        try:
            # Log execution start
            await self._log_event("crew_execution_start", {
                "job_id": self.job_id,
                "start_time": datetime.utcnow().isoformat(),
                "log_level": log_level
            })
            
            # Add our handler to relevant loggers
            for logger_name in crew_loggers:
                logger = logging.getLogger(logger_name)
                self.original_handlers[logger_name] = logger.handlers.copy()
                logger.addHandler(self.handler)
                logger.setLevel(getattr(logging, log_level.upper()))
            
            yield self
            
        finally:
            # Remove our handler and restore original handlers
            for logger_name in crew_loggers:
                logger = logging.getLogger(logger_name)
                if self.handler in logger.handlers:
                    logger.removeHandler(self.handler)
                
                # Restore original handlers
                if logger_name in self.original_handlers:
                    logger.handlers = self.original_handlers[logger_name]
            
            # Flush any remaining logs to database
            if self.handler:
                await self.handler.flush_to_db()
            
            # Log execution end
            await self._log_event("crew_execution_end", {
                "job_id": self.job_id,
                "end_time": datetime.utcnow().isoformat(),
                "total_log_entries": len(self.handler.buffer) if self.handler else 0
            })
    
    async def log_crew_step(self, step_type: str, step_data: Dict[str, Any]):
        """
        Log a specific crew execution step (agent action, task completion, etc.).
        
        Args:
            step_type: Type of step (agent_action, task_start, task_complete, etc.)
            step_data: Data associated with the step
        """
        await self._log_event(f"crew_step_{step_type}", {
            "job_id": self.job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "step_data": step_data
        })
    
    async def log_crew_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Log crew execution errors with full context.
        
        Args:
            error: Exception that occurred
            context: Additional context about the error
        """
        await self._log_event("crew_execution_error", {
            "job_id": self.job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        })
    
    async def _log_event(self, event_type: str, event_data: Dict[str, Any]):
        """Helper method to log events to the database."""
        if not HAS_DATABASE:
            return
            
        try:
            # Check if we can safely log to database
            import asyncio
            try:
                # Check if event loop is available and not closed
                loop = asyncio.get_running_loop()
                if loop.is_closed():
                    # Event loop is closed, skip database logging
                    return
            except RuntimeError:
                # No event loop available, skip database logging
                return
                
            async with get_direct_session() as session:
                event = CrewJobEvent(
                    job_id=self.job_id,
                    event_type=event_type,
                    event_data=event_data,
                    event_time=datetime.utcnow()
                )
                
                session.add(event)
                await session.commit()
                
        except asyncio.CancelledError:
            # Task was cancelled, ignore
            pass
        except Exception as e:
            # Only log if it's not a common cleanup error
            error_msg = str(e).lower()
            if not any(phrase in error_msg for phrase in [
                'event loop is closed', 
                'different loop', 
                'protocol state',
                'connection closed'
            ]):
                logging.getLogger(__name__).debug(f"Crew event logging skipped: {e}")

# Convenience function for easy usage
async def log_crew_execution(job_id: str, crew_function, *args, **kwargs):
    """
    Convenience function to wrap crew execution with logging.
    
    Args:
        job_id: Job ID for tracking
        crew_function: Function that executes the crew (e.g., crew.kickoff)
        *args, **kwargs: Arguments to pass to the crew function
        
    Returns:
        Result of crew execution
        
    Usage:
        result = await log_crew_execution(
            job_id=job.id,
            crew_function=lambda: crew.kickoff(inputs=inputs)
        )
    """
    logger = CrewExecutionLogger(job_id)
    
    async with logger.capture_crew_logs():
        try:
            result = crew_function(*args, **kwargs)
            await logger.log_crew_step("execution_complete", {
                "result_type": type(result).__name__,
                "success": True
            })
            return result
            
        except Exception as e:
            await logger.log_crew_error(e, {
                "function": crew_function.__name__ if hasattr(crew_function, '__name__') else str(crew_function),
                "args": str(args)[:500],  # Limit size
                "kwargs": str(kwargs)[:500]
            })
            raise