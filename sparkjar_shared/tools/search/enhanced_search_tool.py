#!/usr/bin/env python3
"""
Enhanced Search Tool System for SparkJar CrewAI
Provides configurable search capabilities using Google Search grounding and SERPER
"""

import os
import json
import logging
from typing import Dict, List, Optional, Union, Literal
from dataclasses import dataclass
import google.generativeai as genai
from crewai_tools import SerperDevTool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

SearchProvider = Literal["google_grounding", "serper", "auto"]

@dataclass
class SearchConfig:
    """Configuration for search operations"""
    provider: SearchProvider = "auto"
    max_results: int = 10
    country: Optional[str] = None
    locale: Optional[str] = None
    location: Optional[str] = None
    
    # Google-specific settings
    google_model: str = "gemini-2.0-flash"
    enable_grounding: bool = True
    
    # SERPER-specific settings
    serper_search_url: str = "https://google.serper.dev/search"

class EnhancedSearchTool:
    """
    Unified search tool that can use Google Search grounding or SERPER
    Provides intelligent fallback and configurable search strategies
    """
    
    def __init__(self, config: Optional[SearchConfig] = None):
        self.config = config or SearchConfig()
        self._setup_providers()
    
    def _setup_providers(self):
        """Initialize available search providers"""
        self.providers = {}
        
        # REMOVED BY RORY - GOOGLE_API_KEY not used in this repo
        # # Setup Google Grounding if API key available
        # google_api_key = os.getenv("GOOGLE_API_KEY")
        # if google_api_key:
        #     try:
        #         genai.configure(api_key=google_api_key)
        #         self.providers["google_grounding"] = True
        #         logger.info("✅ Google Search grounding available")
        #     except Exception as e:
        #         logger.error("⚠️  Google Search grounding setup failed: %s", e)
        #         self.providers["google_grounding"] = False
        # else:
        #     self.providers["google_grounding"] = False
        self.providers["google_grounding"] = False
            
        # REMOVED BY RORY - SERPER_API_KEY not used in this repo
        # # Setup SERPER if API key available
        # serper_api_key = os.getenv("SERPER_API_KEY")
        # if serper_api_key:
        #     try:
        #         self.serper_tool = SerperDevTool(
        #             search_url=self.config.serper_search_url,
        #             n_results=self.config.max_results,
        #             country=self.config.country,
        #             locale=self.config.locale,
        #             location=self.config.location
        #         )
        #         self.providers["serper"] = True
        #         logger.info("✅ SERPER search available")
        #     except Exception as e:
        self.providers["serper"] = False
        try:
            pass
        except Exception as e:
                logger.error("⚠️  SERPER search setup failed: %s", e)
                self.providers["serper"] = False
        else:
            self.providers["serper"] = False
    
    def _choose_provider(self) -> str:
        """Intelligently choose the best available provider"""
        if self.config.provider != "auto":
            if self.providers.get(self.config.provider, False):
                return self.config.provider
            else:
                logger.warning(
                    "⚠️  Requested provider '%s' not available, falling back to auto selection",
                    self.config.provider,
                )
        
        # Auto selection priority: Google grounding > SERPER
        if self.providers.get("google_grounding", False):
            return "google_grounding"
        elif self.providers.get("serper", False):
            return "serper"
        else:
            raise RuntimeError("No search providers available. Check your API keys.")
    
    def search(self, query: str, provider: Optional[SearchProvider] = None) -> Dict:
        """
        Perform search using the specified or auto-selected provider
        
        Args:
            query: Search query string
            provider: Optional provider override
            
        Returns:
            Dict containing search results and metadata
        """
        effective_provider = provider or self._choose_provider()
        
        try:
            if effective_provider == "google_grounding":
                return self._search_google_grounding(query)
            elif effective_provider == "serper":
                return self._search_serper(query)
            else:
                raise ValueError(f"Unknown provider: {effective_provider}")
                
        except Exception as e:
            logger.error("❌ Search failed with %s: %s", effective_provider, e)
            # Try fallback provider
            fallback_providers = [p for p in ["google_grounding", "serper"] 
                                if p != effective_provider and self.providers.get(p, False)]
            
            if fallback_providers:
                fallback_provider = fallback_providers[0]
                logger.info("🔄 Trying fallback provider: %s", fallback_provider)
                return self.search(query, fallback_provider)
            else:
                raise RuntimeError(f"All search providers failed. Last error: {e}")
    
    def _search_google_grounding(self, query: str) -> Dict:
        """Search using Google's grounding capabilities through Gemini"""
        try:
            # Use Gemini 2.0 Flash which has built-in web access capabilities
            model = genai.GenerativeModel(model_name=self.config.google_model)
            
            # Craft search prompt that leverages Gemini's web knowledge
            search_prompt = f"""
            Search for and provide comprehensive information about: {query}
            
            Please provide current, accurate information including:
            1. Key findings and recent developments
            2. Important facts and statistics
            3. Relevant sources and references
            4. Recent news or updates (if applicable)
            
            Focus on providing factual, well-sourced information that would be useful for research and analysis.
            If you find specific websites, articles, or sources, please mention them.
            """
            
            response = model.generate_content(search_prompt)
            
            return {
                "provider": "google_grounding",
                "query": query,
                "model": self.config.google_model,
                "grounding_enabled": self.config.enable_grounding,
                "content": response.text,
                "metadata": {
                    "finish_reason": getattr(response.candidates[0], 'finish_reason', None) if hasattr(response, 'candidates') and response.candidates else None,
                    "safety_ratings": getattr(response.candidates[0], 'safety_ratings', None) if hasattr(response, 'candidates') and response.candidates else None,
                    "model_used": self.config.google_model
                }
            }
            
        except Exception as e:
            raise RuntimeError(f"Google grounding search failed: {e}")
    
    def _search_serper(self, query: str) -> Dict:
        """Search using SERPER tool"""
        try:
            results = self.serper_tool.run(search_query=query)
            
            return {
                "provider": "serper",
                "query": query,
                "content": results,
                "metadata": {
                    "search_url": self.config.serper_search_url,
                    "max_results": self.config.max_results,
                    "country": self.config.country,
                    "locale": self.config.locale,
                    "location": self.config.location
                }
            }
            
        except Exception as e:
            raise RuntimeError(f"SERPER search failed: {e}")
    
    def get_available_providers(self) -> Dict[str, bool]:
        """Get status of all search providers"""
        return self.providers.copy()
    
    def test_all_providers(self, test_query: str = "artificial intelligence latest developments") -> Dict:
        """Test all available providers with a sample query"""
        results = {}
        
        for provider_name, available in self.providers.items():
            if available:
                try:
                    result = self.search(test_query, provider_name)
                    results[provider_name] = {
                        "status": "success",
                        "response_length": len(str(result.get("content", ""))),
                        "metadata": result.get("metadata", {})
                    }
                except Exception as e:
                    results[provider_name] = {
                        "status": "failed", 
                        "error": str(e)
                    }
            else:
                results[provider_name] = {"status": "unavailable"}
        
        return results

