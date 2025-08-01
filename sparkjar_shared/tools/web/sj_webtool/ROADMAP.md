# SJ Webtool Roadmap

This roadmap tracks the headless scraping service described in `headless_scraper_spec.md`.

Core capabilities include full-fidelity browsing, parallel orchestration, anti-bot simulation, header and cookie injection, sticky sessions, script execution, and wait controls.

## Phase 1: Playwright Prototype
- Build a small script using Playwright.
- Prove full-fidelity headless browsing per the spec.

## Phase 2: Session Management
- Store session data in Redis.
- Persist cookies and browser state across requests.
- Follow the Sticky Sessions capability.

## Phase 3: Proxy Rotation
- Add a proxy micro-service.
- Map each session to one proxy endpoint.
- Implements the Proxy & IP Rotation feature.

## Phase 4: API Endpoints
- Expose `/scrape` and related endpoints.
- Accept headers, cookies, and optional scripts.
- Respect the API Contract from the spec.

## Phase 5: Observability
- Emit OpenTelemetry spans for every scrape.
- Track timing, proxy IP, and blocked reasons.
- Surface metrics in dashboards.

