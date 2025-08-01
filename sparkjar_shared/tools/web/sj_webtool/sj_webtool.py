"""Integration layer for the headless scraping service.

This module exposes :class:`SJWebTool`, a simple `BaseTool` implementation that
invokes :class:`HeadlessScraper` and returns a short text summary. It hides the
asynchronous Playwright logic behind a synchronous interface so that agents can
use it without worrying about event loops.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Optional, Type

from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .headless_scraper import HeadlessScraper, ScrapeRequest

class SJWebToolSchema(BaseModel):
    """Input schema for :class:`SJWebTool`."""

    url: str = Field(..., description="Page URL to scrape")
    render_js: bool = Field(default=True, description="Render JavaScript")
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Extra HTTP headers"
    )
    cookies: Optional[str] = Field(default=None, description="Cookie header string")
    session_id: Optional[str] = Field(
        default=None, description="Reuse session across calls"
    )
    wait_for_selector: Optional[str] = Field(
        default=None, description="CSS selector to wait for"
    )
    wait_for_ms: Optional[int] = Field(
        default=None, description="Delay after load in ms"
    )
    wait_for_event: Optional[str] = Field(
        default=None, description="Load state event to wait for"
    )
    script: Optional[str] = Field(
        default=None, description="JavaScript to run in page context"
    )

class SJWebTool(BaseTool):
    """Scrape a page and return a short text preview."""

    name: str = "SJ Web Scraper"
    description: str = (
        "Fetch a page with the internal headless browser and return a concise"
        " summary for agent consumption."
    )
    args_schema: Type[BaseModel] = SJWebToolSchema

    def _run(
        self,
        url: str,
        render_js: bool = True,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[str] = None,
        session_id: Optional[str] = None,
        wait_for_selector: Optional[str] = None,
        wait_for_ms: Optional[int] = None,
        wait_for_event: Optional[str] = None,
        script: Optional[str] = None,
    ) -> str:
        scraper = HeadlessScraper()
        req = ScrapeRequest(
            url=url,
            render_js=render_js,
            headers=headers or {},
            cookies=cookies,
            session_id=session_id,
            wait_for_selector=wait_for_selector,
            wait_for_ms=wait_for_ms,
            wait_for_event=wait_for_event,
            script=script,
        )
        # ``scrape`` is async so we manage the event loop manually.
        coro = scraper.scrape(req)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            result = new_loop.run_until_complete(coro)
            new_loop.close()
        else:
            result = loop.run_until_complete(coro)
        html = result.get("html", "")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        title = soup.title.string.strip() if soup.title else ""
        preview = text[:500] + ("..." if len(text) > 500 else "")
        return (
            f"URL: {url}\nTitle: {title}\nPreview: {preview}\n"
            f"Session ID: {result.get('session_id')}\n"
            f"Total Time: {result.get('timings', {}).get('total_ms')}ms"
        )
