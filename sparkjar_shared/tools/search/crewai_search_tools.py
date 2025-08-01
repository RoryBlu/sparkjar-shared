#!/usr/bin/env python3
"""
CrewAI Tool Wrapper for Enhanced Search
Provides CrewAI-compatible search tools for both Google grounding and SERPER
"""

from typing import Type, Optional, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import sys
import os
import logging

# Add the backend tools directory to Python path
from tools.enhanced_search_tool import EnhancedSearchTool, SearchConfig, SearchProvider

logger = logging.getLogger(__name__)

class SearchInput(BaseModel):
    """Input schema for search operations"""
    query: str = Field(..., description="The search query to execute")
    provider: Optional[str] = Field(
        default=None, 
        description="Optional provider override: 'google_grounding', 'serper', or 'auto'"
    )

class GoogleGroundingSearchTool(BaseTool):
    """CrewAI tool for Google Search grounding via Gemini models"""
    
    name: str = "Google Grounding Search"
    description: str = """
    Advanced search tool using Google's grounding capabilities through Gemini models.
    Provides high-quality, fact-checked search results with real-time information.
    Best for: Research, fact-checking, current events, comprehensive analysis.
    """
    args_schema: Type[BaseModel] = SearchInput
    
    def _run(self, query: str, provider: Optional[str] = None) -> str:
        """Execute Google grounding search"""
        try:
            # Create search tool instance for this query
            config = SearchConfig(
                provider="google_grounding",
                enable_grounding=True,
                google_model="gemini-2.0-flash"
            )
            search_tool = EnhancedSearchTool(config)
            result = search_tool.search(query, "google_grounding")
            
            # Format result for CrewAI consumption
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            
            formatted_result = f"""Search Query: {query}
Provider: Google Search Grounding (Gemini {result.get('model', 'Unknown')})
Grounding Enabled: {result.get('grounding_enabled', False)}

Results:
{content}

Metadata: {metadata}"""
            return formatted_result.strip()
            
        except Exception as e:
            return f"Google grounding search failed: {str(e)}"

class SerperSearchTool(BaseTool):
    """CrewAI tool for SERPER search"""
    
    name: str = "SERPER Search"
    description: str = """
    Fast web search tool using SERPER API for quick, structured search results.
    Provides JSON-formatted search results with titles, links, and snippets.
    Best for: Quick searches, structured data extraction, web scraping preparation.
    """
    args_schema: Type[BaseModel] = SearchInput
    
    def _run(self, query: str, provider: Optional[str] = None) -> str:
        """Execute SERPER search"""
        try:
            # Create search tool instance for this query
            config = SearchConfig(
                provider="serper",
                max_results=10
            )
            search_tool = EnhancedSearchTool(config)
            result = search_tool.search(query, "serper")
            
            # Format result for CrewAI consumption
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            
            formatted_result = f"""Search Query: {query}
Provider: SERPER
Configuration: {metadata}

Results:
{content}"""
            return formatted_result.strip()
            
        except Exception as e:
            return f"SERPER search failed: {str(e)}"

class AdaptiveSearchTool(BaseTool):
    """CrewAI tool that automatically selects the best available search provider"""
    
    name: str = "Adaptive Search"
    description: str = """
    Intelligent search tool that automatically selects the best available provider.
    Falls back between Google grounding and SERPER based on availability and performance.
    Best for: Robust search operations, production environments, maximum reliability.
    """
    args_schema: Type[BaseModel] = SearchInput
    
    def _run(self, query: str, provider: Optional[str] = None) -> str:
        """Execute adaptive search with automatic provider selection"""
        try:
            # Create search tool instance for this query
            config = SearchConfig(provider="auto")
            search_tool = EnhancedSearchTool(config)
            
            # Override provider if specified
            effective_provider = provider if provider in ["google_grounding", "serper"] else None
            result = search_tool.search(query, effective_provider)
            
            # Format result for CrewAI consumption
            content = result.get("content", "")
            provider_used = result.get("provider", "unknown")
            metadata = result.get("metadata", {})
            
            formatted_result = f"""Search Query: {query}
Provider Used: {provider_used}
Auto-Selected: {provider is None}

Results:
{content}

Provider Metadata: {metadata}"""
            return formatted_result.strip()
            
        except Exception as e:
            return f"Adaptive search failed: {str(e)}"

# Factory functions for easy tool creation
def create_google_search_tool(**kwargs) -> GoogleGroundingSearchTool:
    """Create a Google grounding search tool"""
    return GoogleGroundingSearchTool(**kwargs)

def create_serper_search_tool(max_results: int = 10, country: Optional[str] = None, **kwargs) -> SerperSearchTool:
    """Create a SERPER search tool"""
    return SerperSearchTool(max_results=max_results, country=country, **kwargs)

def create_adaptive_search_tool(**kwargs) -> AdaptiveSearchTool:
    """Create an adaptive search tool"""
    return AdaptiveSearchTool(**kwargs)

# Convenience function to get the best search tool for a crew
def get_recommended_search_tool(crew_type: str = "general") -> BaseTool:
    """
    Get the recommended search tool based on crew type
    
    Args:
        crew_type: Type of crew ("research", "development", "analysis", "general")
        
    Returns:
        Configured search tool instance
    """
    if crew_type == "research":
        # Research crews benefit from Google grounding's comprehensive results
        return create_google_search_tool()
    elif crew_type == "development":
        # Development crews may prefer faster SERPER results
        return create_serper_search_tool(max_results=5)
    elif crew_type == "analysis":
        # Analysis crews benefit from Google grounding's fact-checking
        return create_google_search_tool()
    else:
        # General crews get adaptive tool for maximum reliability
        return create_adaptive_search_tool()

if __name__ == "__main__":
    # Demo script for testing CrewAI tools
    logger.info("🛠️  CrewAI Search Tools Demo")
    logger.info("=" * 40)
    
    # Test all tool types
    tools = [
        ("Google Grounding", create_google_search_tool()),
        ("SERPER", create_serper_search_tool()),
        ("Adaptive", create_adaptive_search_tool())
    ]
    
    test_query = "CrewAI framework documentation"
    
    for tool_name, tool in tools:
        logger.info("\n🧪 Testing %s Tool:", tool_name)
        logger.info("Description: %s", tool.description.strip())
        
        try:
            result = tool._run(test_query)
            logger.info("✅ Success - Response length: %s characters", len(result))
            # Show first 200 characters
            preview = result[:200] + "..." if len(result) > 200 else result
            logger.info("Preview: %s", preview)
        except Exception as e:
            logger.error("❌ Failed: %s", e)
    
    logger.info("\n📋 Recommended tools by crew type:")
    crew_types = ["research", "development", "analysis", "general"]
    for crew_type in crew_types:
        tool = get_recommended_search_tool(crew_type)
        logger.info("  • %s: %s", crew_type, tool.name)
