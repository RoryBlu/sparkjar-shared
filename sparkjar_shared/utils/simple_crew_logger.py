"""
Simple Crew Logger - In-Memory Event Collection

This module provides a simplified logging solution for CrewAI operations.
Events are collected in memory and saved in batch after execution completes.
"""
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID

logger = logging.getLogger(__name__)

class SimpleCrewLogger:
    """
    Simple logger that collects CrewAI events in memory.
    
    Design principles:
    - No threading or async operations
    - All events stored in memory
    - Batch save after execution completes
    - Simple and reliable
    """
    
    # Event type constants
    AGENT_THOUGHT = "agent_thought"
    AGENT_ACTION = "agent_action"
    TOOL_EXECUTION = "tool_execution"
    TOOL_RESULT = "tool_result"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    CREW_START = "crew_start"
    CREW_COMPLETE = "crew_complete"
    ERROR_OCCURRED = "error_occurred"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    RAW_LOG = "raw_log"
    
    def __init__(self, job_id: UUID):
        """Initialize simple logger."""
        self.job_id = job_id
        self.events = []  # Simple list to store events
        
        # Regex patterns for parsing CrewAI output
        self.patterns = {
            'agent_thought': re.compile(r'Thought:\s*(.+)', re.IGNORECASE),
            'agent_action': re.compile(r'Action:\s*(.+)', re.IGNORECASE),
            'action_input': re.compile(r'Action Input:\s*(.+)', re.IGNORECASE | re.DOTALL),
            'observation': re.compile(r'Observation:\s*(.+)', re.IGNORECASE | re.DOTALL),
            'final_answer': re.compile(r'Final Answer:\s*(.+)', re.IGNORECASE | re.DOTALL),
            'agent_started': re.compile(r'Agent:\s*(.+)', re.IGNORECASE),
            'task': re.compile(r'Task:\s*(.+)', re.IGNORECASE),
        }
    
    def log_event(self, event_type: str, event_data: Dict[str, Any]):
        """
        Log an event to memory.
        
        Args:
            event_type: Type of event
            event_data: Event details
        """
        event = {
            'job_id': str(self.job_id),
            'event_type': event_type,
            'event_data': event_data,
            'event_time': datetime.utcnow()
        }
        self.events.append(event)
    
    def parse_line(self, line: str):
        """
        Parse a single line of CrewAI output and create events.
        
        Args:
            line: Single line of output to parse
        """
        # Skip empty lines
        if not line.strip():
            return
        
        # Check for agent thoughts
        if match := self.patterns['agent_thought'].search(line):
            self.log_event(self.AGENT_THOUGHT, {
                'thought': match.group(1).strip(),
                'raw_line': line
            })
            return
        
        # Check for agent actions
        if match := self.patterns['agent_action'].search(line):
            self.log_event(self.AGENT_ACTION, {
                'action': match.group(1).strip(),
                'raw_line': line
            })
            return
        
        # Check for observations
        if match := self.patterns['observation'].search(line):
            self.log_event(self.OBSERVATION, {
                'observation': match.group(1).strip(),
                'raw_line': line
            })
            return
        
        # Check for final answers
        if match := self.patterns['final_answer'].search(line):
            self.log_event(self.FINAL_ANSWER, {
                'answer': match.group(1).strip(),
                'raw_line': line
            })
            return
        
        # Check for agent started
        if match := self.patterns['agent_started'].search(line):
            if '🤖 Agent Started' in line or 'Agent:' in line:
                self.log_event(self.AGENT_THOUGHT, {
                    'agent': match.group(1).strip(),
                    'event': 'started',
                    'raw_line': line
                })
                return
        
        # Check for task info
        if match := self.patterns['task'].search(line):
            self.log_event(self.TASK_START, {
                'task': match.group(1).strip(),
                'raw_line': line
            })
            return
        
        # Log significant lines that don't match patterns
        if any(keyword in line for keyword in ['✅', '📋', '🚀', 'Status:', 'ERROR', 'WARNING']):
            self.log_event(self.RAW_LOG, {
                'message': line.strip(),
                'level': 'INFO'
            })
    
    def parse_output(self, output: str):
        """
        Parse complete CrewAI output and create events.
        
        Args:
            output: Complete stdout/stderr output to parse
        """
        lines = output.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for multi-line patterns (CrewAI uses box drawing)
            if 'Final Answer' in line and i + 1 < len(lines):
                # Collect all lines until we hit the closing box
                answer_lines = []
                j = i + 1
                while j < len(lines) and '╰' not in lines[j]:
                    if '│' in lines[j]:
                        # Extract content between the box characters
                        content = lines[j].strip('│').strip()
                        if content:
                            answer_lines.append(content)
                    j += 1
                
                if answer_lines:
                    self.log_event(self.FINAL_ANSWER, {
                        'answer': ' '.join(answer_lines),
                        'raw_lines': lines[i:j+1]
                    })
                    i = j
                    continue
            
            # Check for Agent Started with multi-line
            if '🤖 Agent Started' in line and i + 1 < len(lines):
                # Look for agent name in following lines
                j = i + 1
                while j < len(lines) and j < i + 5:
                    if 'Agent:' in lines[j]:
                        agent_match = self.patterns['agent_started'].search(lines[j])
                        if agent_match:
                            self.log_event(self.AGENT_THOUGHT, {
                                'agent': agent_match.group(1).strip(),
                                'event': 'started'
                            })
                            i = j
                            break
                    j += 1
            
            # Regular single-line parsing
            self.parse_line(line)
            i += 1
    
    def create_step_callback(self) -> Callable:
        """
        Create a callback for agent steps.
        
        Returns:
            Callback function for CrewAI step_callback
        """
        def callback(step_output):
            # Log whatever data we can extract
            data = {
                'type': type(step_output).__name__,
                'output': getattr(step_output, 'output', None),
                'log': getattr(step_output, 'log', None),
                'return_values': getattr(step_output, 'return_values', None),
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            if data:
                self.log_event('agent_step', data)
            
        return callback
    
    def create_task_callback(self) -> Callable:
        """
        Create a callback for task completion.
        
        Returns:
            Callback function for CrewAI task_callback
        """
        def callback(task_output):
            data = {
                'task_id': str(getattr(task_output, 'id', 'unknown')),
                'description': getattr(task_output, 'description', None),
                'result': getattr(task_output, 'result', None),
                'agent': getattr(task_output, 'agent', None),
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            self.log_event(self.TASK_COMPLETE, data)
            
        return callback
    
    def get_all_events(self) -> List[Dict[str, Any]]:
        """
        Get all collected events.
        
        Returns:
            List of all events collected during execution
        """
        return self.events.copy()