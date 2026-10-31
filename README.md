# Persona-aware Competitive Intelligence Desk

**ContextCon 03 · Theme: Research and Markets (second segment: Investing)**

> Watcher tells us what changed. Our intelligence engine connects the evidence and explains what it means. Persona policies determine why it matters to each decision-maker. Natural-language feedback teaches the system what that stakeholder values — through a governed, testable, reversible policy change.

## The service
**Job replaced:** the recurring competitive-intelligence analyst job — figure out who the competitors are, gather current evidence, keep watching for changes, connect related signals and write a different "what changed / why it matters" brief for each stakeholder.

**Who does it today and who pays:** enterprises pay in-house CI/strategy analysts, research firms and consultants; VC funds pay associates and data subscriptions for market maps, competitor and portfolio tracking.

## What it does now (end to end)
Paste a plain-English brief (market and/or competitor names or domains). With no further input the desk:

1. **Plans** the research (Anthropic `claude-sonnet-5-5` structured output, or a labelled deterministic parser).
2. **Checks the account** — `GET /account/credits`, `GET /account/endpoints` (free); per-run cap of 150 credits.
3. **Resolves canonical identities** with Crustdata **Company Identify** (or **Company Search** for market-only briefs). Ambiguous names are **not guessed**: candidates are shown with Crustdata IDs, size and domain.
4. **Gathers evidence** — **Company Enrich** (basic_info, headcount, funding, news), **Job Search**, **Person Search** (founders/CXOs/VPs), **Web Search** (news). Every record is stored with source URL or Crustdata record reference + field path, source date and retrieval time.
5. **Builds events** — deterministic fingerprints; the same development seen twice (e.g. an article in Enrich news *and* Web Search) becomes one event with corroborating evidence. Facts and inferences are labelled separately.
6. **Scores each event once per stakeholder persona** — `base_significance × category_weight × evidence_factor` with the full breakdown visible. Five presets ship: Corporate Strategy / CI Lead, VC Investment Partner, R&D / Technology Lead, Sales / Marketing Lead, Talent / Recruiting Lead. In a live run, one shared event ("Cursor: 5 recent senior roles posted") scored 0.65 for R&D and Recruiting, 0.52 for Strategy and VC, and 0.26 (below alert threshold) for Sales. More personas can be added in `config/personas.json` (same shape as `PERSONAS` in `app/policy.py`; validated against the same bounds; invalid entries are skipped).
7. **Writes a rich brief per stakeholder** — one grounded LLM call (all five stakeholders, ~$0.04) returns an executive summary, 3–4 insight cards (headline, analysis with numbers from the facts, implication, concrete recommended action, confidence) and what to watch next. Every insight's event and evidence IDs are validated against stored records; uncited insights are dropped. Without the LLM, labelled template insights and recommended actions are used. LLM synthesis may only phrase "why it matters" for events it is given and may only cite those events' evidence IDs (validated); ranking stays deterministic. Template fallback is labelled.
8. **Sets up monitoring** — one shared Crustdata **Company Entity Watch** (`POST /watch/company`) over the resolved companies, read back with `GET /watch/company/{id}`. Weekly schedule, 30-day freshness SLA (the only SLA for this watch type), ≤25 results/run. **Scheduled monitoring, not real time.** Run history is reconciled with `GET /watch/company/{id}/runs` (+ `/runs/{run_id}/summary`); a webhook receiver with HMAC verification is ready when a public HTTPS URL is configured.
9. **Learns from feedback, under governance** — e.g. *"For the VC Partner persona, suppress routine junior hiring alerts. Prioritize senior leadership changes, funding, founder moves and GTM expansion. Do not lower the evidence threshold."* becomes a typed **pending** proposal → deterministic validation → before/after diff → replay on stored events → named reviewer approval → new immutable persona policy version → re-score of **that persona only**. Rollback creates another version.
10. **Shows a compact execution trace** — every Crustdata call (status, duration, result count, actual `X-Credits-Used`), Anthropic tokens and estimated USD, stage timings and failures.

**Where a person still steps in (the exceptions):** choosing between equally-ranked identity candidates ("use this" button), approving or rejecting policy proposals, approving any Watcher/spend change, and making the actual strategy or investment decision.

## How to run
```bash
pip install -r requirements.txt
cp .env.example .env        # add CRUSTDATA_API_KEY (required for live data); ANTHROPIC_API_KEY optional
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
pytest -q                   # 16 tests, all external APIs mocked
```
Without `CRUSTDATA_API_KEY` the UI says **Crustdata: NOT CONFIGURED** and returns no data (nothing is fabricated). Without `ANTHROPIC_API_KEY` every LLM step falls back to deterministic logic and is labelled.

## How it is built
Python · FastAPI · Pydantic v2 · HTTPX · SQLAlchemy 2 + SQLite · Jinja2 + vanilla JS · pytest. One process, no queue/worker.

