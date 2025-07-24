#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Tool Version Migration Script

This script helps migrate from deprecated tool versions (v2, v3, v4) to the 
consolidated production versions.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

def find_deprecated_imports(directory: Path) -> List[Tuple[Path, str, str]]:
    """Find all files with deprecated tool imports."""
    deprecated_imports = []
    
    # Patterns to match deprecated imports
    patterns = [
        r'from\s+.*sj_memory_tool_v[234]\s+import',
        r'from\s+.*sj_sequential_thinking_tool_v[234]\s+import',
        r'from\s+.*sj_document_tool_v[234]\s+import',
        r'import\s+.*sj_memory_tool_v[234]',
        r'import\s+.*sj_sequential_thinking_tool_v[234]',
        r'import\s+.*sj_document_tool_v[234]'
    ]
    
    for py_file in directory.rglob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    deprecated_imports.append((py_file, match.group(), pattern))
        except Exception as e:
            logger.error(f"Error reading {py_file}: {e}")
    
    return deprecated_imports

def suggest_migration(deprecated_import: str) -> str:
    """Suggest the correct import for a deprecated import."""
    # Extract tool type and version
    if 'memory_tool_v' in deprecated_import:
        return "from src.tools.sj_memory_tool import SJMemoryTool"
    elif 'sequential_thinking_tool_v' in deprecated_import:
        return "from src.tools.sj_sequential_thinking_tool import SJSequentialThinkingTool"
    elif 'document_tool_v' in deprecated_import:
        return "from src.tools.sj_document_tool import SJDocumentTool"
    else:
        return "# Unable to determine correct import"

def main():
    """Main migration function."""
    logger.info("SparkJAR Tool Version Migration Script")
    logger.info("=" * 50)
    
    # Check current directory
    current_dir = Path.cwd()
    logger.info(f"Scanning directory: {current_dir}")
    
    # Find deprecated imports
    deprecated_imports = find_deprecated_imports(current_dir)
    
    if not deprecated_imports:
        logger.info("✅ No deprecated tool imports found!")
        return
    
    logger.info(f"\n⚠️  Found {len(deprecated_imports)} deprecated tool imports:")
    logger.info("-" * 50)
    
    for file_path, import_line, pattern in deprecated_imports:
        rel_path = file_path.relative_to(current_dir)
        logger.info(f"\nFile: {rel_path}")
        logger.info(f"Deprecated: {import_line.strip()}")
        logger.info(f"Suggested:  {suggest_migration(import_line)}")
    
    logger.info("\n" + "=" * 50)
    logger.info("Migration Instructions:")
    logger.info("1. Replace deprecated imports with suggested imports")
    logger.info("2. Remove any versioned tool files (v2, v3, v4)")
    logger.info("3. Clear __pycache__ directories")
    logger.info("4. Test your crews to ensure they work correctly")
    
    logger.info("\nFor detailed migration guides, run:")
    logger.info("python3 -c \"from tools.tool_registry import ToolRegistry; print(ToolRegistry.get_migration_guide('memory', 'v2'))\"")
    
    logger.info("\nFor complete tool documentation, run:")
    logger.info("python3 -c \"from tools.tool_registry import print_tool_documentation; print_tool_documentation()\"")

if __name__ == "__main__":
    main()