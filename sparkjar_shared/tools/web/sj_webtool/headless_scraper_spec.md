# Headless Browser–Based Web Scraping Platform  
*Product Requirement Specification*

---

## 1  Vision and Scope  
Deliver an internal-use scraping service that behaves like a real user’s browser, survives modern anti‑bot defenses, and exposes a clean HTTP‑level API that downstream micro‑services (or client applications) can call synchronously. The platform must remain entirely self‑contained—no external search, proxy, or scraping APIs may be invoked.

---

## 2  Functional Capability Stack  

| Capability | “Shall” Statement (Dev‑Facing) | Key Acceptance Tests |
|------------|--------------------------------|----------------------|
| **1. Full‑Fidelity Headless Browsing** | The engine **shall** spin up real Chromium‑class headless browser instances, one per request (or per session, see §2.3). Browsers **shall** load HTML, CSS, JS, fonts, images, and execute all onboard scripts exactly as a human‑operated browser would. | • Verify `navigator.userAgent` inside the page matches a realistic string.<br>• Fetch a site that uses a dynamic JS menu; confirm the rendered DOM equals a manual browser capture. |
| **2. Parallel Instance Orchestration** | The service **shall** manage “thousands” (target: ≥5 000 concurrent) browser containers in a resource‑elastic pool. Instances must auto‑upgrade to the latest stable browser build within 24 h of upstream release. | • Run a soak test firing 10 000 overlapping requests; 99th‑percentile queue latency ≤1 s.<br>• After a headless browser release, pool version check shows new build within 24 h. |
| **3. Anti‑Bot/“Human Footprint” Simulation** | For each request the orchestrator **shall** randomize think‑time, navigation timing, and optional DOM interactions (mouse‑move, scroll, click) based on a tunable policy file. | • Hit a fingerprinting test page; confirm entropy metrics stay within typical human ranges. |
| **4. Header Injection & Rotation** | The REST endpoint **shall** accept an arbitrary map of HTTP headers. If `User‑Agent` is omitted, the engine inserts a rotating real‑world UA string drawn from a maintained list of desktop / mobile browsers. | • Integration test posts `{ "headers": { "X‑Debug": "on" } }`; response includes that header. |
| **5. Cookie Pass‑Through** | Client‑supplied cookie strings **shall** be injected unchanged. Set‑Cookie headers received during render **shall** be persisted in session storage (see §2.3) and surfaced in the response payload. | • Log‑in flow: step 1 posts credentials, receives `Set‑Cookie`; step 2 reuses session and reaches an account‑only page. |
| **6. Sticky Sessions** | The API **shall** expose `session_id`. All calls bearing the same ID within a TTL window (config default 5 min) **shall** reuse: (a) identical outbound proxy/IP, (b) the same browser container with preserved cookies, localStorage, and in‑memory DOM state. | • Repeated calls to `https://httpbin.org/ip` in one session return the same origin IP. |
| **7. JavaScript Rendering Toggle** | Query param `render_js=true | false` **shall** control whether a full browser is used. When `false`, the service may fall back to a lightweight raw‑HTML fetcher. Default `true`. | • For a Vue SPA: with JS off, `<div id="app"></div>` empty; with JS on, DOM populated. |
| **8. Wait‑Until Controls** | Optional fields:<br>• `wait_for_selector` (CSS)<br>• `wait_for_ms` (int)<br>• `wait_for_event` (network‑idle, domcontentloaded, etc.).<br>The browser **shall** block response until condition satisfied or a global timeout elapses. | • Provide `wait_for_selector=".price"` on an infinite‑scroll site; verify final HTML contains the selector’s node. |
| **9. Page‑Context Script Execution** | Field `script` (string) **shall** accept arbitrary JS; engine injects and executes it in the page context after load and before capture. Return value (JSON‑serializable) **shall** be surfaced in `script_result`. | • Supply `return [...document.querySelectorAll("h2")].map(e=>e.textContent)`; expect an array of headings in response. |

---

## 3  API Contract (v1 Draft)

```http
POST /scrape
{
  "url": "https://example.com",
  "render_js": true,
  "headers": { "Accept-Language": "en-US,en;q=0.9" },
  "cookies": "session=abc123; theme=dark",
  "session_id": "optional-uuid",
  "wait_for_selector": "#main",
  "script": "/* optional JS */"
}
→
{
  "status": 200,
  "html": "<!doctype html>…",
  "cookies": "Set-Cookie header string(s)",
  "script_result": { /* if provided */ },
  "timings": { "total_ms": 1843, "render_ms": 712 },
  "session_id": "echo or newly issued"
}
```

**Error handling**: JSON body includes `error_code`, `message`, and, in debug mode, a truncated stack trace.

---

## 4  System Design Notes  

1. **Browser Pool Layer**  
   *Implement via Kubernetes + PodAutoscaler.* Each headless browser runs in a slim Alpine‑based container with Chrome, XVFB disabled, and remote‑debugging port exposed. The pool manager allocates containers round‑robin, tracks health, and reaps those exceeding max‑lifetime (e.g., 10 minutes idle).

2. **Proxy & IP Rotation**  
   *Separate micro‑service.* Maintains a fleet of residential / datacenter proxies (BYO or rented). Session stickiness maps `session_id` → proxy endpoint; LRU cache evicts after TTL.

3. **Session Store**  
   Redis cluster keyed on `session_id` storing: proxy endpoint, browser pod UID, cookies, localStorage snapshot. Expiry sliding window resets on each hit.

4. **Anti‑Bot Policy File**  
   YAML defining min/max delay, scroll patterns, click targets probability. Hot‑reload via ConfigMap.

5. **Observability**  
   OpenTelemetry exporter: span per scrape, attributes include `url_host`, `render_js`, `proxy_ip`, `total_ms`, `blocked_reason` (if any). Metrics feed into Grafana dashboards; alerts fire on p95 latency or block‑rate anomalies.

---

## 5  Non‑Functional Requirements  

* **Throughput**: sustain 100 req/s with JS render, 500 req/s raw HTML, under 4× browser CPU oversubscription.  
* **Latency SLO**: p90 ≤ 3 s JS render; p90 ≤ 800 ms raw.  
* **Security**: browsers run inside gVisor sandbox; no host network access; `CAP_SYS_ADMIN` dropped.  
* **Upgradability**: blue‑green rollout pipeline auto‑tests new Chrome major versions against 50 synthetic target sites.  
* **Compliance**: no third‑party API calls; outbound traffic restricted to target URLs and proxy network.  

---

## 6  Open Items / Next Steps  

1. Proxy procurement plan: decide between self‑hosted residential nodes vs. reputable proxy vendor.  
2. Quota & billing hooks: integrate with internal API‑gateway for rate‑limiting and usage metering.  
3. Script execution sandboxing: evaluate per‑tenant time and memory limits to prevent abuse.  
4. Future roadmap: screenshot capture, PDF rendering, and HAR file export.  

---

## 7  Definition of “Done”  

*All acceptance tests green in CI.*  
Load test meets throughput and latency SLOs for one hour.  
Upgrade pipeline successfully patches Chromium within 24 h twice.  
Observability dashboards live with no broken panels.  