| Module | Role |
|---|---|
| `app/crustdata.py` | Crustdata REST client: auth headers, budget guard, retries (429/5xx/timeout), terminal 402/403, malformed/empty handling, `api_call` ledger with `X-Credits-Used` |
| `app/pipeline.py` | plan → resolve → evidence → events → briefs → watch; reconciliation; reviewer candidate selection |
| `app/policy.py` | persona presets, scoring, proposal parser/validator/diff/replay, approve/reject/rollback |
| `app/llm.py` | bounded Anthropic Messages API (HTTPX, `output_config.format` JSON schema); $5 app cap, 3 calls/request, 1,200 output tokens; fallback on any failure |
| `app/webhook.py` | `x-crustdata-signature` HMAC-SHA256 over `t.raw_body`, ±300 s replay window, idempotency on notification ID, test/baseline isolation |
| `docs/product-v2/` | product plan, Crustdata/Watcher notes, policy model, governance, data model, demo script |

**LLM boundaries:** the LLM never resolves identities, calls APIs, scores events, validates or activates policy. It plans, phrases, and proposes.

## Demo flow
1. `uvicorn app.main:app --reload`, open http://127.0.0.1:8000, submit a brief (domains resolve most precisely).
2. Request page: KPI strip → **Canonical companies** (IDs, confidence, ambiguous candidates with "use this") → **Stakeholder matrix** (the same stored event scored for five stakeholders).
3. **Briefs**: switch stakeholder tabs; open "score breakdown"; facts vs inference are labelled; click `E#` to jump to evidence.
4. **Governance**: submit feedback → pending proposal with diff + replay → enter reviewer name → Approve → new version for that persona only (others unchanged) → optional rollback.
5. **Monitoring**: real watch ID, weekly schedule, 30-day SLA, baseline status; "Reconcile run history" pulls `GET /watch/company/{id}/runs`.
6. **Trace**: every Crustdata call with `X-Credits-Used`, LLM tokens and estimated cost, stage timings, errors.

## Limitations (do not claim)
No LLM-as-a-judge stage; no alert delivery/routing (alerts are an in-app threshold flag); no Supply Chain persona; no auth/RBAC; replay covers stored events only; no Watcher change event received yet; webhook receiver not exercised live; Person Enrich and Web Fetch not implemented. Full API-by-API status: [`DEMO_READINESS_REPORT.md`](DEMO_READINESS_REPORT.md).

## Approaches tried — what worked, what didn't
- **Enrich `people` field group:** returned ~6.8 MB for one company and stalled the run. Dropped; **Person Search** with title filters gives leadership with far less payload.
- **Name-only identity:** "Intercom" returned 7 and "Sierra" 12 matches all at confidence 1.0 (including Sierra the truck and Sierra Textiles). We never guess: a tie is broken only by a unique exact domain-name match, otherwise it is shown as *ambiguous* and the reviewer picks. Domains in the brief resolve exactly.
- **Off-entity news:** Enrich news for Sierra AI included GMC Sierra truck stories. Crustdata's per-article entity-match confidence separated them (0.85–0.90 off-entity vs 0.95 on-entity) — we keep ≥ 0.93 and log how many were dropped.
- **LLM synthesis over the 1,200-token cap:** the first version hit `max_tokens`; the app fell back to template text automatically. Sending only the top 5 events per persona with 2 facts each fixed it (~$0.014 per brief).
- **Webhooks vs pull:** no public HTTPS endpoint at the venue, so the watch is pull-only (`notifications: []`) with run-history reconciliation; the signed webhook path is implemented and tested.

## Hardest case
A brief naming companies whose names collide with unrelated businesses. The desk surfaces all candidates with canonical IDs instead of silently picking one, filters off-entity news by Crustdata's match confidence, and keeps every remaining claim tied to a record you can click.

## Testing
`pytest -q` covers: identity ambiguity, provenance on every event, deduplication/corroboration, different persona scores, persona isolation after approval, invalid/out-of-bounds/integrity-weakening proposals, approval + versioning + rollback, LLM fallback (no key, spend cap, invalid output) and token/cost accounting, Crustdata 402/403/429/malformed/empty/budget, webhook signature tamper/stale/missing, duplicate notifications, and test/baseline isolation. Plus live smoke runs against Crustdata and Anthropic (two fresh briefs; ~15 credits and ~$0.02 LLM each).

## What it could do next (and why not today)
Person entity watches on key executives and a narrow job discovery watch (needs per-watch credit approval UI); cross-dataset discovery watches; more persona presets and workspace RBAC; scheduled digests. Not today: each adds spend or surface area before the core loop has real users.

## Deviations from the plan docs
- Anthropic auth uses the documented `x-api-key` header; `ANTHROPIC_API_VERSION` defaults to the documented `2023-06-01` (configurable).
- Company Enrich omits the `people` group (payload size, above).

## Demo integrity
No fabricated Crustdata calls, events or Watcher deliveries. Test notifications (`metadata.test=true`) and baseline samples are stored but never shown as intelligence. Secrets live only in `.env` (git-ignored) and are never logged or sent to the browser.
