# Hierarchical Memory Tool Guide for CrewAI

## Overview

The Hierarchical Memory Tool extends the standard SJMemoryTool to support memory inheritance patterns, enabling synths to access:
- **Own memories**: Personal experiences and learnings
- **Synth_class templates**: Inherited procedures, SOPs, and guidelines
- **Client knowledge**: Organizational policies and shared resources (optional)

## Key Features

### 1. Hierarchical Search
Searches across multiple memory contexts with a single query:
```json
{
  "action": "search_entities",
  "params": {
    "query": "blog writing procedures",
    "include_hierarchy": true
  }
}
```

### 2. Template Discovery
Find procedures and SOPs from your synth_class:
```json
{
  "action": "search_templates",
  "params": {
    "query": "writing guidelines"
  }
}
```

### 3. Context Awareness
Results indicate where memories came from:
- `"_context_note": "From your synth_class template"`
- `"_context_note": "From your personal memories"`
- `"_context_note": "From organizational knowledge"`

## Usage in CrewAI

### Basic Setup

```python
from crewai import Agent
from services.crew-api.src.tools import create_hierarchical_memory_tool

# Create tool for a specific synth
memory_tool = create_hierarchical_memory_tool(
    actor_type="synth",
    actor_id="synth-uuid-here",
    client_id="client-uuid-here"
)

# Create agent with hierarchical memory
agent = Agent(
    role="Blog Writer",
    goal="Create high-quality blog posts following established procedures",
    tools=[memory_tool],
    verbose=True
)
```

### Advanced Configuration

```python
from services.crew-api.src.tools import HierarchicalMemoryConfig, SJMemoryToolHierarchical

# Custom configuration
config = HierarchicalMemoryConfig(
    enable_hierarchy=True,
    include_synth_class=True,  # Access templates
    include_client=False,      # No org-wide access
    enable_cross_context=True  # Allow explicit cross-context
)

# Create configured tool
memory_tool = SJMemoryToolHierarchical(config=config)
memory_tool.set_actor_context("synth", synth_id, client_id)
```

## Action Reference

### Enhanced Search Actions

#### 1. search_entities (Enhanced)
Standard search with optional hierarchy:
```json
{
  "action": "search_entities",
  "params": {
    "query": "blog procedures",
    "entity_type": "procedure",
    "include_hierarchy": true,
    "limit": 10
  }
}
```

**Response includes**:
- Results from multiple contexts
- `access_source` field indicating origin
- `_context_note` for human readability

#### 2. search_hierarchical
Fine-grained control over contexts:
```json
{
  "action": "search_hierarchical",
  "params": {
    "query": "writing SOP",
    "include_synth_class": true,
    "include_client": false,
    "limit": 5
  }
}
```

**Response includes**:
- `results_by_context`: Grouped by source
- Context counts for each source
- All standard entity fields

#### 3. search_templates
Search only synth_class templates:
```json
{
  "action": "search_templates",
  "params": {
    "query": "blog writing"
  }
}
```

**Response**:
- Only templates from your synth_class
- Filtered to procedure-type entities
- Clear indication of template source

#### 4. access_cross_context
Explicitly access another context:
```json
{
  "action": "access_cross_context",
  "params": {
    "target_type": "synth_class",
    "target_id": "24",
    "query": "advanced techniques"
  }
}
```

**Use cases**:
- Access specific synth_class procedures
- View shared team resources
- Debug memory inheritance

### Standard Actions (Unchanged)

#### create_entity
```json
{
  "action": "create_entity",
  "params": {
    "name": "Python Best Practices Blog",
    "entity_type": "content_output",
    "metadata": {
      "word_count": 1200,
      "seo_score": 92
    }
  }
}
```

#### add_observation
```json
{
  "action": "add_observation",
  "params": {
    "entity_name": "Python Best Practices Blog",
    "observation": "Used new keyword research technique",
    "observation_type": "technique_used"
  }
}
```

#### create_relationship
```json
{
  "action": "create_relationship",
  "params": {
    "from_entity_name": "Python Best Practices Blog",
    "to_entity_name": "Blog Writing SOP v3.0",
    "relationship_type": "followed_procedure"
  }
}
```

## Common Workflows

### 1. Finding and Following Procedures

```python
# Agent task to find procedures
find_procedures_task = Task(
    description="Find the standard blog writing procedures",
    agent=writer_agent,
    tools=[memory_tool],
    expected_output="List of relevant procedures with steps"
)

# Agent will use:
# {"action": "search_templates", "params": {"query": "blog writing SOP"}}
```

