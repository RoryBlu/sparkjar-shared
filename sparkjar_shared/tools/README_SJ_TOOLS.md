# SparkJar Tools for CrewAI

## Production Tool Registry

**IMPORTANT**: All SparkJAR tools have been consolidated to single production versions. 
See `tool_registry.py` for the definitive list of current production tools and their capabilities.

To view complete tool documentation:
```python
from src.tools.tool_registry import print_tool_documentation
print_tool_documentation()
```

## Overview

These tools provide CrewAI agents with access to SparkJar's core services:
- Memory API for entity management and semantic search
- Sequential Thinking API for structured thought processes
- Document Service for document conversion and management

**Deprecated Versions**: All v2, v3, and v4 tool versions have been removed. Use only the production versions documented in this file.

## Tools

### 1. SJMemoryTool

The memory tool provides comprehensive entity management and semantic search capabilities.

#### Configuration

```python
from src.tools import SJMemoryTool
from src.tools.sj_memory_tool import MemoryConfig

# Default configuration (uses internal API)
memory_tool = SJMemoryTool()

# Custom configuration for external API
config = MemoryConfig(
    use_internal_api=False,
    external_url="https://memory-external.railway.app",
    api_token="your-jwt-token"
)
memory_tool = SJMemoryTool(config=config)
```

#### Available Operations

1. **create_entity** - Create a new entity (person, organization, concept, etc.)
2. **add_observations** - Add observations/facts about an entity
3. **create_relationship** - Link two entities with a relationship
4. **search_entities** - Semantic search across all entities
5. **get_entity** - Retrieve entity details by ID
6. **get_entity_history** - Get all observations for an entity
7. **get_relationships** - Get all relationships for an entity
8. **extract_from_conversation** - Extract entities and relationships from text

#### Usage Examples

```python
# Create an entity
result = memory_tool._run(
    operation="create_entity",
    name="John Doe",
    entity_type="person",
    metadata={"role": "developer", "location": "San Francisco"}
)

# Add observations
result = memory_tool._run(
    operation="add_observations",
    entity_id="entity-uuid",
    observations=[
        {"type": "skill", "data": {"skill": "Python", "level": "expert"}},
        {"type": "experience", "data": {"company": "TechCorp", "years": 5}}
    ]
)

# Search entities
result = memory_tool._run(
    operation="search_entities",
    query="Python developers in San Francisco",
    entity_type="person",
    limit=5
)

# Extract from conversation
result = memory_tool._run(
    operation="extract_from_conversation",
    conversation="John Doe is a Python expert who worked at TechCorp with Jane Smith."
)
```

### 2. SJSequentialThinkingTool

The sequential thinking tool provides structured thought management with revision tracking.

#### Configuration

```python
from src.tools import SJSequentialThinkingTool
from src.tools.sj_sequential_thinking_tool import ThinkingConfig

# Default configuration (uses internal API)
thinking_tool = SJSequentialThinkingTool()

# Custom configuration
config = ThinkingConfig(
    use_internal_api=False,
    external_url="https://memory-external.railway.app",
    api_token="your-jwt-token"
)
thinking_tool = SJSequentialThinkingTool(config=config)
```

#### Available Operations

1. **create_session** - Start a new thinking session
2. **add_thought** - Add a thought to a session
3. **revise_thought** - Create a revision of an existing thought
4. **get_session** - Retrieve session details and all thoughts
5. **list_sessions** - List thinking sessions with filters
6. **complete_session** - Mark a session as completed
7. **get_session_summary** - Get AI-generated summary of a session
8. **analyze_thinking_pattern** - Analyze patterns in thinking process
9. **search_thoughts** - Search across all thoughts

#### Usage Examples

```python
# Create a thinking session
result = thinking_tool._run(
    operation="create_session",
    client_user_id="user-uuid",
    session_name="Marketing Strategy Planning",
    problem_statement="How to increase user engagement by 50%?"
)

# Add thoughts
result = thinking_tool._run(
    operation="add_thought",
    session_id="session-uuid",
    thought_content="We should analyze current user behavior patterns first.",
    metadata={"category": "analysis", "priority": "high"}
)

# Revise a thought
result = thinking_tool._run(
    operation="revise_thought",
    thought_id="thought-uuid",
    revised_content="We should analyze behavior patterns and identify drop-off points.",
    revision_reason="Added more specific action"
)

# Get session summary
result = thinking_tool._run(
    operation="get_session_summary",
    session_id="session-uuid"
)
```

## Integration in CrewAI

### Adding Tools to Agents

```python
from crewai import Agent
from src.tools import SJMemoryTool, SJSequentialThinkingTool

# Create tools
memory_tool = SJMemoryTool()
thinking_tool = SJSequentialThinkingTool()

# Create agent with tools
research_agent = Agent(
    role="Research Analyst",
    goal="Analyze market data and maintain knowledge base",
    backstory="Expert analyst with deep market knowledge",
    tools=[memory_tool, thinking_tool],
    verbose=True
)
```

### Using in Tasks

