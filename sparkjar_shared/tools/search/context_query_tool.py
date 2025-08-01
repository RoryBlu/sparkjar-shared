
import logging
logger = logging.getLogger(__name__)

"""
Context Query Tool for SparkJar CrewAI.

Simple tool for extracting client and actor context from the database.
"""
import time
from typing import Dict, Any, Optional
from uuid import UUID

from crewai.tools import BaseTool
from sqlalchemy import select

from database.connection import get_direct_session
from database.models import ClientUsers, Clients, Synths

class ContextQueryTool(BaseTool):
    """Simple context query tool for extracting client and actor data."""
    
    name: str = "context_query"
    description: str = "Extract client and actor context from database. Pass client_user_id, actor_type, and actor_id as parameters."
    
    def _run(self, 
             query_type: str = "retrieve", 
             context_params: Dict[str, Any] = None,
             client_user_id: str = None,
             actor_type: str = None, 
             actor_id: str = None,
             **kwargs) -> Dict[str, Any]:
        """Run the context query tool synchronously."""
        # Processing context query
        
        # Initialize context_params if not provided
        if not context_params:
            context_params = {}
            
        # Prefer direct parameters over context_params dict
        if client_user_id:
            context_params["client_user_id"] = client_user_id
        if actor_type:
            context_params["actor_type"] = actor_type
        if actor_id:
            context_params["actor_id"] = actor_id
            
        # Look for context parameters in kwargs if still missing
        for key in ["client_user_id", "actor_type", "actor_id"]:
            if key not in context_params and key in kwargs:
                context_params[key] = kwargs[key]
        
        # Context params prepared
        
        # For CrewAI compatibility, check if we're already in an event loop
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # We're in an event loop - use thread executor to avoid blocking
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_async_in_thread, query_type, context_params)
                return future.result()
        except RuntimeError:
            # No event loop running - safe to use asyncio.run
            return asyncio.run(self._arun(query_type, context_params))
    
    def _run_async_in_thread(self, query_type: str, context_params: Dict[str, Any]) -> Dict[str, Any]:
        """Run async code in a separate thread to avoid event loop conflicts."""
        import asyncio
        return asyncio.run(self._arun(query_type, context_params))
    
    async def _arun(self, query_type: str, context_params: Dict[str, Any]) -> Dict[str, Any]:
        """Run the context query tool asynchronously with retry logic."""
        max_retries = 3
        session = None
        
        for attempt in range(max_retries):
            try:
                # Processing context query with params
                
                # Validate required fields
                required_fields = ["client_user_id", "actor_type", "actor_id"]
                for field in required_fields:
                    if field not in context_params:
                        raise ValueError(f"Missing required field: {field}")
                
                # Extract and validate UUIDs with better error messages
                client_user_id_str = context_params["client_user_id"]
                actor_id_str = context_params["actor_id"]
                
                # UUID strings extracted successfully
                
                try:
                    client_user_id = UUID(str(client_user_id_str).strip())
                    actor_id = UUID(str(actor_id_str).strip())
                except ValueError as e:
                    raise ValueError(f"Invalid UUID format - client_user_id: '{client_user_id_str}', actor_id: '{actor_id_str}'. Error: {e}")
                
                # Validate actor type
                actor_type = context_params["actor_type"]
                if actor_type not in ["human", "synth"]:
                    raise ValueError(f"Invalid actor_type: {actor_type}. Must be 'human' or 'synth'")
                
                # Query database with proper connection management
                try:
                    async with get_direct_session() as session:
                        # Get client context
                        client_query = select(ClientUsers, Clients).join(
                            Clients, ClientUsers.clients_id == Clients.id
                        ).where(ClientUsers.id == client_user_id)
                        
                        client_result = await session.execute(client_query)
                        client_row = client_result.first()
                        if not client_row:
                            raise ValueError(f"Client user not found: {client_user_id}")
                        
                        client_user, client = client_row
                        
                        # Get actor context based on type
                        if actor_type == "human":
                            # For human actors, the actor_id should match client_user_id
                            if actor_id != client_user_id:
                                raise ValueError("For human actors, actor_id must match client_user_id")
                            actor_context = {
                                "id": str(client_user.id),
                                "type": "human",
                                "name": client_user.preferred_name or client_user.full_name,
                                "email": client_user.email
                            }
                        else:  # synth
                            synth_query = select(Synths).where(Synths.id == actor_id)
                            synth_result = await session.execute(synth_query)
                            synth_row = synth_result.first()
                            if not synth_row:
                                raise ValueError(f"Synth actor not found: {actor_id}")
                            
                            synth = synth_row[0]
                            actor_context = {
                                "id": str(synth.id),
                                "type": "synth",
                                "name": synth.preferred_name or f"{synth.first_name} {synth.last_name}",
                                "description": synth.backstory
                            }
                        
                        # Build result
                        return {
                            "data": {
                                "client_context": {
                                    "client_id": str(client.id),
                                    "client_name": client.display_name or client.legal_name,
                                    "client_user_id": str(client_user.id),
                                    "client_user_name": client_user.preferred_name or client_user.full_name,
                                    "client_user_email": client_user.email
                                },
                                "actor_context": actor_context
                            }
                        }
                except asyncio.CancelledError:
                    # Task was cancelled during shutdown, just return error
                    return {
                        "error": "Context query cancelled during shutdown",
                        "data": None
                    }
                except Exception as db_error:
                    # Make sure session cleanup happens even on errors
                    session = None
                    raise db_error
                    
            except ValueError as e:
                # Don't retry on validation errors - they won't fix themselves
                raise e
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.error(f"Context query attempt {attempt + 1} failed: {e}. Retrying...")
                    time.sleep(2 ** attempt)  # exponential backoff: 2s, 4s, 8s
                    continue
                else:
                    return {
                        "error": f"Failed after {max_retries} attempts: {str(e)}",
                        "data": None
                    }
            finally:
                # Ensure any lingering session references are cleared
                session = None

async def execute_context_query(
    query_type: str,
    context_params: Dict[str, Any],
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Execute a context query directly.
    
    Args:
        query_type: Type of query (currently only supports "actor_context")
        context_params: Dict with client_user_id, actor_type, and actor_id
        limit: Optional limit (ignored for now)
        
    Returns:
        Dict containing client and actor context
    """
    tool = ContextQueryTool()
    return await tool._arun(query_type, context_params)