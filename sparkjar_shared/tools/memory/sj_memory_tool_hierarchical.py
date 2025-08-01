"""
Import the hierarchical memory tool from the shared location.
This ensures we have a single source of truth for the tool.
"""
# Add the shared path to sys.path if needed
import sys
from pathlib import Path
shared_path = Path(__file__).parent.parent.parent.parent / "sparkjar-shared"
if str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

# Import everything from the shared tool
from tools.memory.sj_memory_tool_hierarchical import *