"""Headless scraping helpers using Playwright."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
import redis.asyncio as redis
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

from backend import supabase_helper as sh

class ScrapeRequest(BaseModel):
    """Incoming scrape request."""

    url: str
    render_js: bool = True
    headers: Dict[str, str] = Field(default_factory=dict)
    cookies: Optional[str] = None
    session_id: Optional[str] = None
    wait_for_selector: Optional[str] = None
    wait_for_ms: Optional[int] = None
    wait_for_event: Optional[str] = None
    script: Optional[str] = None

_REDIS: redis.Redis | None = None
# REMOVED BY RORY - SCRAPER_SESSION_TTL not used in this repo
# _SESSION_TTL = int(os.getenv("SCRAPER_SESSION_TTL", "300"))
_SESSION_TTL = 300

async def _get_redis() -> redis.Redis:
    """Return a Redis client."""
    global _REDIS
    if _REDIS is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _REDIS = redis.from_url(url)
    return _REDIS

def _cookie_list(cookie_str: str, url: str) -> List[Dict[str, Any]]:
    """Convert ``"a=1; b=2"`` to Playwright cookie dicts."""
    cookies = []
    for part in cookie_str.split(";"):
        if "=" in part:
            name, value = part.strip().split("=", 1)
            cookies.append({"name": name, "value": value, "url": url})
    return cookies

async def _load_session(session_id: str) -> Dict[str, Any] | None:
    redis_cli = await _get_redis()
    data = await redis_cli.get(f"sj_session:{session_id}")
    return json.loads(data) if data else None

async def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    redis_cli = await _get_redis()
    await redis_cli.setex(f"sj_session:{session_id}", _SESSION_TTL, json.dumps(data))

class HeadlessScraper:
    """Simple Playwright-based scraper."""

    async def scrape(self, req: ScrapeRequest) -> Dict[str, Any]:
        """Return HTML and metadata from ``req.url``."""
        start = time.time()
        session_id = req.session_id or str(uuid.uuid4())
        session = await _load_session(session_id) or {}
        stored_cookies = session.get("cookies", [])

        timings: Dict[str, int] = {}
        if not req.render_js:
            headers = req.headers.copy()
            cookie_parts: List[str] = []
            if stored_cookies:
                cookie_parts.extend(f"{c['name']}={c['value']}" for c in stored_cookies)
            if req.cookies:
                cookie_parts.append(req.cookies)
            if cookie_parts:
                headers["Cookie"] = "; ".join(cookie_parts)

            nav_start = time.time()
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(req.url, headers=headers)
            timings["render_ms"] = int((time.time() - nav_start) * 1000)

            html = resp.text
            new_cookies = [
                {"name": k, "value": v, "url": req.url} for k, v in resp.cookies.items()
            ]
            script_result = None
        else:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                if req.headers:
                    await page.set_extra_http_headers(req.headers)

                # Merge cookies: stored first, then incoming
                cookies: List[Dict[str, Any]] = []
                if stored_cookies:
                    cookies.extend(stored_cookies)
                if req.cookies:
                    cookies.extend(_cookie_list(req.cookies, req.url))
                if cookies:
                    await context.add_cookies(cookies)

                try:
                    nav_start = time.time()
                    await page.goto(req.url)
                    timings["render_ms"] = int((time.time() - nav_start) * 1000)

                    if req.wait_for_selector:
                        await page.wait_for_selector(req.wait_for_selector)
                    if req.wait_for_event:
                        await page.wait_for_load_state(req.wait_for_event)
                    if req.wait_for_ms:
                        await page.wait_for_timeout(req.wait_for_ms)

                    script_result = None
                    if req.script:
                        script_result = await page.evaluate(req.script)

                    html = await page.content()
                    new_cookies = await context.cookies()
                except PlaywrightTimeoutError as exc:  # pragma: no cover - network
                    sh.log_open_item(f"scrape timeout: {exc}")
                    html = ""
                    new_cookies = []
                    script_result = None
                finally:
                    await browser.close()

        timings["total_ms"] = int((time.time() - start) * 1000)

        await _save_session(session_id, {"cookies": new_cookies})

        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in new_cookies)
        return {
            "html": html,
            "cookies": cookie_header,
            "script_result": script_result,
            "timings": timings,
            "session_id": session_id,
        }
