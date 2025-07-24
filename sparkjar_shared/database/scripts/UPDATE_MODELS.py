#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Standalone model updater - generates SQLAlchemy models from database
"""
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    logger.error("Error: DATABASE_URL environment variable is required")
    sys.exit(1)
sync_url = DATABASE_URL.replace('+asyncpg', '').replace('?pgbouncer=true', '')

def get_column_info(cursor, table_name):
    """Get column information for a table"""
    cursor.execute("""
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cursor.fetchall()

def get_constraints(cursor, table_name):
    """Get constraints for a table"""
    cursor.execute("""
        SELECT 
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.table_schema = 'public' AND tc.table_name = %s
    """, (table_name,))
    return cursor.fetchall()

def map_postgres_type(pg_type, length=None):
    """Map PostgreSQL types to SQLAlchemy types"""
    type_map = {
        'uuid': 'UUID',
        'text': 'Text',
        'integer': 'Integer',
        'bigint': 'BigInteger',
        'boolean': 'Boolean',
        'timestamp with time zone': 'DateTime(timezone=True)',
        'timestamp without time zone': 'DateTime',
        'jsonb': 'JSONB',
        'json': 'JSON',
        'date': 'Date',
        'time': 'Time',
        'numeric': 'Numeric',
        'double precision': 'Float',
        'character varying': f'String({length})' if length else 'String',
        'vector': 'Vector(768)',  # pgvector type
    }
    
    if pg_type.startswith('vector'):
        import re
        match = re.search(r'vector\((\d+)\)', pg_type)
        dim = match.group(1) if match else '768'
        return f'Vector({dim})'
    
    return type_map.get(pg_type, 'String')

def get_protected_name_mapping(col_name):
    """Map database column names to Python-safe attribute names"""
    # Protected/reserved names in SQLAlchemy and Python
    protected_mapping = {
        'metadata': 'metadata_json',
        'class': 'class_name',
        'type': 'type_name',
        'id': 'id',  # Keep as is but noted for reference
        'default': 'default_value',
        'import': 'import_name',
        'return': 'return_value',
        'global': 'global_value',
        'exec': 'exec_value',
        'query': 'query_text',
        'order': 'order_value',
        'filter': 'filter_value',
        'group': 'group_name',
        'table': 'table_name',
        'column': 'column_name',
        'index': 'index_name',
        'primary': 'primary_value',
        'foreign': 'foreign_value',
        'check': 'check_value',
        'unique': 'unique_value',
        'schema': 'schema_data',
        'commit': 'commit_value',
        'rollback': 'rollback_value',
        'session': 'session_value',
        'engine': 'engine_value',
    }
    
    # Return mapped name if protected, otherwise return original
    return protected_mapping.get(col_name, col_name)

def generate_model_class(table_name, columns, constraints):
    """Generate a SQLAlchemy model class for a table"""
    class_name = ''.join(word.capitalize() for word in table_name.split('_'))
    
    code = f"\n\nclass {class_name}(Base):\n"
    code += f'    __tablename__ = "{table_name}"\n'
    
    # Add actor type documentation for relevant tables
    if table_name == 'memory_entities':
        code += '    # Uses actor_type and actor_id for context (human/synth/synth_class/client)\n'
    elif table_name == 'memory_relations':
        code += '    # Relationships between memory entities across different actor contexts\n'
    elif table_name in ['client_users', 'synths', 'synth_classes', 'clients']:
        actor_type_map = {
            'client_users': 'human',
            'synths': 'synth',
            'synth_classes': 'synth_class',
            'clients': 'client'
        }
        code += f'    # Actor type: {actor_type_map[table_name]}\n'
    
    code += '\n'
    
    # Find primary keys
    primary_keys = [c[2] for c in constraints if c[1] == 'PRIMARY KEY']
    
    # Find foreign keys
    foreign_keys = {}
    for c in constraints:
        if c[1] == 'FOREIGN KEY':
            foreign_keys[c[2]] = (c[3], c[4])
    
    # Generate columns
    for col in columns:
        col_name, data_type, is_nullable, default, max_length = col
        
        # Get safe Python attribute name
        python_col_name = get_protected_name_mapping(col_name)
        
        # Column definition
        sa_type = map_postgres_type(data_type, max_length)
        
        # If the Python name differs from DB name, specify the DB column name
        if python_col_name != col_name:
            col_def = f"    {python_col_name} = Column('{col_name}', "
        else:
            col_def = f"    {python_col_name} = Column("
        
        # Add type
        if data_type == 'uuid':
            col_def += "UUID(as_uuid=True)"
        else:
            col_def += sa_type
        
        # Add primary key
        if col_name in primary_keys:
            col_def += ", primary_key=True"
        
        # Add foreign key
        if col_name in foreign_keys:
            fk_table, fk_col = foreign_keys[col_name]
            col_def += f', ForeignKey("{fk_table}.{fk_col}")'
        
        # Add nullable
        if is_nullable == 'NO':
            col_def += ", nullable=False"
        
        # Add default
        if default:
            if 'gen_random_uuid()' in default:
                col_def += ", server_default=text('gen_random_uuid()')"
            elif default == 'now()' or 'now()' in default:
                col_def += ", server_default=func.now()"
            elif default.startswith("'") and '::' in default:
                # Handle PostgreSQL cast syntax like 'value'::type
                col_def += f", server_default=text(\"{default}\")"
            elif default.startswith("'"):
                col_def += f", server_default={default}"
        
        col_def += ")\n"
        code += col_def
    
    return code

