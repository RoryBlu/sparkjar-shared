"""
SparkJar Memory Tool for CrewAI - Hierarchical Version.

This enhanced version supports hierarchical memory access, enabling synths to
access their synth_class templates and optionally client-level knowledge.
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
import asyncio
try:
    import nest_asyncio
    # Apply nest_asyncio to allow nested event loops
    nest_asyncio.apply()
except ImportError:
    # If nest_asyncio is not available, we'll handle it differently
    pass

logger = logging.getLogger(__name__)

class HierarchicalMemoryConfig(BaseModel):
    """Configuration for Hierarchical Memory Service access."""
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
    
    # Hierarchical access configuration
    enable_hierarchy: bool = Field(
        default=True,
        description="Enable hierarchical memory access by default"
    )
    include_synth_class: bool = Field(
        default=True,
        description="Include synth_class memories in searches"
    )
    include_client: bool = Field(
        default=False,
        description="Include client-level memories in searches"
    )
    enable_cross_context: bool = Field(
        default=False,
        description="Enable explicit cross-context memory access"
    )

class HierarchicalMemoryToolInput(BaseModel):
    """Input schema for Hierarchical Memory Tool."""
    query: str = Field(
        description="JSON string with action and params. Supports hierarchy options."
    )

class SJMemoryToolHierarchical(BaseTool):
    """
    SparkJar Memory Tool with Hierarchical Access Support.
    
    This enhanced tool provides access to memories across multiple contexts:
    - Own memories (synth's personal experiences)
    - Synth_class templates (inherited procedures and knowledge)
    - Client-level knowledge (organizational policies, if permitted)
    
    Enhanced Actions:
    - search_entities: Now supports hierarchical search
    - search_hierarchical: Dedicated hierarchical search with fine control
    - search_templates: Search specifically for synth_class templates
    - access_cross_context: Explicitly access another context's memories
    
    Standard Actions (unchanged):
    - create_entity: Create new entity
    - add_observation: Add observation to entity
    - create_relationship: Link entities
    - get_entity: Get entity details
    
    Examples:
    - Search with hierarchy: {"action": "search_entities", "params": {"query": "blog procedures", "include_hierarchy": true}}
    - Search templates only: {"action": "search_templates", "params": {"query": "writing SOP"}}
    - Cross-context access: {"action": "access_cross_context", "params": {"target_type": "synth_class", "target_id": "24", "query": "procedures"}}
    """
    
    name: str = "sj_memory_hierarchical"
    description: str = """Enhanced memory management with hierarchical access. Pass JSON with 'action' and 'params'.
    
    Key Features:
    - Access your own memories and inherited templates
    - Search across memory contexts (own, synth_class, client)
    - Identify which context memories come from
    
    Enhanced Actions:
    - search_entities: {"action": "search_entities", "params": {"query": "procedures", "include_hierarchy": true}}
    - search_hierarchical: {"action": "search_hierarchical", "params": {"query": "blog SOP", "include_synth_class": true, "include_client": false}}
    - search_templates: {"action": "search_templates", "params": {"query": "writing guidelines"}}
    """
    args_schema: Type[BaseModel] = HierarchicalMemoryToolInput
    
    config: HierarchicalMemoryConfig = Field(default_factory=HierarchicalMemoryConfig)
    
    def __init__(self, config: Optional[HierarchicalMemoryConfig] = None):
        """Initialize with optional configuration."""
        super().__init__()
        if config:
            self.config = config
        self._service_url = None
        self._service_discovered_at = None
        self._client = None
        
        # Actor context (to be set when tool is initialized for a specific actor)
        self._actor_type = None
        self._actor_id = None
        self._client_id = None
    
    def set_actor_context(self, actor_type: str, actor_id: Union[str, UUID], client_id: Union[str, UUID]):
        """
        Set the actor context for this tool instance.
        This should be called when the tool is initialized for a specific synth.
        """
        self._actor_type = actor_type
        self._actor_id = str(actor_id)
        self._client_id = str(client_id)
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token with hierarchy permissions."""
        payload = {
            "sub": "sparkjar-crew-tool",
            "scopes": ["sparkjar_internal"],
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "iss": "sparkjar-crew",
            # Add hierarchy permissions
            "hierarchy_enabled": self.config.enable_hierarchy,
            "cross_context_enabled": self.config.enable_cross_context
        }
        
        # Include actor context if set
        if self._actor_type and self._actor_id and self._client_id:
            payload.update({
                "actor_type": self._actor_type,
                "actor_id": self._actor_id,
                "client_id": self._client_id
            })
        
        return jwt.encode(payload, self.config.api_secret_key, algorithm="HS256")
    
    async def _discover_memory_service(self) -> Optional[str]:
        """Discover memory service URL from MCP Registry."""
        # Check cache first
        if (self._service_url and 
            self._service_discovered_at and 
            (datetime.utcnow() - self._service_discovered_at).seconds < self.config.cache_ttl):
            return self._service_url
        
        # First try environment variable (more reliable for local dev)
        env_url = os.getenv("MEMORY_API_URL")
        if env_url:
            self._service_url = env_url
            self._service_discovered_at = datetime.utcnow()
            logger.info(f"Using memory service URL from environment: {self._service_url}")
            return self._service_url
        
        # Then try MCP Registry discovery
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
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
                    
                    # Find the memory service (prefer hierarchical version)
                    for service in services:
                        if (service.get("service_type") == "memory" and
                            service.get("status") == "active"):
                            # Check for hierarchical support
                            features = service.get("metadata", {}).get("features", [])
                            if "hierarchical" in features:
                                logger.info(f"Found hierarchical memory service")
                            
                            self._service_url = service.get("base_url") or service.get("internal_url")
                            self._service_discovered_at = datetime.utcnow()
                            logger.info(f"Discovered memory service at: {self._service_url}")
                            return self._service_url
                
                logger.warning("No active memory service found in registry")
                
        except Exception as e:
            logger.debug(f"MCP Registry discovery failed (using fallback): {e}")
        
        # Fallback to known URL if discovery fails
        fallback_url = "https://memory-external-development.up.railway.app"
        self._service_url = fallback_url
        self._service_discovered_at = datetime.utcnow()
        logger.info(f"Using fallback memory service URL: {self._service_url}")
        return self._service_url
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized with discovered service URL."""
        if self._client is None:
            service_url = await self._discover_memory_service()
            if not service_url:
                raise RuntimeError("Failed to discover memory service")
            
            # Create client with increased timeout and retry logic
            timeout = httpx.Timeout(
                connect=10.0,  # Connection timeout
                read=30.0,     # Read timeout
                write=10.0,    # Write timeout
                pool=10.0      # Pool timeout
            )
            
            self._client = httpx.AsyncClient(
                base_url=service_url,
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self._generate_jwt_token()}",
                    "User-Agent": "SparkJar-CrewAI-HierarchicalMemoryTool/2.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
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
                return f"Error: Invalid JSON. Expected format: {{\"action\": \"search_entities\", \"params\": {{...}}}}"
            
            if not action:
                return f"Error: Missing 'action' field. Available: search_entities, search_hierarchical, search_templates, access_cross_context, create_entity, add_observation, create_relationship, get_entity"
            
            # Map actions to methods (including new hierarchical actions)
            actions = {
                # Enhanced search actions
                "search_entities": self._search_entities_hierarchical,
                "search_hierarchical": self._search_hierarchical,
                "search_templates": self._search_templates,
                "access_cross_context": self._access_cross_context,
                # Standard actions (unchanged)
                "create_entity": self._create_entity,
                "add_observation": self._add_observation,
                "create_relationship": self._create_relationship,
                "get_entity": self._get_entity,
            }
            
            if action not in actions:
                return f"Error: Unknown action '{action}'. Available: {list(actions.keys())}"
            
            # Run async operation in sync context
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, use run_coroutine_threadsafe
                import concurrent.futures
                import threading
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(actions[action](**params))
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    result = future.result()
            except RuntimeError:
                # No event loop running, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(actions[action](**params))
                finally:
                    loop.close()
            
            if result.get("success"):
                return json.dumps(result, indent=2)
            else:
                return f"Error: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            logger.error(f"Unexpected error in hierarchical memory tool: {e}")
            return f"Error: {str(e)}"
    
    async def _search_entities_hierarchical(self,
                                          query: str,
                                          entity_type: Optional[Union[str, List[str]]] = None,
                                          limit: int = 10,
                                          include_hierarchy: Optional[bool] = None,
                                          **kwargs) -> Dict[str, Any]:
        """
        Enhanced search with optional hierarchical access.
        
        When include_hierarchy is True, searches across:
        - Your own memories
        - Synth_class templates (if you're a synth)
        - Client-level knowledge (if configured)
        """
        try:
            client = await self._ensure_client()
            
            # Use config default if not specified
            if include_hierarchy is None:
                include_hierarchy = self.config.enable_hierarchy
            
            params = {
                "query": query,
                "limit": limit,
                "include_hierarchy": include_hierarchy
            }
            
            if entity_type:
                if isinstance(entity_type, str):
                    params["entity_types"] = [entity_type]
                else:
                    params["entity_types"] = entity_type
            
            response = await client.get("/memory/search", params=params)
            
            if response.status_code == 200:
                data = response.json()
                results = data if isinstance(data, list) else data.get("results", [])
                
                # Process results to highlight access context
                enhanced_results = []
                for result in results:
                    # Add human-readable access source if present
                    if "access_source" in result:
                        if result["access_source"] == "inherited_template":
                            result["_context_note"] = "From your synth_class template"
                        elif result["access_source"] == "organizational":
                            result["_context_note"] = "From organizational knowledge"
                        elif result["access_source"] == "own":
                            result["_context_note"] = "From your personal memories"
                    
                    enhanced_results.append(result)
                
                return {
                    "success": True,
                    "results": enhanced_results,
                    "count": len(enhanced_results),
                    "query": query,
                    "hierarchical_search": include_hierarchy,
                    "contexts_searched": self._get_contexts_searched(include_hierarchy)
                }
            else:
                return {
                    "success": False,
                    "error": f"Search failed: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error in hierarchical search: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _search_hierarchical(self,
                                  query: str,
                                  entity_types: Optional[List[str]] = None,
                                  include_synth_class: Optional[bool] = None,
                                  include_client: Optional[bool] = None,
                                  limit: int = 10,
                                  **kwargs) -> Dict[str, Any]:
        """
        Dedicated hierarchical search with fine-grained control.
        
        Allows explicit control over which memory contexts to search.
        """
        try:
            client = await self._ensure_client()
            
            # Use config defaults if not specified
            if include_synth_class is None:
                include_synth_class = self.config.include_synth_class
            if include_client is None:
                include_client = self.config.include_client
            
            params = {
                "query": query,
                "limit": limit,
                "include_synth_class": include_synth_class,
                "include_client": include_client
            }
            
            if entity_types:
                params["entity_types"] = entity_types
            
            response = await client.post("/memory/hierarchical-search", params=params)
            
            if response.status_code == 200:
                data = response.json()
                results = data if isinstance(data, list) else data.get("results", [])
                
                # Group results by access context
                results_by_context = {
                    "own": [],
                    "synth_class": [],
                    "client": []
                }
                
                for result in results:
                    context = result.get("access_context", "own")
                    if context == "synth_class":
                        results_by_context["synth_class"].append(result)
                    elif context == "client":
                        results_by_context["client"].append(result)
                    else:
                        results_by_context["own"].append(result)
                
                return {
                    "success": True,
                    "results": results,
                    "results_by_context": results_by_context,
                    "count": len(results),
                    "query": query,
                    "contexts": {
                        "own_memories": len(results_by_context["own"]),
                        "template_memories": len(results_by_context["synth_class"]),
                        "organizational_memories": len(results_by_context["client"])
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Hierarchical search failed: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error in dedicated hierarchical search: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _search_templates(self,
                               query: str,
                               limit: int = 10,
                               **kwargs) -> Dict[str, Any]:
        """
        Search specifically for synth_class templates.
        
        Useful for finding procedures, SOPs, and guidelines from your class.
        """
        try:
            # Use hierarchical search but only include synth_class
            result = await self._search_hierarchical(
                query=query,
                entity_types=["procedure", "template", "guide", "sop", "procedure_template"],
                include_synth_class=True,
                include_client=False,
                limit=limit
            )
            
            if result.get("success"):
                # Filter to only template results
                template_results = result.get("results_by_context", {}).get("synth_class", [])
                
                return {
                    "success": True,
                    "templates": template_results,
                    "count": len(template_results),
                    "query": query,
                    "message": f"Found {len(template_results)} templates from your synth_class"
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error searching templates: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _access_cross_context(self,
                                   target_type: str,
                                   target_id: str,
                                   query: Optional[str] = None,
                                   permission_check: bool = True,
                                   **kwargs) -> Dict[str, Any]:
        """
        Explicitly access memories from another context.
        
        Requires appropriate permissions. Useful for:
        - Accessing specific synth_class procedures
        - Viewing another synth's experiences (if permitted)
        - Accessing client-wide knowledge bases
        """
        try:
            if not self.config.enable_cross_context:
                return {
                    "success": False,
                    "error": "Cross-context access is not enabled in configuration"
                }
            
            client = await self._ensure_client()
            
            payload = {
                "target_actor_type": target_type,
                "target_actor_id": target_id,
                "query": query,
                "permission_check": permission_check
            }
            
            response = await client.post("/memory/cross-context-access", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                results = data if isinstance(data, list) else data.get("results", [])
                
                return {
                    "success": True,
                    "results": results,
                    "count": len(results),
                    "target_context": f"{target_type}:{target_id}",
                    "cross_context_access": True,
                    "message": f"Accessed {len(results)} memories from {target_type}:{target_id}"
                }
            elif response.status_code == 403:
                return {
                    "success": False,
                    "error": "Permission denied for cross-context access"
                }
            else:
                return {
                    "success": False,
                    "error": f"Cross-context access failed: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error in cross-context access: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_contexts_searched(self, include_hierarchy: bool) -> List[str]:
        """Get list of contexts that were searched."""
        if not include_hierarchy:
            return ["own"]
        
        contexts = ["own"]
        if self._actor_type == "synth" and self.config.include_synth_class:
            contexts.append("synth_class")
        if self.config.include_client:
            contexts.append("client")
        
        return contexts
    
    # Standard methods remain unchanged but included for completeness
    async def _create_entity(self, 
                           name: str,
                           entity_type: str,
                           metadata: Optional[Dict[str, Any]] = None,
                           **kwargs) -> Dict[str, Any]:
        """Create a new entity with retry logic."""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                client = await self._ensure_client()
                
                payload = [{
                    "name": name,
                    "entityType": entity_type,
                    "metadata": metadata or {},
                    "observations": []
                }]
                
                logger.debug(f"Creating entity: {name} (type: {entity_type}, attempt {attempt + 1}/{max_retries})")
                
                response = await client.post("/memory/entities", json=payload)
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    entity_data = data[0] if isinstance(data, list) else data
                    return {
                        "success": True,
                        "entity_id": entity_data.get("id"),
                        "entity": entity_data,
                        "message": f"Created {entity_type} entity: {name}"
                    }
                elif response.status_code == 409:
                    # Entity already exists
                    return {
                        "success": True,
                        "message": f"Entity already exists: {name}",
                        "existing": True
                    }
                else:
                    error_msg = f"Failed to create entity (status {response.status_code}): {response.text}"
                    logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                    
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    
                    return {
                        "success": False,
                        "error": error_msg
                    }
                    
            except httpx.ConnectError as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    # Reset client to force reconnection
                    self._client = None
                    continue
                return {
                    "success": False,
                    "error": f"Connection error after {max_retries} attempts: {str(e)}"
                }
            except httpx.TimeoutException as e:
                logger.warning(f"Timeout error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                return {
                    "success": False,
                    "error": f"Timeout error after {max_retries} attempts: {str(e)}"
                }
            except Exception as e:
                logger.error(f"Unexpected error creating entity: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def _add_observation(self,
                              entity_name: str,
                              observation: str,
                              observation_type: str = "general",
                              source: str = "crew_tool",
                              **kwargs) -> Dict[str, Any]:
        """Add an observation to an entity (enhanced for hierarchical context)."""
        try:
            client = await self._ensure_client()
            
            payload = [{
                "entityName": entity_name,
                "contents": [{
                    "type": observation_type,
                    "value": observation,
                    "source": source
                }]
            }]
            
            response = await client.post("/memory/observations", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "message": f"Added observation to entity {entity_name}",
                    "observation_added": observation
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
                                  from_entity_name: str,
                                  to_entity_name: str,
                                  relationship_type: str,
                                  metadata: Optional[Dict[str, Any]] = None,
                                  **kwargs) -> Dict[str, Any]:
        """Create a relationship between two entities."""
        try:
            client = await self._ensure_client()
            
            payload = [{
                "from_entity_name": from_entity_name,
                "to_entity_name": to_entity_name,
                "relationType": relationship_type,
                "metadata": metadata or {}
            }]
            
            response = await client.post("/memory/relations", json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "message": f"Created {relationship_type} relationship between {from_entity_name} and {to_entity_name}"
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
    
    async def _get_entity(self,
                         entity_name: str,
                         include_hierarchy: Optional[bool] = None,
                         **kwargs) -> Dict[str, Any]:
        """Get entity details (enhanced with hierarchy option)."""
        try:
            client = await self._ensure_client()
            
            if include_hierarchy is None:
                include_hierarchy = self.config.enable_hierarchy
            
            params = {
                "entity_names": [entity_name],
                "include_hierarchy": include_hierarchy
            }
            
            response = await client.get("/memory/entities", params=params)
            
            if response.status_code == 200:
                data = response.json()
                entities = data if isinstance(data, list) else data.get("results", [])
                
                if entities:
                    entity = entities[0]
                    # Add context information if available
                    if "access_source" in entity:
                        entity["_retrieved_from"] = entity["access_source"]
                    
                    return {
                        "success": True,
                        "entity": entity,
                        "found": True
                    }
                else:
                    return {
                        "success": True,
                        "found": False,
                        "message": f"Entity '{entity_name}' not found"
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

# Convenience function to create a hierarchical memory tool for a specific actor
def create_hierarchical_memory_tool(
    actor_type: str,
    actor_id: Union[str, UUID],
    client_id: Union[str, UUID],
    config: Optional[HierarchicalMemoryConfig] = None
) -> SJMemoryToolHierarchical:
    """
    Create a hierarchical memory tool configured for a specific actor.
    
    Args:
        actor_type: Type of actor (synth, human, etc.)
        actor_id: ID of the actor
        client_id: ID of the client
        config: Optional configuration overrides
    
    Returns:
        Configured hierarchical memory tool
    """
    tool = SJMemoryToolHierarchical(config=config)
    tool.set_actor_context(actor_type, actor_id, client_id)
    return tool