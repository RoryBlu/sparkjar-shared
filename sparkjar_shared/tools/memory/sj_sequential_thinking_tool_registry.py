"""
SparkJar Sequential Thinking Tool for CrewAI - Registry Version with MCP Discovery.

This version uses the MCP Registry to discover and connect to the thinking service.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Union, Type
from uuid import UUID
import httpx
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
from datetime import datetime, timedelta
import jwt
import os

logger = logging.getLogger(__name__)

class ThinkingConfig(BaseModel):
    """Configuration for Sequential Thinking Service access via MCP Registry."""
    mcp_registry_url: str = Field(
        default="https://mcp-registry-development.up.railway.app",
        description="MCP Registry URL for service discovery"
    )
    api_secret_key: str = Field(
        default=os.getenv("API_SECRET_KEY", ""),
        description="Secret key for JWT generation"
    )
    timeout: int = Field(default=10, description="Request timeout in seconds")
    cache_ttl: int = Field(default=300, description="Service discovery cache TTL in seconds")

class SJSequentialThinkingToolInput(BaseModel):
    """Input schema for SJSequentialThinkingTool."""
    query: str = Field(
        description="JSON string with action and params. Example: {\"action\": \"create_session\", \"params\": {\"client_user_id\": \"uuid\", \"session_name\": \"Strategy Planning\"}}"
    )

class SJSequentialThinkingTool(BaseTool):
    """
    SparkJar Sequential Thinking Tool with MCP Registry discovery.
    
    This tool discovers the thinking service through the MCP Registry
    and properly authenticates all requests.
    
    Actions:
    - create_session: Start thinking session (params: client_user_id, session_name, problem_statement)
    - add_thought: Add thought to session (params: session_id, thought_content, metadata)
    - get_session: Get session with thoughts (params: session_id)
    - complete_session: Complete session (params: session_id, conclusion)
    """
    
    name: str = "sj_sequential_thinking"
    description: str = """Sequential thinking via MCP Registry. Pass JSON with 'action' and 'params'.
    
    Actions:
    - create_session: {"action": "create_session", "params": {"client_user_id": "uuid", "session_name": "Research Plan"}}
    - add_thought: {"action": "add_thought", "params": {"session_id": "uuid", "thought_content": "First, we need to..."}}
    - get_session: {"action": "get_session", "params": {"session_id": "uuid"}}
    """
    args_schema: Type[BaseModel] = SJSequentialThinkingToolInput
    
    config: ThinkingConfig = Field(default_factory=ThinkingConfig)
    
    def __init__(self, config: Optional[ThinkingConfig] = None):
        """Initialize with optional configuration."""
        super().__init__()
        if config:
            self.config = config
        self._service_url = None
        self._service_discovered_at = None
        self._client = None
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for authentication."""
        payload = {
            "sub": "sparkjar-crew-tool",
            "scopes": ["sparkjar_internal"],
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "iss": "sparkjar-crew"
        }
        return jwt.encode(payload, self.config.api_secret_key, algorithm="HS256")
    
    async def _discover_thinking_service(self) -> Optional[str]:
        """Discover thinking service URL from MCP Registry."""
        # Check cache first
        if (self._service_url and 
            self._service_discovered_at and 
            (datetime.utcnow() - self._service_discovered_at).seconds < self.config.cache_ttl):
            return self._service_url
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {self._generate_jwt_token()}"}
                
                # Query registry for thinking services
                response = await client.get(
                    f"{self.config.mcp_registry_url}/registry/services",
                    headers=headers,
                    params={"service_type": "thinking"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    services = data.get("services", [])
                    
                    # Find the thinking service
                    for service in services:
                        if (service.get("service_type") == "thinking" and
                            service.get("status") == "active"):
                            # Prefer public URL over internal
                            self._service_url = service.get("base_url") or service.get("internal_url")
                            # Thinking service is part of memory service
                            if not self._service_url.endswith("/thinking"):
                                self._service_url = f"{self._service_url}/thinking"
                            self._service_discovered_at = datetime.utcnow()
                            logger.info(f"Discovered thinking service at: {self._service_url}")
                            return self._service_url
                
                logger.warning("No active thinking service found in registry")
                
        except Exception as e:
            logger.error(f"Failed to discover thinking service: {e}")
        
        # Fallback - thinking is part of memory service
        self._service_url = "https://memory-external-development.up.railway.app/thinking"
        self._service_discovered_at = datetime.utcnow()
        logger.warning(f"Using fallback thinking service URL: {self._service_url}")
        return self._service_url
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized with discovered service URL."""
        if self._client is None:
            service_url = await self._discover_thinking_service()
            if not service_url:
                raise RuntimeError("Failed to discover thinking service")
            
            self._client = httpx.AsyncClient(
                base_url=service_url,
                timeout=httpx.Timeout(self.config.timeout),
                headers={
                    "Authorization": f"Bearer {self._generate_jwt_token()}",
                    "User-Agent": "SparkJar-CrewAI-ThinkingTool/Registry",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    def _run(self, query: str) -> str:
        """
        Execute thinking operations based on JSON query input.
        Runs async operations in sync context for CrewAI compatibility.
        """
        import asyncio
        
        try:
            # Parse JSON query from CrewAI
            try:
                data = json.loads(query)
                action = data.get("action")
                params = data.get("params", {})
            except json.JSONDecodeError:
                return f"Error: Invalid JSON. Expected format: {{\"action\": \"create_session\", \"params\": {{...}}}}"
            
            if not action:
                return f"Error: Missing 'action' field. Available: create_session, add_thought, get_session, complete_session"
            
            # Map actions to methods
            actions = {
                "create_session": self._create_session,
                "add_thought": self._add_thought,
                "get_session": self._get_session,
                "complete_session": self._complete_session,
            }
            
            if action not in actions:
                return f"Error: Unknown action '{action}'. Available: {list(actions.keys())}"
            
            # Run async operation in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(actions[action](**params))
                if result.get("success"):
                    return json.dumps(result, indent=2)
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Unexpected error in thinking tool: {e}")
            return f"Error: {str(e)}"
    
    async def _create_session(self,
                            client_user_id: str,
                            session_name: Optional[str] = None,
                            problem_statement: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None,
                            **kwargs) -> Dict[str, Any]:
        """Create a new thinking session."""
        try:
            client = await self._ensure_client()
            
            payload = {
                "client_user_id": client_user_id,
                "session_name": session_name,
                "problem_statement": problem_statement,
                "metadata": metadata or {}
            }
            
            response = await client.post("/sessions", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "session_id": data.get("session_id"),
                    "session": data,
                    "message": f"Created thinking session: {session_name or 'Untitled'}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create session: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _add_thought(self,
                          session_id: str,
                          thought_content: str,
                          metadata: Optional[Dict[str, Any]] = None,
                          **kwargs) -> Dict[str, Any]:
        """Add a thought to a session."""
        try:
            client = await self._ensure_client()
            
            payload = {
                "thought_content": thought_content,
                "metadata": metadata or {}
            }
            
            response = await client.post(f"/sessions/{session_id}/thoughts", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "thought_id": data.get("thought_id"),
                    "thought_number": data.get("thought_number"),
                    "thought": data,
                    "message": f"Added thought #{data.get('thought_number', 'N/A')}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add thought: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error adding thought: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_session(self,
                          session_id: str,
                          include_thoughts: bool = True,
                          **kwargs) -> Dict[str, Any]:
        """Get session details with all thoughts."""
        try:
            client = await self._ensure_client()
            
            params = {"include_thoughts": include_thoughts}
            response = await client.get(f"/sessions/{session_id}", params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "session": data,
                    "thought_count": len(data.get("thoughts", [])),
                    "session_id": session_id
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get session: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _complete_session(self,
                               session_id: str,
                               conclusion: Optional[str] = None,
                               **kwargs) -> Dict[str, Any]:
        """Mark a session as completed."""
        try:
            client = await self._ensure_client()
            
            payload = {}
            if conclusion:
                payload["conclusion"] = conclusion
            
            response = await client.post(f"/sessions/{session_id}/complete", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "session_id": session_id,
                    "status": "completed",
                    "message": "Session marked as completed"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to complete session: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error completing session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup."""
        if self._client:
            await self._client.aclose()
            self._client = None