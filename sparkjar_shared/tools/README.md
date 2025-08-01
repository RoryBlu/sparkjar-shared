# SparkJar CrewAI - Custom Tools

This directory contains custom CrewAI tools specific to the SparkJar application. These tools extend CrewAI's capabilities with domain-specific functionality.

## Available Tools

### `context_query_tool.py`
**Purpose**: Database context query tool for extracting relevant information from multiple tables  
**Status**: 🚧 In Development  
**Usage**: Provides context-aware database queries for crew operations

## Usage

Import tools into your crew configurations:

```python
from src.tools.context_query_tool import ContextQueryTool

# In your crew configuration
tools = [ContextQueryTool()]
```

## Development

When creating new tools:
1. Follow CrewAI tool patterns and interfaces
2. Include proper error handling and logging
3. Add clear docstrings and usage examples
4. Update this README with tool descriptions

## Integration

Tools in this directory are designed to work with:
- CrewAI agents and crews
- The SparkJar database models
- Application-specific context and workflows
