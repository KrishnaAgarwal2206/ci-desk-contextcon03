# Demo Readiness Report — 31 Oct 2026, ~14:45 IST

Status key: **LIVE** = succeeded against the real API today with parsed, persisted, downstream-used output · **TESTED** = covered by mocked pytest · **UNVERIFIED** = code exists but not exercised live.

## Crustdata (base `https://api.crustdata.com`, `x-api-version: 2025-11-01`)
| Endpoint | Purpose | Live | Parsed / persisted / used downstream | Errors & empty handled | Credits recorded |
|---|---|---|---|---|---|
| `GET /account/credits` | balance before/after run | **LIVE** | `account.credits` → `request.credits_before/after`, shown in UI | yes (non-fatal) | free |
| `GET /account/endpoints` | entitlement check | **LIVE** (200) | called and logged; **prices not parsed or used** | yes | free |
| `POST /company/identify` | canonical IDs | **LIVE** (5 runs) | matches → `entity` (ID, confidence, alternatives); ambiguity detection; TESTED | 4xx → unresolved; 402 terminal | 0.0 recorded |
| `POST /company/search` | market-only discovery | **LIVE** (direct call: 3 companies, 1.29 credits) | parsed to IDs/names; **pipeline branch (market-only brief) not run end-to-end** | yes | yes |
| `POST /company/enrich` | headcount, funding, news | **LIVE** | → evidence + headcount/funding/news events; TESTED | 403 → retry with fewer fields (untested) | ~2 / company |
| `POST /person/search` | founders/CXOs/VPs | **LIVE** | → evidence rows (leadership context); not converted into events | empty TESTED | ~0.33 / result |
| Person Enrich | — | not implemented | — | — | — |
| `POST /job/search` | hiring signals | **LIVE** | → senior/junior/GTM hiring events with job URLs | 429 retry TESTED | ~0.03 / result |
| `POST /web/search/live` | public news evidence | **LIVE** | → evidence + events; same-URL corroboration merge TESTED | malformed TESTED | 1 / query |
| Web Fetch | — | not implemented | — | — | — |
| `POST /watch/company` + `GET /watch/company/{id}` | shared entity watch | **LIVE** (watches 56239, 56240, + later runs) | definition + read-back stored and displayed | errors shown on card | baseline free |
| `GET /watch/company/{id}/runs` + `/runs/{run_id}/summary` | run-history reconciliation | **LIVE** (watch 56239: baseline run 488288, SUCCESS, 3 records, 0 credits) | baseline sample correctly stored as `baseline_sample`, **not** turned into events | yes | 0 |
| `POST /watch/company/{id}/test` | free test notification | **FAILS for pull-only watches**: API returns 400 "No delivery channel configured. Pass a 'notification_endpoint'". Button only shown for webhook watches. | — | error surfaced | free |
| `POST /webhooks/crustdata` (our receiver) | signed deliveries | **UNVERIFIED live** (no public HTTPS URL); signature/replay/duplicate/test/baseline logic TESTED | — | 401/400/413 | — |

Typical fresh run: ~15 credits (3 companies), all within the 150-credit run cap.

## Anthropic (`POST https://api.anthropic.com/v1/messages`, `x-api-key`, model `claude-sonnet-5-5`)
| Feature | Status |
|---|---|
| Auth + model config | **LIVE** (env-configured; key never logged) |
| Call 1 — research planner (JSON schema output) | **LIVE** (~$0.003/request) |
| Call 2 — brief synthesis (Strategy + VC only) | **LIVE** (~$0.013); first attempt hit `max_tokens` → automatic labelled fallback, fixed by smaller payload |
| Call 3 — feedback → typed PolicyProposal | **LIVE** (proposal parser `llm:claude-sonnet-5-5`) |
| Token + cost logging | **LIVE** (`llm_call` table, trace panel) and TESTED |
| $5 spend cap, 3 calls/request, 1,200 output tokens | TESTED (cap, no key, invalid output) |
| Timeout / 429 / refusal / max_tokens fallback | implemented; max_tokens fallback observed live; timeout/429 not live-triggered |
| **LLM-as-a-judge** | **NOT IMPLEMENTED** — do not claim |

## Features demonstrated end-to-end (live)
Final fresh run (request #4, 14:44): "Sierra, decagon.ai, intercom.com" → Decagon/Intercom resolved, Sierra ambiguous (12 candidates) → reviewer clicked "use this" (sierra.ai, 1128961) → evidence fetched, briefs rebuilt, watch 56276 created over all three. 21 events, 50+ evidence records, 15/15 API calls OK, 9.9 credits + reviewer step; LLM plan/synthesis/feedback all `ok` (~$0.02). Recruiting feedback → pending proposal #2 (suppress news_mention, leadership 0.8→1.0).

Fresh brief → LLM plan → Identify (canonical IDs; "Sierra"/"Intercom" names surfaced as ambiguous with candidates) → Enrich/Jobs/People/Web evidence with source + retrieval time → claims (fact vs inference) and deduplicated events → five stakeholder scores per shared event (matrix view) → per-persona briefs → NL feedback → validated pending proposal with diff + replay → reviewer approval → new persona policy version, other personas unchanged → shared Watcher create/read-back → run-history reconciliation → trace with credits and LLM cost.

## Incomplete / simulated / must not be claimed
- R&D, Sales/Marketing, Recruiting "why it matters" text is **template-based** (labelled); only Strategy and VC briefs are LLM-written.
- No Supply Chain persona; no alert delivery/routing (alerts = UI threshold flag only); no LLM judge; no auth/RBAC (reviewer is a typed name); replay covers stored events only (no historical backtest).
- No Watcher change event has been received; monitoring is **scheduled (weekly), 30-day SLA**, not real time.
- Company Search market-only path not run end-to-end; webhook receiver not exercised live.
- Nothing in the UI uses fixtures or mock data; mocks exist only in `tests/`.

## Tests
`pytest -q` → **19 passed** (identity ambiguity, provenance, dedupe, persona scoring, five-stakeholder scoring, isolation, invalid proposals, approval/versioning/rollback, custom persona validation, LLM fallback/cap/cost, Crustdata 402/403/429/malformed/empty/budget, webhook signature/stale/duplicate/test/baseline).

## Known failure modes
- Name-only inputs that collide (e.g. "Sierra") stay **ambiguous** until a reviewer clicks "use this" — by design. Use domains for a smooth demo.
- Enrich news can contain off-entity items; items with Crustdata match confidence < 0.93 are dropped and counted in Notes.
- A run takes ~45–60 s (Web Search ≈ 5 s per company). The page polls and refreshes automatically.
- Resolving an ambiguous entity after creation creates a **new** watch for the larger set (previous one, e.g. 56273, stays active — no PATCH yet).
- Each new set of companies creates a new watch (5 credits per changed company per weekly run) — cancel demo watches after the event.

## Restart and demo
```bash
# stop any running server (Ctrl+C), then from the repo root:
uvicorn app.main:app --reload        # http://127.0.0.1:8000
pytest -q
```
Optional clean slate: stop the server, delete `contextcon03.db`, restart (persona policies re-seed at v1).

Demo flow (2 min): submit a brief with domains → KPI strip + canonical companies → **Stakeholder matrix** (same event, different priorities) → Brief tab switch (score breakdown, cited facts, inference labels) → Governance: submit feedback → diff + replay → Approve (enter reviewer name) → version history; other personas unchanged → Monitoring card (watch ID, weekly, 30-day SLA, baseline) → Trace (credits, LLM cost).
