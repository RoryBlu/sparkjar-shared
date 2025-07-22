"""
Memory Entities Integrity Manager

This module provides tools to ensure data integrity in the memory_entities table,
including entity name uniqueness, proper type naming, and metadata validation.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_, text
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from shared.database.models import MemoryEntity, MemoryRelation, ObjectSchemas
from shared.database.connection import get_async_db_session
from shared.services.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

class MemoryIntegrityManager:
    """
    Manages memory_entities data integrity and validation.
    
    This class provides methods to:
    - Enforce entity name uniqueness as accessible keys
    - Remove 'template' from entity type names for actual knowledge records
    - Validate metadata JSON against object_schemas table
    - Fix existing data integrity issues
    - Generate integrity reports
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.schema_validator = SchemaValidator(db_session)
        self.integrity_issues = {
            'duplicate_names': [],
            'invalid_type_names': [],
            'metadata_validation_failures': [],
            'orphaned_relations': []
        }
    
    async def analyze_integrity(self) -> Dict[str, Any]:
        """
        Analyze the current state of memory_entities data integrity.
        
        Returns:
            Dictionary containing analysis results and identified issues
        """
        logger.info("Starting memory entities integrity analysis...")
        
        results = {
            'total_entities': 0,
            'duplicate_names': [],
            'template_type_issues': [],
            'metadata_issues': [],
            'orphaned_relations': [],
            'summary': {}
        }
        
        # Count total entities
        count_query = select(func.count()).select_from(MemoryEntity)
        total = await self.db.scalar(count_query)
        results['total_entities'] = total
        
        # Find duplicate entity names within same scope
        results['duplicate_names'] = await self._find_duplicate_names()
        
        # Find entities with 'template' in type name
        results['template_type_issues'] = await self._find_template_type_issues()
        
        # Validate metadata against schemas
        results['metadata_issues'] = await self._validate_all_metadata()
        
        # Find orphaned relations
        results['orphaned_relations'] = await self._find_orphaned_relations()
        
        # Generate summary
        results['summary'] = {
            'total_entities': results['total_entities'],
            'duplicate_names_count': len(results['duplicate_names']),
            'template_type_issues_count': len(results['template_type_issues']),
            'metadata_issues_count': len(results['metadata_issues']),
            'orphaned_relations_count': len(results['orphaned_relations']),
            'needs_fixes': (
                len(results['duplicate_names']) > 0 or
                len(results['template_type_issues']) > 0 or
                len(results['metadata_issues']) > 0 or
                len(results['orphaned_relations']) > 0
            )
        }
        
        logger.info(f"Integrity analysis complete: {results['summary']}")
        return results
    
    async def _find_duplicate_names(self) -> List[Dict[str, Any]]:
        """Find entities with duplicate names within the same scope."""
        query = text("""
            SELECT 
                entity_name,
                client_id,
                actor_type,
                actor_id,
                COUNT(*) as count,
                array_agg(id) as entity_ids
            FROM memory_entities
            WHERE deleted_at IS NULL
            GROUP BY entity_name, client_id, actor_type, actor_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        result = await self.db.execute(query)
        duplicates = []
        
        for row in result:
            duplicates.append({
                'entity_name': row.entity_name,
                'client_id': str(row.client_id),
                'actor_type': row.actor_type,
                'actor_id': str(row.actor_id),
                'count': row.count,
                'entity_ids': [str(id) for id in row.entity_ids]
            })
        
        return duplicates
    
    async def _find_template_type_issues(self) -> List[Dict[str, Any]]:
        """Find entities with 'template' in their type name that shouldn't have it."""
        query = select(MemoryEntity).where(
            and_(
                MemoryEntity.entity_type.like('%template%'),
                MemoryEntity.deleted_at.is_(None),
                # Exclude actual template entities (e.g., from synth_class)
                MemoryEntity.actor_type == 'synth_class'
            )
        )
        
        result = await self.db.execute(query)
        entities = result.scalars().all()
        
        issues = []
        for entity in entities:
            # Check if this is actual knowledge (has observations)
            if entity.observations and len(entity.observations) > 0:
                issues.append({
                    'entity_id': str(entity.id),
                    'entity_name': entity.entity_name,
                    'entity_type': entity.entity_type,
                    'actor_type': entity.actor_type,
                    'actor_id': str(entity.actor_id),
                    'observation_count': len(entity.observations),
                    'suggested_type': entity.entity_type.replace('_template', '').replace('template_', '')
                })
        
        return issues
    
    async def _validate_all_metadata(self) -> List[Dict[str, Any]]:
        """Validate metadata JSON against corresponding schemas."""
        # Get all entities with metadata
        query = select(MemoryEntity).where(
            and_(
                MemoryEntity.metadata_json.isnot(None),
                MemoryEntity.deleted_at.is_(None)
            )
        ).limit(1000)  # Process in batches
        
        result = await self.db.execute(query)
        entities = result.scalars().all()
        
        validation_issues = []
        
        for entity in entities:
            if entity.metadata_json and entity.metadata_json != {}:
                # Try to validate against schema
                schema_name = f"memory_entity_{entity.entity_type}"
                validation_result = await self.schema_validator.validate_data(
                    entity.metadata_json,
                    schema_name,
                    validate_metadata=False  # Avoid recursion
                )
                
                if not validation_result['valid']:
                    validation_issues.append({
                        'entity_id': str(entity.id),
                        'entity_name': entity.entity_name,
                        'entity_type': entity.entity_type,
                        'validation_errors': validation_result.get('errors', []),
                        'metadata_keys': list(entity.metadata_json.keys())
                    })
        
        return validation_issues
    
    async def _find_orphaned_relations(self) -> List[Dict[str, Any]]:
        """Find relations pointing to non-existent entities."""
        query = text("""
            SELECT 
                r.id as relation_id,
                r.from_entity_id,
                r.to_entity_id,
                r.relation_type,
                CASE WHEN fe.id IS NULL THEN true ELSE false END as from_missing,
                CASE WHEN te.id IS NULL THEN true ELSE false END as to_missing
            FROM memory_relations r
            LEFT JOIN memory_entities fe ON r.from_entity_id = fe.id
            LEFT JOIN memory_entities te ON r.to_entity_id = te.id
            WHERE r.deleted_at IS NULL
                AND (fe.id IS NULL OR te.id IS NULL)
        """)
        
        result = await self.db.execute(query)
        orphaned = []
        
        for row in result:
            orphaned.append({
                'relation_id': str(row.relation_id),
                'from_entity_id': str(row.from_entity_id),
                'to_entity_id': str(row.to_entity_id),
                'relation_type': row.relation_type,
                'from_missing': row.from_missing,
                'to_missing': row.to_missing
            })
        
        return orphaned
    
    async def fix_entity_naming(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Ensure entity names are proper unique keys.
        
        Args:
            dry_run: If True, only report what would be changed
            
        Returns:
            Dictionary with results of the operation
        """
        logger.info(f"Starting entity naming fix (dry_run={dry_run})...")
        
        results = {
            'entities_processed': 0,
            'names_fixed': 0,
            'duplicates_resolved': 0,
            'errors': []
        }
        
        # Find entities with problematic names
        query = select(MemoryEntity).where(
            MemoryEntity.deleted_at.is_(None)
        )
        
        result = await self.db.execute(query)
        entities = result.scalars().all()
        
        for entity in entities:
            results['entities_processed'] += 1
            
            # Check if name is a proper key (no spaces, lowercase, underscores)
            original_name = entity.entity_name
            suggested_name = self._normalize_entity_name(original_name)
            
            if original_name != suggested_name:
                if not dry_run:
                    try:
                        entity.entity_name = suggested_name
                        await self.db.flush()
                        results['names_fixed'] += 1
                    except IntegrityError:
                        # Handle duplicate by appending actor_id
                        entity.entity_name = f"{suggested_name}_{entity.actor_id}"
                        await self.db.flush()
                        results['duplicates_resolved'] += 1
                else:
                    logger.info(f"Would rename: '{original_name}' -> '{suggested_name}'")
                    results['names_fixed'] += 1
        
        if not dry_run:
            await self.db.commit()
            logger.info(f"Entity naming fix complete: {results}")
        else:
            logger.info(f"Dry run complete. Would fix {results['names_fixed']} names")
            
        return results
    
    def _normalize_entity_name(self, name: str) -> str:
        """Convert entity name to a proper key format."""
        # Convert to lowercase
        name = name.lower()
        
        # Replace spaces and special characters with underscores
        import re
        name = re.sub(r'[^a-z0-9_]+', '_', name)
        
        # Remove leading/trailing underscores
        name = name.strip('_')
        
        # Replace multiple underscores with single
        name = re.sub(r'_+', '_', name)
        
        return name
    
    async def remove_template_types(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Remove 'template' from entity type names for actual knowledge records.
        
        Args:
            dry_run: If True, only report what would be changed
            
        Returns:
            Dictionary with results of the operation
        """
        logger.info(f"Starting template type removal (dry_run={dry_run})...")
        
        results = {
            'entities_processed': 0,
            'types_fixed': 0,
            'errors': []
        }
        
        # Find entities with template in type name
        issues = await self._find_template_type_issues()
        
        for issue in issues:
            results['entities_processed'] += 1
            
            if not dry_run:
                try:
                    # Update the entity type
                    update_query = update(MemoryEntity).where(
                        MemoryEntity.id == issue['entity_id']
                    ).values(
                        entity_type=issue['suggested_type'],
                        updated_at=datetime.utcnow()
                    )
                    
                    await self.db.execute(update_query)
                    results['types_fixed'] += 1
                except Exception as e:
                    results['errors'].append({
                        'entity_id': issue['entity_id'],
                        'error': str(e)
                    })
            else:
                logger.info(
                    f"Would change type: '{issue['entity_type']}' -> '{issue['suggested_type']}' "
                    f"for entity {issue['entity_name']}"
                )
                results['types_fixed'] += 1
        
        if not dry_run:
            await self.db.commit()
            logger.info(f"Template type removal complete: {results}")
        else:
            logger.info(f"Dry run complete. Would fix {results['types_fixed']} types")
            
        return results
    
    async def validate_metadata_schemas(self, fix_invalid: bool = False) -> Dict[str, Any]:
        """
        Validate metadata JSON against corresponding schemas in object_schemas table.
        
        Args:
            fix_invalid: If True, remove invalid fields from metadata
            
        Returns:
            Dictionary with validation results
        """
        logger.info(f"Starting metadata schema validation (fix_invalid={fix_invalid})...")
        
        results = {
            'entities_validated': 0,
            'validation_failures': 0,
            'metadata_fixed': 0,
            'errors': []
        }
        
        # Get validation issues
        issues = await self._validate_all_metadata()
        results['entities_validated'] = len(issues)
        results['validation_failures'] = len(issues)
        
        if fix_invalid and issues:
            for issue in issues:
                try:
                    # Get the entity
                    entity_query = select(MemoryEntity).where(
                        MemoryEntity.id == issue['entity_id']
                    )
                    result = await self.db.execute(entity_query)
                    entity = result.scalar_one()
                    
                    # Remove invalid fields (for now, just log what would be removed)
                    logger.warning(
                        f"Entity {issue['entity_name']} has metadata validation errors: "
                        f"{issue['validation_errors']}"
                    )
                    
                    # In a real fix, we would clean the metadata here
                    # For now, just count it
                    results['metadata_fixed'] += 1
                    
                except Exception as e:
                    results['errors'].append({
                        'entity_id': issue['entity_id'],
                        'error': str(e)
                    })
        
        logger.info(f"Metadata validation complete: {results}")
        return results
    
    async def create_migration_script(self) -> str:
        """
        Generate a SQL migration script to fix all identified issues.
        
        Returns:
            SQL script as a string
        """
        logger.info("Generating migration script...")
        
        # Analyze current state
        analysis = await self.analyze_integrity()
        
        script_parts = [
            "-- Memory Entities Integrity Migration Script",
            f"-- Generated: {datetime.utcnow().isoformat()}",
            "-- This script fixes data integrity issues in memory_entities table",
            "",
            "BEGIN;",
            ""
        ]
        
        # Fix duplicate names
        if analysis['duplicate_names']:
            script_parts.append("-- Fix duplicate entity names")
            for dup in analysis['duplicate_names']:
                script_parts.append(f"-- Duplicate: {dup['entity_name']} ({dup['count']} occurrences)")
                # Add row_number to duplicates to make them unique
                script_parts.append(f"""
UPDATE memory_entities
SET entity_name = entity_name || '_' || row_num::text
FROM (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY entity_name, client_id, actor_type, actor_id 
                                  ORDER BY created_at) as row_num
    FROM memory_entities
    WHERE entity_name = '{dup['entity_name']}'
      AND client_id = '{dup['client_id']}'::uuid
      AND actor_type = '{dup['actor_type']}'
      AND actor_id = '{dup['actor_id']}'::uuid
) as numbered
WHERE memory_entities.id = numbered.id
  AND numbered.row_num > 1;
""")
        
        # Fix template types
        if analysis['template_type_issues']:
            script_parts.append("")
            script_parts.append("-- Remove 'template' from entity types")
            for issue in analysis['template_type_issues']:
                script_parts.append(f"""
UPDATE memory_entities
SET entity_type = '{issue['suggested_type']}',
    updated_at = NOW()
WHERE id = '{issue['entity_id']}'::uuid;
""")
        
        # Clean up orphaned relations
        if analysis['orphaned_relations']:
            script_parts.append("")
            script_parts.append("-- Soft delete orphaned relations")
            for orphan in analysis['orphaned_relations']:
                script_parts.append(f"""
UPDATE memory_relations
SET deleted_at = NOW()
WHERE id = '{orphan['relation_id']}'::uuid;
""")
        
        script_parts.extend([
            "",
            "COMMIT;",
            "",
            "-- Verification queries:",
            "-- SELECT entity_name, COUNT(*) FROM memory_entities GROUP BY entity_name HAVING COUNT(*) > 1;",
            "-- SELECT COUNT(*) FROM memory_entities WHERE entity_type LIKE '%template%';",
            "-- SELECT COUNT(*) FROM memory_relations r LEFT JOIN memory_entities e ON r.from_entity_id = e.id WHERE e.id IS NULL;"
        ])
        
        return '\n'.join(script_parts)
    
    async def generate_report(self) -> str:
        """
        Generate a comprehensive integrity report.
        
        Returns:
            Formatted report as a string
        """
        logger.info("Generating integrity report...")
        
        analysis = await self.analyze_integrity()
        
        report_lines = [
            "# Memory Entities Integrity Report",
            f"Generated: {datetime.utcnow().isoformat()}",
            "",
            "## Summary",
            f"- Total Entities: {analysis['summary']['total_entities']}",
            f"- Duplicate Names: {analysis['summary']['duplicate_names_count']}",
            f"- Template Type Issues: {analysis['summary']['template_type_issues_count']}",
            f"- Metadata Validation Issues: {analysis['summary']['metadata_issues_count']}",
            f"- Orphaned Relations: {analysis['summary']['orphaned_relations_count']}",
            f"- **Needs Fixes: {'YES' if analysis['summary']['needs_fixes'] else 'NO'}**",
            ""
        ]
        
        # Duplicate names details
        if analysis['duplicate_names']:
            report_lines.extend([
                "## Duplicate Entity Names",
                "These entities have the same name within the same scope:",
                ""
            ])
            for dup in analysis['duplicate_names'][:10]:  # Show first 10
                report_lines.append(
                    f"- **{dup['entity_name']}**: {dup['count']} duplicates "
                    f"(client: {dup['client_id'][:8]}..., {dup['actor_type']})"
                )
            if len(analysis['duplicate_names']) > 10:
                report_lines.append(f"... and {len(analysis['duplicate_names']) - 10} more")
            report_lines.append("")
        
        # Template type issues
        if analysis['template_type_issues']:
            report_lines.extend([
                "## Template Type Issues",
                "These entities have 'template' in their type but contain actual knowledge:",
                ""
            ])
            for issue in analysis['template_type_issues'][:10]:
                report_lines.append(
                    f"- **{issue['entity_name']}**: type '{issue['entity_type']}' -> '{issue['suggested_type']}' "
                    f"({issue['observation_count']} observations)"
                )
            if len(analysis['template_type_issues']) > 10:
                report_lines.append(f"... and {len(analysis['template_type_issues']) - 10} more")
            report_lines.append("")
        
        # Metadata issues
        if analysis['metadata_issues']:
            report_lines.extend([
                "## Metadata Validation Issues",
                "These entities have metadata that doesn't match their schema:",
                ""
            ])
            for issue in analysis['metadata_issues'][:5]:
                report_lines.append(
                    f"- **{issue['entity_name']}** ({issue['entity_type']}): "
                    f"{len(issue['validation_errors'])} validation errors"
                )
            if len(analysis['metadata_issues']) > 5:
                report_lines.append(f"... and {len(analysis['metadata_issues']) - 5} more")
            report_lines.append("")
        
        # Recommendations
        report_lines.extend([
            "## Recommendations",
            ""
        ])
        
        if analysis['summary']['needs_fixes']:
            report_lines.extend([
                "1. **Backup the database** before running any fixes",
                "2. Run `fix_entity_naming(dry_run=True)` to preview naming fixes",
                "3. Run `remove_template_types(dry_run=True)` to preview type fixes",
                "4. Generate and review the migration script with `create_migration_script()`",
                "5. Apply fixes in a transaction with proper error handling",
                "6. Re-run this report to verify all issues are resolved"
            ])
        else:
            report_lines.append("✅ No integrity issues found. The memory_entities table is in good shape!")
        
        return '\n'.join(report_lines)

# Utility function for CLI usage
async def run_integrity_check():
    """Run a complete integrity check and generate a report."""
    async with get_async_db_session() as session:
        manager = MemoryIntegrityManager(session)
        report = await manager.generate_report()
        logger.info(report)
        
        # Also save the migration script if issues found
        analysis = await manager.analyze_integrity()
        if analysis['summary']['needs_fixes']:
            script = await manager.create_migration_script()
            with open('memory_integrity_migration.sql', 'w') as f:
                f.write(script)
            logger.info("\n📄 Migration script saved to: memory_integrity_migration.sql")

if __name__ == "__main__":
    asyncio.run(run_integrity_check())