from typing import Any, Optional, Type

import chromadb
from pydantic import BaseModel, Field

from crewai_tools.tools.rag.rag_tool import RagTool

class FixedWebsiteSearchToolSchema(BaseModel):
    """Input for WebsiteSearchTool."""

    search_query: str = Field(
        ...,
        description="Mandatory search query you want to use to search a specific website",
    )

class WebsiteSearchToolSchema(FixedWebsiteSearchToolSchema):
    """Input for WebsiteSearchTool."""

    website: str = Field(
        ..., description="Mandatory valid website URL you want to search on"
    )

class WebsiteSearchTool(RagTool):
    name: str = "Search in a specific website"
    description: str = (
        "A tool that can be used to semantic search a query from a specific URL content."
    )
    args_schema: Type[BaseModel] = WebsiteSearchToolSchema

    def __init__(self, website: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.client = chromadb.Client()
        if website is not None:
            self.add(website)
            self.description = f"A tool that can be used to semantic search a query from {website} website content."
            self.args_schema = FixedWebsiteSearchToolSchema
            self._generate_description()

    def add(self, website: str) -> None:
        # Example of adding website data to ChromaDB
        self.client.add(collection_name="web_pages", documents=[website])

    def _run(
        self,
        search_query: str,
        website: Optional[str] = None,
    ) -> str:
        if website is not None:
            self.add(website)
        # Example of querying ChromaDB
        results = self.client.query(collection_name="web_pages", query_text=search_query)
        return results[0] if results else "No results found."
