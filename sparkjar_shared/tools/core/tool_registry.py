
import logging
logger = logging.getLogger(__name__)

"""
SparkJAR Tool Registry - Single Source of Truth for Production Tools

This registry defines the current production versions of all SparkJAR tools
and provides documentation for their capabilities.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ToolDefinition:
    """Definition of a production tool with its capabilities."""
    name: str
    version: str
    file_path: str
    capabilities: List[str]
    description: str
    config_class: str
    input_schema: str
    deprecated_versions: List[str]

class ToolRegistry:
    """Registry of all production SparkJAR tools."""
    
    PRODUCTION_TOOLS = {
        'memory': ToolDefinition(
            name='sj_memory_tool',
            version='1.0',
            file_path='sj_memory_tool.py',
            capabilities=[
                'Create and manage entities',
                'Add observations to entities',
                'Create relationships between entities',
                'Search entities with filters',
                'Process text chunks for automatic extraction',
                'MCP Registry service discovery',
                'JWT authentication',
                'Hierarchical memory support'
            ],
            description='SparkJar Memory Tool with MCP Registry discovery for comprehensive memory management',
            config_class='MemoryConfig',
            input_schema='SJMemoryToolInput',
            deprecated_versions=['v2', 'v3', 'v4']
        ),
        
        'thinking': ToolDefinition(
            name='sj_sequential_thinking_tool',
            version='1.0',
            file_path='sj_sequential_thinking_tool.py',
            capabilities=[
                'Create and manage thinking sessions',
                'Add thoughts with automatic numbering',
                'Revise thoughts with history tracking',
                'Analyze thinking patterns',
                'Generate session summaries',
                'Support collaborative thinking',
                'Internal and external API support'
            ],
            description='SparkJar Sequential Thinking Tool for structured thought management and analysis',
            config_class='ThinkingConfig',
            input_schema='Built-in JSON parsing',
            deprecated_versions=['v2', 'v3', 'v4']
        ),
        
        'document': ToolDefinition(
            name='sj_document_tool',
            version='1.0',
            file_path='sj_document_tool.py',
            capabilities=[
                'Document conversion (multiple formats)',
                'Batch document processing',
                'Template management',
                'Folder organization',
                'Document search and retrieval',
                'Folder hierarchy management',
                'IPv6 internal communication'
            ],
            description='SparkJar Document Tool for comprehensive document management and conversion',
            config_class='DocumentConfig',
            input_schema='Built-in JSON parsing',
            deprecated_versions=['v2', 'v3', 'v4']
        )
    }
    
    @classmethod
    def get_tool(cls, tool_type: str) -> Optional[ToolDefinition]:
        """Get the production version of a tool."""
        return cls.PRODUCTION_TOOLS.get(tool_type)
    
    @classmethod
    def list_tools(cls) -> List[str]:
        """List all available tool types."""
        return list(cls.PRODUCTION_TOOLS.keys())
    
    @classmethod
    def get_tool_capabilities(cls, tool_type: str) -> List[str]:
        """Get capabilities of a specific tool."""
        tool = cls.get_tool(tool_type)
        return tool.capabilities if tool else []
    
    @classmethod
    def validate_tool_exists(cls, tool_type: str) -> bool:
        """Validate that a tool type exists in the registry."""
        return tool_type in cls.PRODUCTION_TOOLS
    
    @classmethod
    def get_deprecated_versions(cls, tool_type: str) -> List[str]:
        """Get list of deprecated versions for a tool."""
        tool = cls.get_tool(tool_type)
        return tool.deprecated_versions if tool else []
    
    @classmethod
    def generate_import_statement(cls, tool_type: str) -> str:
        """Generate the correct import statement for a tool."""
        tool = cls.get_tool(tool_type)
        if not tool:
            raise ValueError(f"Tool type '{tool_type}' not found in registry")
        
        # Map tool names to their actual class names
        class_names = {
            'sj_memory_tool': 'SJMemoryTool',
            'sj_sequential_thinking_tool': 'SJSequentialThinkingTool',
            'sj_document_tool': 'SJDocumentTool'
        }
        
        class_name = class_names.get(tool.name, tool.name)
        return f"from src.tools.{tool.file_path.replace('.py', '')} import {class_name}"
    
    @classmethod
    def get_migration_guide(cls, tool_type: str, from_version: str) -> str:
        """Get migration guide for upgrading from deprecated version."""
        tool = cls.get_tool(tool_type)
        if not tool:
            return f"Tool type '{tool_type}' not found"
        
        if from_version not in tool.deprecated_versions:
            return f"Version '{from_version}' is not a known deprecated version"
        
        class_name = ''.join(word.capitalize() for word in tool.name.split('_'))
        
        return f"""
Migration Guide: {tool.name}_{from_version} → {tool.name} (v{tool.version})

OLD IMPORT:
from tools.{tool.name}_{from_version} import {class_name}

NEW IMPORT:
from src.tools.{tool.name} import {class_name}

CHANGES:
- All functionality from {from_version} is included in the production version
- Configuration uses {tool.config_class} class
- Input validation uses {tool.input_schema}
- Enhanced error handling and logging
- MCP Registry integration (for memory tool)
- Improved performance and reliability

CAPABILITIES:
{chr(10).join(f'- {cap}' for cap in tool.capabilities)}

No code changes required beyond updating the import statement.
"""

def print_tool_documentation():
    """Print comprehensive documentation for all tools."""
    logger.info("SparkJAR Production Tools Documentation")
    logger.info("=" * 50)
    
    for tool_type, tool in ToolRegistry.PRODUCTION_TOOLS.items():
        logger.info(f"\n{tool.name.upper()} (v{tool.version})")
        logger.info("-" * 30)
        logger.info(f"Description: {tool.description}")
        logger.info(f"File: {tool.file_path}")
        logger.info(f"Config Class: {tool.config_class}")
        logger.info(f"Input Schema: {tool.input_schema}")
        
        logger.info("\nCapabilities:")
        for cap in tool.capabilities:
            logger.info(f"  • {cap}")
        
        logger.info(f"\nDeprecated Versions: {', '.join(tool.deprecated_versions)}")
        
        logger.info(f"\nImport Statement:")
        logger.info(f"  {ToolRegistry.generate_import_statement(tool_type)}")

if __name__ == "__main__":
    print_tool_documentation()