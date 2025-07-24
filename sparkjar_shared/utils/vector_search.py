"""
Vector search utilities for pgvector-enabled tables
Provides semantic search capabilities for crew logs and other embedded data
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from src.utils.embedding_client import get_embedding_client

logger = logging.getLogger(__name__)

class VectorSearchClient:
    """
    Client for performing vector similarity searches using pgvector
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.embedding_client = get_embedding_client()

    async def search_crew_logs(
        self,
        query: str,
        job_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Search crew logs using semantic similarity

        Args:
            query: Search query text
            job_id: Optional job ID to filter by
            event_types: Optional list of event types to filter
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of matching events with similarity scores
        """
        # Get query embedding using the embeddings service
        query_embedding = (await self.embedding_client.get_embeddings(query))[0]

        # Build SQL query
        conditions = ["embedding IS NOT NULL"]
        params = [query_embedding, query_embedding, similarity_threshold]
        param_idx = 4

        if job_id:
            conditions.append(f"job_id = ${param_idx}")
            params.append(job_id)
            param_idx += 1

        if event_types:
            placeholders = ", ".join(
                f"${i}" for i in range(param_idx, param_idx + len(event_types))
            )
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
            param_idx += len(event_types)

        where_clause = " AND ".join(conditions)

        query_sql = f"""
            SELECT 
                id,
                job_id,
                event_type,
                event_data,
                event_time,
                created_at,
                1 - (embedding <=> $1::vector) as similarity
            FROM crew_job_event
            WHERE {where_clause}
                AND 1 - (embedding <=> $2::vector) > $3
            ORDER BY embedding <=> $1::vector
            LIMIT {limit}
        """

        # Execute search
        conn = await asyncpg.connect(self.db_url)
        try:
            rows = await conn.fetch(query_sql, *params)

            results = []
            for row in rows:
                results.append(
                    {
                        "id": row["id"],
                        "job_id": row["job_id"],
                        "event_type": row["event_type"],
                        "event_data": row["event_data"],
                        "event_time": row["event_time"],
                        "created_at": row["created_at"],
                        "similarity": float(row["similarity"]),
                    }
                )

            logger.info(
                f"Vector search found {len(results)} results for query: {query[:50]}..."
            )
            return results

        finally:
            await conn.close()

    async def find_similar_events(
        self, event_id: int, limit: int = 5, exclude_same_job: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find events similar to a given event

        Args:
            event_id: ID of the reference event
            limit: Maximum number of similar events
            exclude_same_job: Whether to exclude events from the same job

        Returns:
            List of similar events with similarity scores
        """
        conn = await asyncpg.connect(self.db_url)
        try:
            # Get the reference event
            ref_event = await conn.fetchrow(
                "SELECT job_id, embedding FROM crew_job_event WHERE id = $1", event_id
            )

            if not ref_event or not ref_event["embedding"]:
                return []

            # Build query
            conditions = ["id != $1", "embedding IS NOT NULL"]
            params = [event_id, ref_event["embedding"], ref_event["embedding"]]

            if exclude_same_job:
                conditions.append("job_id != $4")
                params.append(ref_event["job_id"])

            where_clause = " AND ".join(conditions)

            query_sql = f"""
                SELECT 
                    id,
                    job_id,
                    event_type,
                    event_data,
                    event_time,
                    1 - (embedding <=> $2::vector) as similarity
                FROM crew_job_event
                WHERE {where_clause}
                ORDER BY embedding <=> $3::vector
                LIMIT {limit}
            """

            rows = await conn.fetch(query_sql, *params)

            results = []
            for row in rows:
                results.append(
                    {
                        "id": row["id"],
                        "job_id": row["job_id"],
                        "event_type": row["event_type"],
                        "event_data": row["event_data"],
                        "event_time": row["event_time"],
                        "similarity": float(row["similarity"]),
                    }
                )

            return results

        finally:
            await conn.close()

    async def analyze_patterns(
        self, job_id: str, pattern_queries: Dict[str, str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze multiple patterns in a job's execution

        Args:
            job_id: Job ID to analyze
            pattern_queries: Dict of pattern_name -> search_query

        Returns:
            Dict of pattern_name -> list of matching events
        """
        results = {}

        for pattern_name, query in pattern_queries.items():
            matches = await self.search_crew_logs(
                query=query, job_id=job_id, limit=10, similarity_threshold=0.7
            )
            results[pattern_name] = matches

        return results

    async def get_event_context(
        self, event_id: int, context_window: int = 5
    ) -> Dict[str, Any]:
        """
        Get temporal context around an event

        Args:
            event_id: Central event ID
            context_window: Number of events before/after to include

        Returns:
            Dict with the event and its temporal context
        """
        conn = await asyncpg.connect(self.db_url)
        try:
            # Get the reference event
            ref_event = await conn.fetchrow(
                """
                SELECT job_id, event_time 
                FROM crew_job_event 
                WHERE id = $1
            """,
                event_id,
            )

            if not ref_event:
                return {}

            # Get events before
            before = await conn.fetch(
                """
                SELECT id, event_type, event_data, event_time
                FROM crew_job_event
                WHERE job_id = $1 AND event_time < $2
                ORDER BY event_time DESC
                LIMIT $3
            """,
                ref_event["job_id"],
                ref_event["event_time"],
                context_window,
            )

            # Get events after
            after = await conn.fetch(
                """
                SELECT id, event_type, event_data, event_time
                FROM crew_job_event
                WHERE job_id = $1 AND event_time > $2
                ORDER BY event_time ASC
                LIMIT $3
            """,
                ref_event["job_id"],
                ref_event["event_time"],
                context_window,
            )

            # Get the central event
            central = await conn.fetchrow(
                """
                SELECT id, event_type, event_data, event_time
                FROM crew_job_event
                WHERE id = $1
            """,
                event_id,
            )

            return {
                "central_event": dict(central) if central else None,
                "before": [dict(row) for row in reversed(before)],
                "after": [dict(row) for row in after],
            }

        finally:
            await conn.close()

# Sync wrapper for non-async contexts
class VectorSearchClientSync:
    """Synchronous wrapper for VectorSearchClient"""

    def __init__(self, db_url: str):
        self.async_client = VectorSearchClient(db_url)

    def search_crew_logs(self, **kwargs) -> List[Dict[str, Any]]:
        import asyncio

        return asyncio.run(self.async_client.search_crew_logs(**kwargs))

    def find_similar_events(self, **kwargs) -> List[Dict[str, Any]]:
        import asyncio

        return asyncio.run(self.async_client.find_similar_events(**kwargs))

    def analyze_patterns(self, **kwargs) -> Dict[str, List[Dict[str, Any]]]:
        import asyncio

        return asyncio.run(self.async_client.analyze_patterns(**kwargs))

    def get_event_context(self, **kwargs) -> Dict[str, Any]:
        import asyncio

        return asyncio.run(self.async_client.get_event_context(**kwargs))