def create_search_tool(provider: SearchProvider = "auto", **kwargs) -> EnhancedSearchTool:
    """
    Factory function to create a configured search tool
    
    Args:
        provider: Search provider to use ("google_grounding", "serper", "auto")
        **kwargs: Additional configuration options
        
    Returns:
        Configured EnhancedSearchTool instance
    """
    config = SearchConfig(provider=provider, **kwargs)
    return EnhancedSearchTool(config)

if __name__ == "__main__":
    # Demo/test script
    logger.info("🔍 Enhanced Search Tool Demo")
    logger.info("=" * 50)
    
    # Create search tool with auto provider selection
    search_tool = create_search_tool()
    
    # Show available providers
    providers = search_tool.get_available_providers()
    logger.info("\n📊 Available Providers:")
    for provider, available in providers.items():
        status = "✅ Available" if available else "❌ Unavailable"
        logger.info("  • %s: %s", provider, status)
    
    # Test search if any providers are available
    if any(providers.values()):
        logger.info("\n🧪 Testing search with query: 'CrewAI framework latest features'")
        try:
            result = search_tool.search("CrewAI framework latest features")
            logger.info("\n✅ Search successful using: %s", result['provider'])
            logger.info("📄 Response length: %s characters", len(str(result['content'])))
            
            # Show first 300 characters of response
            content = str(result['content'])
            preview = content[:300] + "..." if len(content) > 300 else content
            logger.info("\n📖 Preview:\n%s", preview)
            
        except Exception as e:
            logger.error("\n❌ Search failed: %s", e)
    else:
        logger.warning("\n⚠️  No search providers available. Please check your API keys:")
        # REMOVED BY RORY - These env vars not used
        # logger.warning("  • GOOGLE_API_KEY: %s", '✅ Set' if os.getenv('GOOGLE_API_KEY') else '❌ Missing')
        # logger.warning("  • SERPER_API_KEY: %s", '✅ Set' if os.getenv('SERPER_API_KEY') else '❌ Missing')