### 2. Creating Content with Templates

```python
# Agent task to create blog following SOP
create_blog_task = Task(
    description="""
    Create a blog post about Python decorators following our standard procedures.
    First, find the blog writing SOP, then follow each phase.
    """,
    agent=writer_agent,
    tools=[memory_tool, writing_tool],
    expected_output="Complete blog post with metadata"
)

# Agent will:
# 1. Search for SOP: {"action": "search_templates", "params": {"query": "blog SOP"}}
# 2. Create entity: {"action": "create_entity", "params": {...}}
# 3. Add observations about following the SOP
```

### 3. Learning from Experience

```python
# Task to improve based on past experiences
improvement_task = Task(
    description="""
    Review past blog posts and their performance metrics.
    Identify patterns in successful posts and update your approach.
    """,
    agent=analyst_agent,
    tools=[memory_tool],
    expected_output="Insights and recommendations"
)

# Agent will search both own memories and templates:
# {"action": "search_hierarchical", "params": {"query": "blog performance metrics"}}
```

## Best Practices

### 1. Use Appropriate Search Scope
- Use `search_templates` for procedures and guidelines
- Use `search_entities` with hierarchy for general searches
- Use standard search (no hierarchy) for private/personal memories

### 2. Create Meaningful Relationships
Always link outputs to the procedures followed:
```json
{
  "action": "create_relationship",
  "params": {
    "from_entity_name": "Your Blog Post",
    "to_entity_name": "Blog SOP v3.0",
    "relationship_type": "followed_procedure",
    "metadata": {
      "phases_completed": [1, 2, 3, 4],
      "time_taken_hours": 3.5
    }
  }
}
```

### 3. Track Performance
Add observations about what worked:
```json
{
  "action": "add_observation",
  "params": {
    "entity_name": "Your Blog Post",
    "observation": "Keyword research phase led to 40% better ranking",
    "observation_type": "performance_insight"
  }
}
```

### 4. Handle Missing Templates Gracefully
```python
# In your agent's instructions
"""
If you cannot find specific procedures:
1. Search more broadly (remove specific terms)
2. Check if you have the right synth_class
3. Create a basic approach and document it for future use
"""
```

## Troubleshooting

### "No templates found"
- Verify your synth has a synth_class_id assigned
- Check that templates exist at the synth_class level
- Try broader search terms

### "Permission denied for cross-context"
- Ensure `enable_cross_context` is True in config
- Verify JWT token has proper permissions
- Check target context exists and is accessible

### "Slow performance"
- Hierarchical searches may take longer
- Use specific entity_types to narrow results
- Consider using standard search when hierarchy isn't needed

## Migration from Standard Tool

### Minimal Changes
```python
# Old
from tools import SJMemoryTool
tool = SJMemoryTool()

# New (drop-in replacement)
from tools import SJMemoryToolHierarchical
tool = SJMemoryToolHierarchical()
```

### Taking Advantage of Hierarchy
```python
# Enhanced usage
tool = create_hierarchical_memory_tool(
    actor_type="synth",
    actor_id=synth_id,
    client_id=client_id
)

# Now your agents can access templates!
```

## Example: Blog Writing Agent with Templates

```python
from crewai import Agent, Task, Crew
from tools import create_hierarchical_memory_tool

# Create memory tool
memory_tool = create_hierarchical_memory_tool(
    actor_type="synth",
    actor_id="blog-writer-synth-id",
    client_id="your-client-id"
)

# Create blog writer agent
blog_writer = Agent(
    role="SEO Blog Writer",
    goal="Create high-quality blogs following established procedures",
    backstory="""You are an expert blog writer who follows proven SOPs 
    to create engaging, SEO-optimized content. You always check for 
    the latest procedures before starting.""",
    tools=[memory_tool],
    verbose=True
)

# Create task
write_blog_task = Task(
    description="""
    Write a blog post about 'Python Type Hints Best Practices'.
    
    Steps:
    1. Search for our blog writing SOP and study it
    2. Follow each phase of the procedure
    3. Create the blog post entity with all metadata
    4. Link the blog to the SOP you followed
    5. Add observations about the process
    """,
    agent=blog_writer,
    expected_output="Complete blog post following our SOP"
)

# Run crew
crew = Crew(
    agents=[blog_writer],
    tasks=[write_blog_task]
)

result = crew.kickoff()
```

This agent will automatically:
1. Find blog writing procedures from synth_class templates
2. Follow the structured approach
3. Create proper memory entities
4. Build knowledge over time