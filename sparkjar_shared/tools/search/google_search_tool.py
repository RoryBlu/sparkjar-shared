"""Google Search Tool for CrewAI agents."""
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from utils.google_search import search_web

class GoogleSearchToolSchema(BaseModel):
    """Input for GoogleSearchTool."""
    
    query: str = Field(
        ...,
        description="Search query to find information on the web"
    )
    num_results: int = Field(
        default=3,
        description="Number of search results to return (max 10)"
    )

class GoogleSearchTool(BaseTool):
    name: str = "Google Search"
    description: str = "Search the web using Google Custom Search API to find current information"
    args_schema: Type[BaseModel] = GoogleSearchToolSchema

    def _run(self, query: str, num_results: int = 3) -> str:
        """Execute the search."""
        try:
            results = search_web(query, num_results)
            
            if not results:
                return "No search results found or Google API not configured."
            
            # Format results for agent consumption
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(
                    f"{i}. {result['title']}\n"
                    f"   URL: {result['link']}\n"
                    f"   {result['snippet']}"
                )
            
            return "\n\n".join(formatted_results)
            
        except Exception as e:
            return f"Error performing search: {str(e)}"