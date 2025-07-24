#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Fix import issues for testing by ensuring proper package imports.
This script is deprecated - imports should use proper package structure.
"""
import os
import sys
from pathlib import Path

def fix_memory_service_imports():
    """Update memory service to use correct import paths."""
    memory_manager_path = "services/memory-service/services/memory_manager.py"
    
    if os.path.exists(memory_manager_path):
        with open(memory_manager_path, 'r') as f:
            content = f.read()
        
        # Replace the import to use proper package imports
        old_import = "from services.crew_api.src.database.models import MemoryEntities, MemoryRelations, ObjectSchemas, MemoryObservations"
        new_import = "from sparkjar_crew.shared.database.models import MemoryEntities, MemoryRelations, ObjectSchemas, MemoryObservations"
        
        if old_import in content:
            content = content.replace(old_import, new_import)
            
            with open(memory_manager_path, 'w') as f:
                f.write(content)
            logger.info(f"✅ Fixed imports in {memory_manager_path}")
        else:
            logger.info(f"⚠️  Import already fixed or different in {memory_manager_path}")

def validate_package_structure():
    """Validate that the package structure is correct for proper imports."""
    project_root = Path(__file__).parent.parent
    
    # Check if the package is installed in development mode
    try:
        import sparkjar_crew
        logger.info(f"✅ sparkjar_crew package is available at: {sparkjar_crew.__file__}")
        return True
    except ImportError:
        logger.info("❌ sparkjar_crew package not found. Please install with: pip install -e .")
        return False

if __name__ == "__main__":
    logger.info("Validating package structure for proper imports...")
    
    if validate_package_structure():
        logger.info("✅ Package structure is correct")
        fix_memory_service_imports()
    else:
        logger.info("❌ Please fix package installation first")
        sys.exit(1)
    
    logger.info("Done!")