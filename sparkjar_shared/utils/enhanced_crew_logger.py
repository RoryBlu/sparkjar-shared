"""
Enhanced Crew Logger with Real-time Event Capture

This module provides comprehensive logging for CrewAI operations, capturing:
- Every agent thought and reasoning step
- All tool executions and results
- Task progress and completions
- Errors and retries
- System events and performance metrics
"""
import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID
from contextlib import contextmanager
import asyncio
from queue import Queue
import threading

from sqlalchemy.ext.asyncio import AsyncSession
from database.models import CrewJobEvent
from database.connection import get_db_session

logger = logging.getLogger(__name__)

class EnhancedCrewLogger:
    """
    Enhanced logger that captures ALL CrewAI events in real-time.
    
    Features:
    - Real-time event streaming to database
    - Structured event parsing from log messages
    - Callback integration for rich event data
    - Buffering with periodic flushing
    - Thread-safe event queue
    """
    
    # Event type constants
    AGENT_THOUGHT = "agent_thought"
    AGENT_ACTION = "agent_action"
    TOOL_EXECUTION = "tool_execution"
    TOOL_RESULT = "tool_result"
    TASK_START = "task_start"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    CREW_START = "crew_start"
    CREW_COMPLETE = "crew_complete"
    ERROR_OCCURRED = "error_occurred"
    RETRY_ATTEMPT = "retry_attempt"
    MEMORY_ACCESS = "memory_access"
    MEMORY_UPDATE = "memory_update"
    CONTEXT_SET = "context_set"
    OBSERVATION = "observation"
    
    def __init__(self, job_id: UUID, flush_interval: float = 5.0):
        """
        Initialize enhanced logger.
        
        Args:
            job_id: The crew job ID
            flush_interval: Seconds between automatic flushes to database
        """
        self.job_id = job_id
        self.flush_interval = flush_interval
        self._event_queue = Queue()
        self._handlers = []
        self._flush_thread = None
        self._stop_flushing = threading.Event()
        self._session = None
        self._collected_events = []  # Store events for batch saving
        
        # Regex patterns for parsing CrewAI output
        self.patterns = {
            'agent_thought': re.compile(r'Thought:\s*(.+)', re.IGNORECASE),
            'agent_action': re.compile(r'Action:\s*(.+)', re.IGNORECASE),
            'action_input': re.compile(r'Action Input:\s*(.+)', re.IGNORECASE | re.DOTALL),
            'observation': re.compile(r'Observation:\s*(.+)', re.IGNORECASE | re.DOTALL),
            'final_answer': re.compile(r'Final Answer:\s*(.+)', re.IGNORECASE | re.DOTALL),
            'task_status': re.compile(r'Status:\s*(.+)', re.IGNORECASE),
            'tool_error': re.compile(r'Tool Error.*?:\s*(.+)', re.IGNORECASE),
            'retry': re.compile(r'Retry(?:ing)?\s+(?:attempt\s+)?(\d+)(?:\s+of\s+\d+)?.*?:\s*(.+)', re.IGNORECASE),
        }
    
    def start(self):
        """Start the background flush thread."""
        self._stop_flushing.clear()
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
    
    def stop(self):
        """Stop the background flush thread and flush remaining events."""
        self._stop_flushing.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=2)
        # Final flush - only if thread is not running to avoid conflicts
        if not self._flush_thread or not self._flush_thread.is_alive():
            self._flush_events()
        
        # Save all pending events if we have any
        # This will be called from the main thread with proper async context
        if hasattr(self, '_pending_events') and self._pending_events:
            # We'll save these synchronously since we're being called from async context
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule the save operation
                    asyncio.create_task(self._save_events(self._pending_events))
                else:
                    # Run it directly
                    loop.run_until_complete(self._save_events(self._pending_events))
                self._pending_events = []
            except Exception as e:
                logger.error(f"Failed to save pending events: {e}")
    
    def _flush_loop(self):
        """Background thread that periodically flushes events to database."""
        while not self._stop_flushing.is_set():
            self._stop_flushing.wait(self.flush_interval)
            if not self._stop_flushing.is_set():
                self._flush_events()
    
    def _flush_events(self):
        """Flush queued events to database."""
        events = []
        while not self._event_queue.empty():
            try:
                events.append(self._event_queue.get_nowait())
            except:
                break
        
        if events:
            # Store events for later saving
            # We'll save them when stop() is called from the main thread
            self._pending_events = getattr(self, '_pending_events', [])
            self._pending_events.extend(events)
    
    async def _save_events(self, events: List[Dict[str, Any]]):
        """Save events to database."""
        try:
            async with get_db_session() as db:
                for event in events:
                    db_event = CrewJobEvent(
                        job_id=self.job_id,
                        event_type=event['event_type'],
                        event_data=event['event_data'],
                        event_time=event['event_time']
                    )
                    db.add(db_event)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save events: {e}")
    
    def log_event(self, event_type: str, event_data: Dict[str, Any]):
        """
        Log an event to the queue.
        
        Args:
            event_type: Type of event
            event_data: Event details
        """
        event = {
            'event_type': event_type,
            'event_data': event_data,
            'event_time': datetime.utcnow()
        }
        # Store events in memory for batch saving
        self._collected_events.append(event)
    
    def _should_filter_message(self, message: str) -> bool:
        """Check if message should be filtered out entirely."""
        filter_patterns = [
            r'RequestOptions\(',
            r'api_key=',
            r'Authorization:',
            r'httpx\.',
            r'urllib3\.',
            r'connectionpool\.',
            r'Starting new HTTP',
            r'POST /v1/embeddings',
            r'POST /v1/chat/completions',
        ]
        return any(re.search(pattern, message, re.IGNORECASE) for pattern in filter_patterns)
    
    def _sanitize_message(self, message: str) -> str:
        """Remove sensitive information from messages."""
        # Redact API keys
        message = re.sub(r'(api_key|API_KEY|authorization)=["\']?[^"\'\s]+', r'\1=REDACTED', message)
        # Remove full request options
        message = re.sub(r'RequestOptions\([^)]+\)', 'RequestOptions(REDACTED)', message)
        # Truncate very long messages
        if len(message) > 1000:
            message = message[:1000] + '... (truncated)'
        return message
    
    def parse_and_log(self, message: str, level: str = "INFO"):
        """
        Parse CrewAI log message and create structured events.
        
        Args:
            message: Raw log message
            level: Log level
        """
        # Filter out implementation details and sensitive data
        if self._should_filter_message(message):
            return
        # Check for agent thoughts
        if match := self.patterns['agent_thought'].search(message):
            self.log_event(self.AGENT_THOUGHT, {
                'thought': match.group(1).strip(),
                'raw_message': message,
                'level': level
            })
        
        # Check for agent actions
        if match := self.patterns['agent_action'].search(message):
            action = match.group(1).strip()
            action_input = None
            if input_match := self.patterns['action_input'].search(message):
                action_input = input_match.group(1).strip()
            
            self.log_event(self.AGENT_ACTION, {
                'action': action,
                'action_input': action_input,
                'raw_message': message,
                'level': level
            })
        
        # Check for observations
        if match := self.patterns['observation'].search(message):
            self.log_event(self.OBSERVATION, {
                'observation': match.group(1).strip(),
                'raw_message': message,
                'level': level
            })
        
        # Check for final answers
        if match := self.patterns['final_answer'].search(message):
            self.log_event(self.TASK_COMPLETE, {
                'final_answer': match.group(1).strip(),
                'raw_message': message,
                'level': level
            })
        
        # Check for tool errors
        if match := self.patterns['tool_error'].search(message):
            self.log_event(self.ERROR_OCCURRED, {
                'error_type': 'tool_error',
                'error': match.group(1).strip(),
                'raw_message': message,
                'level': level
            })
        
        # Check for retries
        if match := self.patterns['retry'].search(message):
            self.log_event(self.RETRY_ATTEMPT, {
                'retry_number': int(match.group(1)),
                'reason': match.group(2).strip(),
                'raw_message': message,
                'level': level
            })
        
        # Only log sanitized raw messages for debug purposes
        if level in ['ERROR', 'WARNING'] or not message.startswith(('POST', 'GET', 'HTTP')):
            self.log_event('raw_log', {
                'message': self._sanitize_message(message),
                'level': level,
                'timestamp': datetime.utcnow().isoformat()
            })
    
    def create_step_callback(self) -> Callable:
        """
        Create a callback for agent steps that logs to database.
        
        Returns:
            Callback function for CrewAI step_callback
        """
        def callback(step_output):
            # Extract relevant data from step output
            data = {
                'agent': getattr(step_output, 'agent', 'unknown'),
                'action': getattr(step_output, 'action', None),
                'action_input': getattr(step_output, 'action_input', None),
                'observation': getattr(step_output, 'observation', None),
                'thought': getattr(step_output, 'thought', None),
                'output': getattr(step_output, 'output', None),
                'log': getattr(step_output, 'log', None),
                'return_values': getattr(step_output, 'return_values', None),
                'raw_output': str(step_output),
                'type': type(step_output).__name__
            }
            
            # Log based on content
            if data['thought']:
                self.log_event(self.AGENT_THOUGHT, data)
            if data['action']:
                self.log_event(self.AGENT_ACTION, data)
            if data['observation']:
                self.log_event(self.OBSERVATION, data)
            
            # Also log the complete step
            self.log_event('agent_step', data)
            
        return callback
    
    def create_task_callback(self) -> Callable:
        """
        Create a callback for task completion that logs to database.
        
        Returns:
            Callback function for CrewAI task_callback
        """
        def callback(task_output):
            data = {
                'task_id': str(getattr(task_output, 'id', 'unknown')),
                'description': getattr(task_output, 'description', None),
                'summary': getattr(task_output, 'summary', None),
                'result': getattr(task_output, 'result', None),
                'agent': getattr(task_output, 'agent', None),
                'raw_output': str(task_output)
            }
            
            self.log_event(self.TASK_COMPLETE, data)
            
        return callback
    
    def create_tool_callback(self) -> Callable:
        """
        Create a callback for tool execution that logs to database.
        
        Returns:
            Callback function for tool execution
        """
        def callback(tool_name: str, tool_input: Any, tool_output: Any, error: Optional[str] = None):
            data = {
                'tool_name': tool_name,
                'tool_input': str(tool_input),
                'tool_output': str(tool_output),
                'error': error,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if error:
                self.log_event(self.ERROR_OCCURRED, {
                    'error_type': 'tool_execution',
                    **data
                })
            else:
                self.log_event(self.TOOL_EXECUTION, data)
            
        return callback
    
    @contextmanager
    def capture_logs(self):
        """
        Context manager that captures all CrewAI logs.
        
        Usage:
            with logger.capture_logs():
                crew.kickoff()
        """
        # Setup custom log handler
        handler = CrewLogCaptureHandler(self)
        
        # Add handler to all relevant loggers
        loggers = [
            'crewai',
            'crewai.crew',
            'crewai.agent',
            'crewai.task',
            'crewai.tools',
            'crewai.memory',
            'langchain',
            'openai'
        ]
        
        # Store original log levels
        original_levels = {}
        
        for logger_name in loggers:
            target_logger = logging.getLogger(logger_name)
            original_levels[logger_name] = target_logger.level
            target_logger.addHandler(handler)
            
            # Set appropriate log levels to reduce noise
            if logger_name in ['openai', 'httpx', 'urllib3']:
                target_logger.setLevel(logging.WARNING)  # Only warnings and errors
            else:
                target_logger.setLevel(logging.INFO)  # Skip debug logs
                
            self._handlers.append((target_logger, handler, original_levels[logger_name]))
        
        # Start background flushing
        self.start()
        
        try:
            yield self
        finally:
            # Remove handlers and restore original log levels
            for target_logger, handler, original_level in self._handlers:
                target_logger.removeHandler(handler)
                target_logger.setLevel(original_level)
            
            # Stop flushing and save remaining events
            self.stop()

class CrewLogCaptureHandler(logging.Handler):
    """Custom log handler that captures and parses CrewAI logs."""
    
    def __init__(self, crew_logger: EnhancedCrewLogger):
        super().__init__()
        self.crew_logger = crew_logger
    
    def emit(self, record: logging.LogRecord):
        """Process a log record."""
        try:
            message = self.format(record)
            self.crew_logger.parse_and_log(
                message,
                level=record.levelname
            )
        except Exception as e:
            logger.error(f"Error processing log record: {e}")

def create_enhanced_logger(job_id: UUID, flush_interval: float = 5.0) -> EnhancedCrewLogger:
    """
    Factory function to create an enhanced crew logger.
    
    Args:
        job_id: The crew job ID
        flush_interval: Seconds between automatic flushes
        
    Returns:
        Configured EnhancedCrewLogger instance
    """
    return EnhancedCrewLogger(job_id, flush_interval)