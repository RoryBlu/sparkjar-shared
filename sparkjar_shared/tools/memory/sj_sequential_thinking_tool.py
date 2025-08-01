"""
SparkJar Sequential Thinking Tool for CrewAI.

Provides comprehensive access to the Sequential Thinking API for managing
thinking sessions, thoughts, revisions, and analysis.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Union
from uuid import UUID
import httpx
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

class ThinkingConfig(BaseModel):
    """Configuration for Sequential Thinking API access."""
    base_url: str = Field(default="http://memory-service.railway.internal:8001", description="Memory service internal URL")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    use_internal_api: bool = Field(default=True, description="Use internal API (no auth) vs external API (requires auth)")
    external_url: Optional[str] = Field(default=None, description="External API URL if using authenticated access")
    api_token: Optional[str] = Field(default=None, description="JWT token for external API access")

class SJSequentialThinkingTool(BaseTool):
    """
    SparkJar Sequential Thinking Tool for structured thought management.
    
    Supports:
    - Creating and managing thinking sessions
    - Adding thoughts with automatic numbering
    - Revising thoughts with history tracking
    - Analyzing thinking patterns
    - Session summaries and insights
    - Collaborative thinking with multiple participants
    """
    
    name: str = "sj_sequential_thinking"
    description: str = """Access SparkJar Sequential Thinking API for structured thought management.
    
    Available operations:
    - create_session: Start a new thinking session
    - add_thought: Add a thought to a session
    - revise_thought: Create a revision of an existing thought
    - get_session: Retrieve session details and all thoughts
    - list_sessions: List thinking sessions with filters
    - complete_session: Mark a session as completed
    - get_session_summary: Get AI-generated summary of a session
    - analyze_thinking_pattern: Analyze patterns in thinking process
    - search_thoughts: Search across all thoughts
    """
    
    config: ThinkingConfig = Field(default_factory=ThinkingConfig)
    
    def __init__(self, config: Optional[ThinkingConfig] = None):
        """Initialize with optional configuration."""
        super().__init__()
        if config:
            self.config = config
        self._client = None
    
    @property
    def client(self) -> httpx.Client:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            base_url = self.config.base_url if self.config.use_internal_api else self.config.external_url
            headers = {}
            if not self.config.use_internal_api and self.config.api_token:
                headers["Authorization"] = f"Bearer {self.config.api_token}"
            
            # Add thinking API prefix
            if not base_url.endswith("/thinking"):
                base_url = f"{base_url}/thinking"
            
            self._client = httpx.Client(
                base_url=base_url,
                headers=headers,
                timeout=self.config.timeout
            )
        return self._client
    
    def _run(self, 
             operation: str,
             **kwargs) -> Dict[str, Any]:
        """
        Execute thinking operations.
        
        Args:
            operation: The operation to perform
            **kwargs: Operation-specific parameters
            
        Returns:
            Dict containing operation results
        """
        logger.info(f"[SJThinking] Executing operation: {operation} with params: {kwargs}")
        
        try:
            # Map operations to methods
            operations = {
                "create_session": self._create_session,
                "add_thought": self._add_thought,
                "revise_thought": self._revise_thought,
                "get_session": self._get_session,
                "list_sessions": self._list_sessions,
                "complete_session": self._complete_session,
                "get_session_summary": self._get_session_summary,
                "analyze_thinking_pattern": self._analyze_thinking_pattern,
                "search_thoughts": self._search_thoughts,
            }
            
            if operation not in operations:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}. Available: {list(operations.keys())}"
                }
            
            return operations[operation](**kwargs)
            
        except Exception as e:
            logger.error(f"[SJThinking] Error in operation {operation}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "operation": operation
            }
    
    def _create_session(self,
                       client_user_id: str,
                       session_name: Optional[str] = None,
                       problem_statement: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None,
                       **kwargs) -> Dict[str, Any]:
        """Create a new thinking session."""
        try:
            payload = {
                "client_user_id": client_user_id,
                "session_name": session_name,
                "problem_statement": problem_statement,
                "metadata": metadata or {}
            }
            
            response = self.client.post("/sessions", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "session_id": data.get("session_id"),
                "session": data,
                "message": f"Created thinking session: {session_name or 'Untitled'}"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error creating session: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _add_thought(self,
                    session_id: str,
                    thought_content: str,
                    metadata: Optional[Dict[str, Any]] = None,
                    **kwargs) -> Dict[str, Any]:
        """Add a thought to a session."""
        try:
            payload = {
                "thought_content": thought_content,
                "metadata": metadata or {}
            }
            
            response = self.client.post(f"/sessions/{session_id}/thoughts", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "thought_id": data.get("thought_id"),
                "thought_number": data.get("thought_number"),
                "thought": data,
                "message": f"Added thought #{data.get('thought_number', 'N/A')}"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error adding thought: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _revise_thought(self,
                       thought_id: str,
                       revised_content: str,
                       revision_reason: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None,
                       **kwargs) -> Dict[str, Any]:
        """Create a revision of an existing thought."""
        try:
            payload = {
                "revised_content": revised_content,
                "revision_reason": revision_reason,
                "metadata": metadata or {}
            }
            
            response = self.client.post(f"/thoughts/{thought_id}/revise", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "thought_id": data.get("thought_id"),
                "revision_number": data.get("revision_number"),
                "thought": data,
                "message": f"Created revision #{data.get('revision_number', 'N/A')}"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error revising thought: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _get_session(self,
                    session_id: str,
                    include_thoughts: bool = True,
                    **kwargs) -> Dict[str, Any]:
        """Get session details with all thoughts."""
        try:
            params = {"include_thoughts": include_thoughts}
            response = self.client.get(f"/sessions/{session_id}", params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "session": data,
                "thought_count": len(data.get("thoughts", [])),
                "session_id": session_id
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error getting session: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _list_sessions(self,
                      client_user_id: Optional[str] = None,
                      status: Optional[str] = None,
                      limit: int = 20,
                      offset: int = 0,
                      **kwargs) -> Dict[str, Any]:
        """List thinking sessions with filters."""
        try:
            params = {
                "limit": limit,
                "offset": offset
            }
            if client_user_id:
                params["client_user_id"] = client_user_id
            if status:
                params["status"] = status
            
            response = self.client.get("/sessions", params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "sessions": data.get("sessions", []),
                "total": data.get("total", len(data.get("sessions", []))),
                "count": len(data.get("sessions", []))
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error listing sessions: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _complete_session(self,
                         session_id: str,
                         conclusion: Optional[str] = None,
                         **kwargs) -> Dict[str, Any]:
        """Mark a session as completed."""
        try:
            payload = {}
            if conclusion:
                payload["conclusion"] = conclusion
            
            response = self.client.post(f"/sessions/{session_id}/complete", json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "session_id": session_id,
                "status": "completed",
                "message": "Session marked as completed"
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error completing session: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _get_session_summary(self,
                            session_id: str,
                            **kwargs) -> Dict[str, Any]:
        """Get AI-generated summary of a thinking session."""
        try:
            response = self.client.get(f"/sessions/{session_id}/summary")
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "summary": data.get("summary"),
                "key_insights": data.get("key_insights", []),
                "decisions": data.get("decisions", []),
                "next_steps": data.get("next_steps", []),
                "session_id": session_id
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error getting session summary: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _analyze_thinking_pattern(self,
                                 session_id: str,
                                 **kwargs) -> Dict[str, Any]:
        """Analyze thinking patterns in a session."""
        try:
            response = self.client.get(f"/sessions/{session_id}/analysis")
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "patterns": data.get("patterns", []),
                "revision_frequency": data.get("revision_frequency"),
                "thought_progression": data.get("thought_progression"),
                "decision_points": data.get("decision_points", []),
                "session_id": session_id
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error analyzing thinking pattern: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def _search_thoughts(self,
                        query: str,
                        session_id: Optional[str] = None,
                        limit: int = 20,
                        **kwargs) -> Dict[str, Any]:
        """Search across thoughts."""
        try:
            params = {
                "query": query,
                "limit": limit
            }
            if session_id:
                params["session_id"] = session_id
            
            response = self.client.get("/thoughts/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "thoughts": data.get("thoughts", []),
                "count": len(data.get("thoughts", [])),
                "query": query
            }
            
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP error searching thoughts: {str(e)}",
                "details": getattr(e.response, 'text', None) if hasattr(e, 'response') else None
            }
    
    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if self._client:
            self._client.close()

# Example usage patterns for agents:
"""
# Create a thinking session
result = sj_thinking_tool._run(
    operation="create_session",
    client_user_id="user-uuid",
    session_name="Marketing Strategy Planning",
    problem_statement="How to increase user engagement by 50%?"
)

# Add thoughts
result = sj_thinking_tool._run(
    operation="add_thought",
    session_id="session-uuid",
    thought_content="We should analyze current user behavior patterns first.",
    metadata={"category": "analysis", "priority": "high"}
)

# Revise a thought
result = sj_thinking_tool._run(
    operation="revise_thought",
    thought_id="thought-uuid",
    revised_content="We should analyze current user behavior patterns and identify drop-off points.",
    revision_reason="Added more specific action"
)

# Get session with all thoughts
result = sj_thinking_tool._run(
    operation="get_session",
    session_id="session-uuid",
    include_thoughts=True
)

# Search thoughts
result = sj_thinking_tool._run(
    operation="search_thoughts",
    query="user engagement strategies",
    limit=10
)

# Get session summary
result = sj_thinking_tool._run(
    operation="get_session_summary",
    session_id="session-uuid"
)
"""