"""
Standalone logger for crew execution without database dependency.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StandaloneCrewLogger:
    """Simple logger for standalone crew execution."""
    
    def __init__(self, crew_name: str):
        self.crew_name = crew_name
        self.start_time = None
        self.events = []
    
    def log_execution_start(self, inputs: Dict[str, Any]):
        """Log the start of crew execution."""
        self.start_time = datetime.now()
        logger.info(f"Starting {self.crew_name} execution")
        logger.info(f"Inputs: {inputs}")
        self.events.append({
            "timestamp": self.start_time,
            "event": "execution_start",
            "inputs": inputs
        })
    
    def log_task_start(self, task_name: str):
        """Log the start of a task."""
        logger.info(f"Starting task: {task_name}")
        self.events.append({
            "timestamp": datetime.now(),
            "event": "task_start",
            "task": task_name
        })
    
    def log_task_complete(self, task_name: str, result: Any):
        """Log task completion."""
        logger.info(f"Completed task: {task_name}")
        self.events.append({
            "timestamp": datetime.now(),
            "event": "task_complete",
            "task": task_name,
            "result": str(result)
        })
    
    def log_execution_complete(self, result: Any):
        """Log execution completion."""
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        logger.info(f"Completed {self.crew_name} execution in {duration:.2f} seconds")
        self.events.append({
            "timestamp": datetime.now(),
            "event": "execution_complete",
            "duration": duration,
            "result": str(result)
        })
        
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        return {
            "crew_name": self.crew_name,
            "start_time": self.start_time,
            "events": self.events,
            "total_events": len(self.events)
        }