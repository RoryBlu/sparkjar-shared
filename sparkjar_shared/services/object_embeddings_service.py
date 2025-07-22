"""
Service for managing object embeddings stored in database with pgvector.
Handles embeddings for semantic search across knowledge realms with model validation.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, text, func
from sqlalchemy.dialects.postgresql import insert
import logging
import uuid
from datetime import datetime

from shared.database.models import ObjectEmbeddings
from shared.config.embedding_config import get_embedding_config_manager

logger = logging.getLogger(__name__)

class ObjectEmbeddingsService:
    """
    Service for managing embeddings across knowledge realms with model validation.
    
    This service provides CRUD operations for object embeddings and vector similarity search
    with automatic validation against supported embedding models.
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.embedding_manager = get_embedding_config_manager(db_session)
    
    async def store_embedding(
        self,
        source_table: str,
        source_id: uuid.UUID,
        source_field: str,
        embedding_model: str,
        embedding: List[float],
        actor_type: str,
        actor_id: str,
        client_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ObjectEmbeddings:
        """
        Store an embedding with model validation.
        
        Args:
            source_table: Name of the source table
            source_id: UUID of the source row
            source_field: Field that was embedded
            embedding_model: Name of the embedding model used
            embedding: The vector embedding
            actor_type: Knowledge realm (synth, synth_class, skill_module, client)
            actor_id: ID within the actor_type context
            client_id: Client identifier (required for synth/client, null for synth_class/skill_module)
            metadata: Additional metadata
            
        Returns:
            The created ObjectEmbeddings record
            
        Raises:
            ValueError: If model validation fails
        """
        try:
            # Validate embedding model and dimension
            embedding_dimension = len(embedding)
            if not self.embedding_manager.validate_model_dimension(embedding_model, embedding_dimension):
                raise ValueError(f"Invalid model/dimension combination: {embedding_model}/{embedding_dimension}")
            
            # Validate actor_type and client_id requirements
            if actor_type in ('synth', 'client') and client_id is None:
                raise ValueError(f"client_id is required for actor_type '{actor_type}'")
            if actor_type in ('synth_class', 'skill_module') and client_id is not None:
                raise ValueError(f"client_id must be null for actor_type '{actor_type}'")
            
            # Use upsert to handle duplicates gracefully
            stmt = insert(ObjectEmbeddings).values(
                client_id=client_id,
                source_table=source_table,
                source_id=source_id,
                source_field=source_field,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
                embedding=embedding,
                actor_type=actor_type,
                actor_id=actor_id,
                metadata=metadata or {},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # On conflict, update the embedding and metadata
            stmt = stmt.on_conflict_do_update(
                constraint='unique_embedding',
                set_={
                    'embedding': stmt.excluded.embedding,
                    'metadata': stmt.excluded.metadata,
                    'updated_at': stmt.excluded.updated_at
                }
            ).returning(ObjectEmbeddings)
            
            result = await self.db.execute(stmt)
            embedding_record = result.scalar_one()
            await self.db.commit()
            
            logger.info(f"Stored embedding for {source_table}.{source_field} using {embedding_model} "
                       f"(actor: {actor_type}/{actor_id})")
            return embedding_record
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to store embedding: {e}")
            raise
    
    async def get_embeddings_by_source(
        self,
        source_table: str,
        source_field: Optional[str] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        client_id: Optional[uuid.UUID] = None
    ) -> List[ObjectEmbeddings]:
        """
        Get embeddings filtered by source and context.
        
        Args:
            source_table: Source table name
            source_field: Optional specific field name
            actor_type: Optional actor type filter
            actor_id: Optional actor ID filter
            client_id: Optional client identifier
            
        Returns:
            List of ObjectEmbeddings records
        """
        try:
            where_conditions = [ObjectEmbeddings.source_table == source_table]
            
            if source_field:
                where_conditions.append(ObjectEmbeddings.source_field == source_field)
            if actor_type:
                where_conditions.append(ObjectEmbeddings.actor_type == actor_type)
            if actor_id:
                where_conditions.append(ObjectEmbeddings.actor_id == actor_id)
            if client_id:
                where_conditions.append(ObjectEmbeddings.client_id == client_id)
            
            query = select(ObjectEmbeddings).where(and_(*where_conditions))
            result = await self.db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get embeddings for {source_table}: {e}")
            raise
    
    async def hierarchical_similarity_search(
        self,
        query_embedding: List[float],
        embedding_model: str,
        actor_types: Optional[List[str]] = None,
        actor_ids: Optional[List[str]] = None,
        client_id: Optional[uuid.UUID] = None,
        source_table: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[ObjectEmbeddings, float, int]]:
        """
        Perform hierarchical vector similarity search with priority ordering.
        
        Args:
            query_embedding: The query vector
            embedding_model: Model used for the query embedding
            actor_types: Optional list of actor types to search
            actor_ids: Optional list of actor IDs to search
            client_id: Optional client identifier
            source_table: Optional source table filter
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of tuples (ObjectEmbeddings, similarity_score, priority_order)
        """
        try:
            # Validate query embedding model
            query_dimension = len(query_embedding)
            if not self.embedding_manager.validate_model_dimension(embedding_model, query_dimension):
                raise ValueError(f"Invalid query embedding model/dimension: {embedding_model}/{query_dimension}")
            
            # Build base conditions
            where_conditions = [
                ObjectEmbeddings.embedding_model == embedding_model,
                ObjectEmbeddings.embedding_dimension == query_dimension
            ]
            
            if actor_types:
                where_conditions.append(ObjectEmbeddings.actor_type.in_(actor_types))
            if actor_ids:
                where_conditions.append(ObjectEmbeddings.actor_id.in_(actor_ids))
            if client_id:
                where_conditions.append(ObjectEmbeddings.client_id == client_id)
            if source_table:
                where_conditions.append(ObjectEmbeddings.source_table == source_table)
            
            # Use cosine similarity (1 - cosine distance)
            similarity_expr = text("1 - (embedding <=> :query_embedding)")
            
            # Priority ordering based on actor_type
            priority_expr = text("""
                CASE 
                    WHEN actor_type = 'client' THEN 1
                    WHEN actor_type = 'synth' THEN 2
                    WHEN actor_type = 'synth_class' THEN 3
                    WHEN actor_type = 'skill_module' THEN 4
                    ELSE 5
                END
            """)
            
            query = select(
                ObjectEmbeddings,
                similarity_expr.label('similarity'),
                priority_expr.label('priority_order')
            ).where(
                and_(*where_conditions)
            ).where(
                similarity_expr >= similarity_threshold
            ).order_by(
                priority_expr.asc(),  # Lower priority number = higher priority
                similarity_expr.desc()
            ).limit(limit)
            
            result = await self.db.execute(
                query, 
                {"query_embedding": str(query_embedding)}
            )
            
            rows = result.fetchall()
            return [(row.ObjectEmbeddings, row.similarity, row.priority_order) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to perform hierarchical similarity search: {e}")
            raise
    
    async def delete_embeddings(
        self,
        source_table: Optional[str] = None,
        source_field: Optional[str] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        client_id: Optional[uuid.UUID] = None,
        embedding_model: Optional[str] = None
    ) -> int:
        """
        Delete embeddings with flexible filtering.
        
        Args:
            source_table: Optional source table filter
            source_field: Optional source field filter
            actor_type: Optional actor type filter
            actor_id: Optional actor ID filter
            client_id: Optional client identifier filter
            embedding_model: Optional embedding model filter
            
        Returns:
            Number of deleted records
        """
        try:
            where_conditions = []
            
            if source_table:
                where_conditions.append(ObjectEmbeddings.source_table == source_table)
            if source_field:
                where_conditions.append(ObjectEmbeddings.source_field == source_field)
            if actor_type:
                where_conditions.append(ObjectEmbeddings.actor_type == actor_type)
            if actor_id:
                where_conditions.append(ObjectEmbeddings.actor_id == actor_id)
            if client_id:
                where_conditions.append(ObjectEmbeddings.client_id == client_id)
            if embedding_model:
                where_conditions.append(ObjectEmbeddings.embedding_model == embedding_model)
            
            if not where_conditions:
                raise ValueError("At least one filter condition must be provided for deletion")
            
            stmt = delete(ObjectEmbeddings).where(and_(*where_conditions))
            result = await self.db.execute(stmt)
            await self.db.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} embeddings with filters: "
                       f"table={source_table}, field={source_field}, actor={actor_type}/{actor_id}")
            return deleted_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete embeddings: {e}")
            raise
    
    async def get_embedding_stats(
        self, 
        client_id: Optional[uuid.UUID] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics about embeddings.
        
        Args:
            client_id: Optional client identifier filter
            actor_type: Optional actor type filter
            actor_id: Optional actor ID filter
            
        Returns:
            Dictionary with embedding statistics
        """
        try:
            # Build base conditions
            where_conditions = []
            if client_id:
                where_conditions.append(ObjectEmbeddings.client_id == client_id)
            if actor_type:
                where_conditions.append(ObjectEmbeddings.actor_type == actor_type)
            if actor_id:
                where_conditions.append(ObjectEmbeddings.actor_id == actor_id)
            
            base_query = select(ObjectEmbeddings)
            if where_conditions:
                base_query = base_query.where(and_(*where_conditions))
            
            # Count total embeddings
            total_query = select(func.count()).select_from(base_query.subquery())
            total_result = await self.db.execute(total_query)
            total_count = total_result.scalar()
            
            # Count by source table
            table_query = select(
                ObjectEmbeddings.source_table,
                func.count().label('count')
            )
            if where_conditions:
                table_query = table_query.where(and_(*where_conditions))
            table_query = table_query.group_by(ObjectEmbeddings.source_table)
            
            table_result = await self.db.execute(table_query)
            table_counts = {row.source_table: row.count for row in table_result}
            
            # Count by embedding model
            model_query = select(
                ObjectEmbeddings.embedding_model,
                ObjectEmbeddings.embedding_dimension,
                func.count().label('count')
            )
            if where_conditions:
                model_query = model_query.where(and_(*where_conditions))
            model_query = model_query.group_by(
                ObjectEmbeddings.embedding_model,
                ObjectEmbeddings.embedding_dimension
            )
            
            model_result = await self.db.execute(model_query)
            model_counts = [
                {
                    'model': row.embedding_model,
                    'dimension': row.embedding_dimension,
                    'count': row.count
                }
                for row in model_result
            ]
            
            # Count by actor type
            actor_query = select(
                ObjectEmbeddings.actor_type,
                func.count().label('count')
            )
            if where_conditions:
                actor_query = actor_query.where(and_(*where_conditions))
            actor_query = actor_query.group_by(ObjectEmbeddings.actor_type)
            
            actor_result = await self.db.execute(actor_query)
            actor_counts = {row.actor_type: row.count for row in actor_result}
            
            return {
                'total_embeddings': total_count,
                'embeddings_by_table': table_counts,
                'embeddings_by_model': model_counts,
                'embeddings_by_actor_type': actor_counts,
                'filters': {
                    'client_id': str(client_id) if client_id else None,
                    'actor_type': actor_type,
                    'actor_id': actor_id
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            raise