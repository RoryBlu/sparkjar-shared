"""
SparkJar Memory Tool for CrewAI - Registry Version with MCP Discovery.

This version uses the MCP Registry to discover and connect to the memory service.
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

class MemoryConfig(BaseModel):
    """Configuration for Memory Service access via MCP Registry."""
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

class SJMemoryToolInput(BaseModel):
    """Input schema for SJMemoryTool."""
    query: str = Field(
        description="JSON string with action and params. Example: {\"action\": \"create_entity\", \"params\": {\"name\": \"John Doe\", \"entity_type\": \"person\"}}"
    )

class SJMemoryTool(BaseTool):
    """
    SparkJar Memory Tool with MCP Registry discovery.
    
    This tool discovers the memory service through the MCP Registry
    and properly authenticates all requests.
    
    Actions:
    - create_entity: Create new entity (params: name, entity_type, metadata)
    - add_observation: Add observation to entity (params: entity_id, observation, observation_type)
    - create_relationship: Link entities (params: source_id, target_id, relationship_type)
    - search_entities: Search entities (params: query, entity_type, limit)
    - get_entity: Get entity details (params: entity_id)
    """
    
    name: str = "sj_memory"
    description: str = """Memory management via MCP Registry. Pass JSON with 'action' and 'params'.
    
    Actions:
    - create_entity: {"action": "create_entity", "params": {"name": "John Doe", "entity_type": "person"}}
    - search_entities: {"action": "search_entities", "params": {"query": "tech companies", "limit": 10}}
    - add_observation: {"action": "add_observation", "params": {"entity_id": "uuid", "observation": "Works at TechCorp"}}
    """
    args_schema: Type[BaseModel] = SJMemoryToolInput
    
    config: MemoryConfig = Field(default_factory=MemoryConfig)
    
    def __init__(self, config: Optional[MemoryConfig] = None):
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
    
    async def _discover_memory_service(self) -> Optional[str]:
        """Discover memory service URL from MCP Registry."""
        # Check cache first
        if (self._service_url and 
            self._service_discovered_at and 
            (datetime.utcnow() - self._service_discovered_at).seconds < self.config.cache_ttl):
            return self._service_url
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {self._generate_jwt_token()}"}
                
                # Query registry for memory services
                response = await client.get(
                    f"{self.config.mcp_registry_url}/registry/services",
                    headers=headers,
                    params={"service_type": "memory"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    services = data.get("services", [])
                    
                    # Find the memory service
                    for service in services:
                        if (service.get("service_type") == "memory" and
                            service.get("status") == "active"):
                            # Prefer public URL over internal
                            self._service_url = service.get("base_url") or service.get("internal_url")
                            self._service_discovered_at = datetime.utcnow()
                            logger.info(f"Discovered memory service at: {self._service_url}")
                            return self._service_url
                
                logger.warning("No active memory service found in registry")
                
        except Exception as e:
            logger.error(f"Failed to discover memory service: {e}")
        
        # Fallback to known URL if discovery fails
        self._service_url = "https://memory-external-development.up.railway.app"
        self._service_discovered_at = datetime.utcnow()
        logger.warning(f"Using fallback memory service URL: {self._service_url}")
        return self._service_url
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized with discovered service URL."""
        if self._client is None:
            service_url = await self._discover_memory_service()
            if not service_url:
                raise RuntimeError("Failed to discover memory service")
            
            self._client = httpx.AsyncClient(
                base_url=service_url,
                timeout=httpx.Timeout(self.config.timeout),
                headers={
                    "Authorization": f"Bearer {self._generate_jwt_token()}",
                    "User-Agent": "SparkJar-CrewAI-MemoryTool/Registry",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    def _run(self, query: str) -> str:
        """
        Execute memory operations based on JSON query input.
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
                return f"Error: Invalid JSON. Expected format: {{\"action\": \"create_entity\", \"params\": {{...}}}}"
            
            if not action:
                return f"Error: Missing 'action' field. Available: create_entity, add_observation, create_relationship, search_entities, get_entity"
            
            # Map actions to methods
            actions = {
                "create_entity": self._create_entity,
                "add_observation": self._add_observation,
                "create_relationship": self._create_relationship,
                "search_entities": self._search_entities,
                "get_entity": self._get_entity,
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
            logger.error(f"Unexpected error in memory tool: {e}")
            return f"Error: {str(e)}"
    
    async def _create_entity(self, 
                           name: str,
                           entity_type: str,
                           metadata: Optional[Dict[str, Any]] = None,
                           **kwargs) -> Dict[str, Any]:
        """Create a new entity."""
        try:
            client = await self._ensure_client()
            
            payload = {
                "name": name,
                "entity_type": entity_type,
                "metadata": metadata or {}
            }
            
            response = await client.post("/memory/entities", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "entity_id": data.get("entity_id"),
                    "entity": data,
                    "message": f"Created {entity_type} entity: {name}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create entity: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error creating entity: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _add_observation(self,
                              entity_id: str,
                              observation: str,
                              observation_type: str = "general",
                              metadata: Optional[Dict[str, Any]] = None,
                              **kwargs) -> Dict[str, Any]:
        """Add an observation to an entity."""
        try:
            client = await self._ensure_client()
            
            payload = {
                "entity_id": entity_id,
                "observation_type": observation_type,
                "value": {
                    "content": observation,
                    "metadata": metadata or {}
                }
            }
            
            response = await client.post("/memory/observations", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "observation_id": data.get("observation_id"),
                    "message": f"Added observation to entity {entity_id}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add observation: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error adding observation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_relationship(self,
                                  source_id: str,
                                  target_id: str,
                                  relationship_type: str,
                                  metadata: Optional[Dict[str, Any]] = None,
                                  **kwargs) -> Dict[str, Any]:
        """Create a relationship between two entities."""
        try:
            client = await self._ensure_client()
            
            payload = {
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "relationship_type": relationship_type,
                "metadata": metadata or {}
            }
            
            response = await client.post("/memory/relationships", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "relationship_id": data.get("relationship_id"),
                    "message": f"Created {relationship_type} relationship"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create relationship: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _search_entities(self,
                              query: str,
                              entity_type: Optional[str] = None,
                              limit: int = 10,
                              **kwargs) -> Dict[str, Any]:
        """Search for entities."""
        try:
            client = await self._ensure_client()
            
            params = {
                "query": query,
                "limit": limit
            }
            if entity_type:
                params["entity_type"] = entity_type
            
            response = await client.get("/memory/search", params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "results": data.get("results", []),
                    "count": len(data.get("results", [])),
                    "query": query
                }
            else:
                return {
                    "success": False,
                    "error": f"Search failed: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error searching entities: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_entity(self,
                         entity_id: str,
                         include_observations: bool = True,
                         **kwargs) -> Dict[str, Any]:
        """Get entity details."""
        try:
            client = await self._ensure_client()
            
            params = {"include_observations": include_observations}
            response = await client.get(f"/memory/entities/{entity_id}", params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "entity": data,
                    "observation_count": len(data.get("observations", []))
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get entity: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error getting entity: {e}")
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