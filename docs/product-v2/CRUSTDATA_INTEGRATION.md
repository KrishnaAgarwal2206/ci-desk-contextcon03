# CRUSTDATA INTEGRATION

Source: `https://docs.crustdata.com/llms.txt` and linked pages, read 31 Oct 2026. Account-specific responses always override anything here.

## Connection
- Base URL `https://api.crustdata.com`; headers `Authorization: Bearer ${CRUSTDATA_API_KEY}`, `x-api-version: 2025-11-01`.
- Backend-only `httpx` client (`app/crustdata/client.py`). Key read from `.env`; never logged, never sent to the browser. `.env.example` committed, `.env` gitignored.
- Runtime uses REST, not MCP. MCP (`claude mcp add --transport http crustdata https://install.crustdata.com/mcp`) is **not configured** in this environment (checked `claude mcp list`); optional for dev exploration only.

## Endpoints used (MVP)
| Purpose | Endpoint | Public list price (not account price) |
|---|---|---|
| Balance | `GET /account/credits` → `account.credits`, `recurring_credits`, wallets | Free |
| Entitlements & prices | `GET /account/endpoints` | Free. No watch prices here. |
| Company identify | Company Identify (name/domain/profile URL/ID → ranked matches) | Free |
| Company enrich | Company Enrich (`fields` groups) | ~2–4 / profile |
| Company search | Company Search (filters / NL ranked; ≤100/page) | from 0.03 / result |
| Person search | Person Search | from 0.03 / result |
| Person enrich | Person Enrich (≤25 profile URLs) | 1–9 / profile |
| Jobs | Job Search (indexed) | per result **[VERIFY-LIVE]** |
| Web | Web Search; Web Fetch (≤10 URLs) | 1 / query; 1 / page |
| Watch | see `WATCHER_INGESTION.md` | per delivered record |

Exact request paths/bodies for search/identify/enrich are taken from the API reference pages at build time **[VERIFY-LIVE]**; do not hardcode guessed field names without checking one real response.

## Client behaviour
- Record per call: endpoint, status, duration, result count, `X-Credits-Used` header → `api_call` table.
- **429:** honour `X-RateLimit-Reset`/backoff with jitter, max 3 retries. Watch-management endpoints: 10 req/min per path.
- **402** (insufficient credits): terminal — stop the run, surface to user, no retry.
- **403** (endpoint denied) or denied fields: terminal for that call; drop field group if field-level; continue with partial result.
- Timeout (default 20 s): one retry, then mark stage `partial`.
- Empty result: recorded as `empty`, brief shows "no evidence found" — never substituted.
- Budget guard before every paid call: `estimated_cost + spent ≤ run_cap`, else skip and log `skipped_budget`.

## Feature decisions
| Feature | Decision |
|---|---|
| Company Identify/Enrich, Person Search, Job Search, Web Search/Fetch | RETAIN-NEW (P0) |
| Person Enrich | P0 but ≤3 people per run |
| Social Post Search / Watcher | DEFER (account-dependent) |
| Batch APIs, Contact Enrich | REMOVE for MVP (contact data not needed; no outreach) |
| Cross-dataset discovery watch | DEFER; try only if P0 finishes early |