def main():
    """Generate models for all tables"""
    conn = psycopg2.connect(sync_url)
    cur = conn.cursor()
    
    try:
        # Get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            AND table_name NOT IN ('schema_migrations', 'ar_internal_metadata')
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        logger.info(f"Found {len(tables)} tables")
        
        # Generate header
        model_code = '''"""
Database models for SparkJAR Crew system.
AUTO-GENERATED from database schema - DO NOT EDIT MANUALLY.
Use UPDATE_MODELS.py script to regenerate.

PROTECTED NAME MAPPINGS:
The following database column names are mapped to Python-safe attribute names:
- metadata -> metadata_json
- class -> class_name
- type -> type_name
- schema -> schema_data
- Any other Python/SQLAlchemy reserved words are similarly mapped

To access these columns in queries, use the mapped Python attribute name.
Example: MyModel.metadata_json (not MyModel.metadata)

ACTOR TYPE SYSTEM:
The memory system uses actor_type and actor_id to provide context for all operations.
Valid actor_type values and their corresponding tables:
- 'human' -> client_users table (for human users)
- 'synth' -> synths table (for AI agents/personas)
- 'synth_class' -> synth_classes table (for agent class definitions)
- 'client' -> clients table (for client organizations)

This allows the memory system to work across different contexts without requiring
a direct client_id relationship on every memory entity.
"""
from sqlalchemy import Column, String, DateTime, Text, Integer, BigInteger, Date, Boolean, Index, Numeric, Float, Time, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, JSON, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

Base = declarative_base()

# Import crew configuration model
try:
    from services.crew_api.src.database.crew_config_model import CrewConfig
except ImportError:
    # Define a placeholder if not available
    class CrewConfig:
        pass
'''
        
        # Track protected name mappings for reporting
        protected_mappings_found = []
        
        # Generate models for each table
        for table in tables:
            logger.info(f"Generating model for {table}...")
            columns = get_column_info(cur, table)
            constraints = get_constraints(cur, table)
            
            # Check for protected names in this table
            for col in columns:
                col_name = col[0]
                mapped_name = get_protected_name_mapping(col_name)
                if mapped_name != col_name:
                    protected_mappings_found.append(f"{table}.{col_name} -> {mapped_name}")
            
            model_code += generate_model_class(table, columns, constraints)
        
        # Add the new thinking models specifically
        if 'thinking_sessions' in tables:
            model_code += """

# Relationships for thinking models
ThinkingSessions.thoughts = relationship("Thoughts", back_populates="session", cascade="all, delete-orphan")
Thoughts.session = relationship("ThinkingSessions", back_populates="thoughts")
"""
        
        # Write to file
        models_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'crew-api', 'src', 'database', 'models.py')
        with open(models_path, 'w') as f:
            f.write(model_code)
        
        logger.info(f"\n✅ Models generated successfully!")
        logger.info(f"   Output: {models_path}")
        logger.info(f"   Tables processed: {len(tables)}")
        
        if protected_mappings_found:
            logger.info(f"\n📝 Protected name mappings applied:")
            for mapping in protected_mappings_found:
                logger.info(f"   - {mapping}")
        else:
            logger.info(f"\n📝 No protected names found - all column names are safe")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()