"""
Custom tools package for SparkJar CrewAI application.
"""

# Import available tools for easy access
try:
    from .context_query_tool import ContextQueryTool
    from .pdf_generator import PDFGeneratorTool
    from .sj_memory_tool import SJMemoryTool
    from .sj_memory_tool_hierarchical import (
        SJMemoryToolHierarchical,
        HierarchicalMemoryConfig,
        create_hierarchical_memory_tool
    )
    from .sj_sequential_thinking_tool import SJSequentialThinkingTool
    from .sj_document_tool import SJDocumentTool
    
    __all__ = [
        'ContextQueryTool',
        'PDFGeneratorTool',
        'SJMemoryTool',
        'SJMemoryToolHierarchical',
        'HierarchicalMemoryConfig',
        'create_hierarchical_memory_tool',
        'SJSequentialThinkingTool',
        'SJDocumentTool'
    ]
except ImportError:
    # Handle case where dependencies might not be available
    __all__ = []
