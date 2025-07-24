# Scripts Directory

This directory contains utility scripts for managing and maintaining the SparkJAR Crew system.

## Database Management Scripts

### Core Database Operations
- **`reset_database.py`** - Reset and reinitialize the database schema (WARNING: destructive!)
- **`UPDATE_MODELS.py`** - Generate SQLAlchemy models from database schema
- **`inspect_db_schema.py`** - Inspect current database schema and tables
- **`examine_schema.py`** - Examine specific table schemas in detail

### Data Seeding
- **`seed_crew_configs.py`** - Seed initial crew configurations
- **`seed_memory_schemas.py`** - Seed memory observation schemas for validation
- **`create_mcp_registry_tables.py`** - Create tables for MCP service registry

### Schema Files
- **`sequential_thinking_schema.sql`** - SQL schema definition for sequential thinking feature

## Development Utilities

- **`dev_utils.py`** - Development helper functions for testing connections and debugging
- **`fix_vscode_ghost_files.sh`** - Shell script to fix VSCode ghost file issues

## Usage

Most scripts can be run directly with Python from the project root:

```bash
# Update models from database
.venv/bin/python scripts/UPDATE_MODELS.py

# Reset database (WARNING: destructive!)
.venv/bin/python scripts/reset_database.py

# Seed initial data
.venv/bin/python scripts/seed_crew_configs.py
.venv/bin/python scripts/seed_memory_schemas.py

# Inspect database schema
.venv/bin/python scripts/inspect_db_schema.py
```

## Important Notes

- **Always backup your database** before running reset or schema modification scripts
- The `UPDATE_MODELS.py` script should be run after any database schema changes to regenerate SQLAlchemy models
- Most scripts require proper environment variables to be set (DATABASE_URL, etc.)
- Scripts assume they're run from the project root directory with the virtual environment activated

## Script Maintenance

When adding new scripts:
1. Follow the naming convention: `verb_noun.py` (e.g., `seed_crews.py`, `reset_cache.py`)
2. Add appropriate documentation at the top of the script
3. Update this README with the script's purpose
4. Ensure the script handles errors gracefully and provides helpful output