```python
from crewai import Task

# Task using memory tool
memory_task = Task(
    description="""
    Search for all entities related to 'artificial intelligence' and 
    create a comprehensive knowledge graph of AI companies, 
    researchers, and technologies.
    """,
    agent=research_agent,
    expected_output="Knowledge graph with entities and relationships"
)

# Task using thinking tool
thinking_task = Task(
    description="""
    Create a thinking session to analyze the AI market landscape.
    Document key insights, trends, and strategic recommendations.
    """,
    agent=research_agent,
    expected_output="Structured analysis with numbered thoughts"
)
```

## Best Practices

1. **Entity Types**: Use consistent entity types (person, organization, concept, technology, etc.)
2. **Observations**: Structure observations with clear types and data
3. **Relationships**: Use descriptive relationship types (works_with, invested_in, developed_by)
4. **Thinking Sessions**: Keep sessions focused on specific problems
5. **Thought Revisions**: Always provide revision reasons for traceability

## Error Handling

Both tools return structured responses with success indicators:

```python
result = tool._run(operation="...", **params)

if result["success"]:
    # Process successful result
    data = result.get("data")
else:
    # Handle error
    error = result.get("error")
    details = result.get("details")
```

## Performance Considerations

1. **Batching**: When adding multiple observations, batch them in a single call
2. **Caching**: Tools maintain HTTP client connections for efficiency
3. **Limits**: Use appropriate limits for search operations
4. **Internal API**: Use internal API when running within Railway network

## Debugging

Enable debug logging:

```python
import logging
logging.getLogger("src.tools").setLevel(logging.DEBUG)
```

This will show detailed information about API calls and responses.

---

### 3. SJDocumentTool

The document tool provides comprehensive document conversion and management capabilities.

#### Configuration

```python
from src.tools import SJDocumentTool
from src.tools.sj_document_tool import DocumentConfig

# Default configuration (uses internal IPv6 API)
document_tool = SJDocumentTool()

# Custom configuration
config = DocumentConfig(
    base_url="http://sparkjar-document-mcp.railway.internal",
    timeout=60,  # Longer timeout for document conversions
    use_ipv6=True
)
document_tool = SJDocumentTool(config=config)
```

#### Available Operations

1. **convert_document** - Convert and save a document to various formats
2. **batch_convert** - Convert multiple documents at once
3. **list_templates** - Get available document templates
4. **get_template** - Retrieve a specific template
5. **create_folder** - Create a new folder
6. **list_folders** - List all folders
7. **list_documents** - List documents in a folder
8. **search_documents** - Search across all documents
9. **organize_documents** - Move and organize documents
10. **get_folder_structure** - Get complete folder hierarchy
11. **check_health** - Check service health status

#### Usage Examples

```python
# Convert a document
result = document_tool._run(
    operation="convert_document",
    source_path="/path/to/document.docx",
    output_format="pdf",
    template_name="professional",
    save_to_folder="/converted/pdfs"
)

# Batch convert documents
result = document_tool._run(
    operation="batch_convert",
    documents=[
        {"source_path": "/doc1.docx", "metadata": {"author": "John"}},
        {"source_path": "/doc2.docx", "metadata": {"author": "Jane"}}
    ],
    output_format="pdf"
)

# Search documents
result = document_tool._run(
    operation="search_documents",
    query="quarterly report",
    document_type="pdf",
    limit=10
)

# Create folder structure
result = document_tool._run(
    operation="create_folder",
    folder_name="2024-Q1-Reports",
    parent_folder="/reports",
    metadata={"year": 2024, "quarter": 1}
)

# Organize documents
result = document_tool._run(
    operation="organize_documents",
    document_ids=["doc1-id", "doc2-id"],
    target_folder="/archive/2024",
    operation="move"  # or "copy"
)
```

### Document Tool Best Practices

1. **Folder Organization**: Use hierarchical folder structures for better organization
2. **Templates**: Use templates for consistent document formatting
3. **Batch Operations**: Use batch_convert for multiple documents to improve efficiency
4. **Search**: Use specific document_type filters to narrow search results
5. **IPv6**: The tool is configured for IPv6 by default for Railway internal communication

### Complete Tool Integration Example

```python
from crewai import Agent, Task, Crew
from src.tools import SJMemoryTool, SJSequentialThinkingTool, SJDocumentTool

# Initialize all tools
memory_tool = SJMemoryTool()
thinking_tool = SJSequentialThinkingTool()
document_tool = SJDocumentTool()

# Create a comprehensive research agent
research_agent = Agent(
    role="Research Analyst",
    goal="Conduct thorough research and document findings",
    backstory="Expert analyst with comprehensive toolset",
    tools=[memory_tool, thinking_tool, document_tool],
    verbose=True
)

# Complex task using all tools
research_task = Task(
    description='''
    1. Search the memory for all entities related to "artificial intelligence"
    2. Create a thinking session to analyze the findings
    3. Generate a comprehensive report and convert it to PDF
    4. Organize all related documents in a structured folder hierarchy
    ''',
    agent=research_agent,
    expected_output="PDF report with organized documentation"
)

# Execute crew
crew = Crew(
    agents=[research_agent],
    tasks=[research_task],
    verbose=True
)
```