# FINAL PRODUCT PLAN — Persona-aware Competitive Intelligence Desk

Status: **authoritative** for the ContextCon 03 build. Decision source: `PM_Verdict_ContextCon03_v2.docx`. Written 31 Oct 2026, 13:41 IST.
Labels used: **[FACT-COMP]** competition material · **[FACT-API]** Crustdata docs read 31 Oct 2026 · **[LEGACY]** old CI docs · **[PM]** PM decision.

## 1. Product definition
A continuous competitive-intelligence service that turns a plain-English market/competitor brief into a verified, Crustdata-grounded intelligence brief and a Watcher-monitored landscape, interpreted separately for each decision-maker persona, with persona policies tuned by natural-language feedback through governed, testable, reversible proposals.

> Watcher tells us what changed. Our intelligence engine connects the evidence and explains what it means. Persona policies determine why it matters to each decision-maker. Natural-language feedback teaches the system what that stakeholder values through a governed, testable and reversible policy change.

## 2. Customer and buyer
- **Enterprise:** buyer = Head of Competitive Intelligence / Corporate Strategy (budget today: CI analysts, research firms, consultants). Demo persona: *Corporate Strategy / CI Lead*.
- **VC firm:** buyer = Investment Partner / Head of Platform (budget today: associates, market-map research, data subscriptions). Demo persona: *VC Investment Partner*.

## 3. Theme
Primary: **Research and Markets**. Adjacent customer segment: **Investing**. Not pitched as "Infrastructure for Agents". Governance is a core differentiator of the paid service; observability is supporting infrastructure, built last.

## 4. Service replaced
The recurring analyst job of: resolving who the competitors are, gathering current evidence, monitoring for changes, connecting related signals, writing "what changed / why it matters" briefs, and re-tailoring them per stakeholder. Humans keep final strategy and investment decisions; the service automates research, monitoring, synthesis, prioritization and briefing.

## 5. Inputs → outputs
**Input:** free-text brief (market, companies/domains, optional people, signal interests, time window, persona(s)); optional NL feedback later.
**Outputs:** (a) resolved entity list with Crustdata IDs + confidence + ambiguous/unresolved states; (b) intelligence brief with atomic, cited claims, fact/inference labels, confidence and unknowns; (c) Watcher subscription(s) with ID, track, schedule, SLA, cost estimate; (d) deduplicated event list; (e) two persona-ranked views with score breakdown; (f) policy proposal → diff → replay → approval → version; (g) compact run trace incl. actual credits.

## 6. End-to-end workflow (single in-process path)
1. **Intake** → request record; planner extracts structured plan (LLM if key supplied; else deterministic parser, labelled).
2. **Preflight** → `GET /account/credits`, `GET /account/endpoints` (free); budget cap set for the run.
3. **Resolve** → Company Identify per name/domain; keep top match + alternatives; low confidence/multi-match → `ambiguous` (shown, not guessed).
4. **Evidence** → Company Enrich (selected field groups) for resolved IDs; Job Search (capped) per company; Person Search for leadership (capped); Web Search (1–2 queries/company, capped) + optional Web Fetch of top URLs.
5. **Normalize** → each record/result → evidence row (source type, URL/record ref, retrieved_at, excerpt/field path) → atomic claims → events (fingerprint, dedupe, cluster).
6. **Score** → deterministic base significance + persona policy weights → per-persona assessment rows (policy_version recorded).
7. **Brief** → per persona: ranked findings, "why it matters" (inference labelled), sources, confidence, unknowns, next steps.
8. **Watch** → create bounded Company Entity Watch over resolved IDs (30-day SLA, `every_hours` ≥ 24, `max_results_per_run` ≤ 25); read back; `POST /watch/company/{id}/test`; reconcile `GET /watch/company/{id}/runs`.
9. **Ingest** → webhook (HMAC verified, idempotent) or run-history pull → raw envelope → same normalize/score path. Test payloads isolated.
10. **Feedback** → NL → typed proposal (`pending_review`) → validate → diff + replay → approve → new immutable persona policy version → re-score.

## 7. Crustdata mapping per stage [FACT-API]
Base `https://api.crustdata.com`, headers `Authorization: Bearer <key>`, `x-api-version: 2025-11-01`.
| Stage | Endpoint | Notes |
|---|---|---|
| Preflight | `GET /account/credits`, `GET /account/endpoints` | Free. `/account/endpoints` does **not** carry watch prices. |
| Resolve company | Company Identify | Free per public pricing; ranked by confidence. |
| Company context | Company Enrich | Select field groups only (basic_info, headcount, funding, news, people). |
| People | Person Search (+ Person Enrich only for ≤3 selected) | Search first. |
| Hiring | Job Search | Cap results; aggregate by category/seniority. |
| Public evidence | Web Search, Web Fetch | Cited URLs + excerpts. |
| Ongoing (known set) | `POST /watch/company` (entity) | MVP watcher. Optional 2nd: `POST /watch/job/search` narrow discovery. |
| Recovery | `GET /watch/company/{id}`, `/runs`, `/runs/{run_id}/summary` | Reconcile missed webhooks. |
| Plumbing test | `POST /watch/company/{id}/test` | Free, `metadata.test=true`. Never a business event. |

## 8. Persona model & hierarchy
Global integrity rules (immutable) → Workspace policy (scope, budget, exclusions) → Persona policy (weights, thresholds, lens) → Individual presentation prefs. Details: `PERSONA_POLICY_MODEL.md`. Two presets shipped; schema supports custom personas.

## 9. Feedback governance lifecycle
capture → parse to typed proposal (`pending_review`) → deterministic validation (fields, operators, bounds, guardrails, scope, authority) → diff + affected events → replay on stored events → reviewer approval (risk-gated) → immutable new version + audit → apply only to that persona → rollback available. Watcher-changing proposals need a separate credit approval. Details: `FEEDBACK_GOVERNANCE.md`.

## 10. Evidence & identity requirements
Every company/person carries `crustdata_company_id`/`crustdata_person_id` or explicit `unresolved`/`ambiguous`. Every factual claim → ≥1 evidence row with source URL or Crustdata record ref + field path, `retrieved_at`, excerpt/value. Claims typed `fact | inference | hypothesis`. No evidence → abstain ("not found in retrieved sources").

## 11. Minimal observability
Passive `run_step` + `api_call` rows: request_id, stage, endpoint, HTTP status, duration_ms, record count, `X-Credits-Used`, watch_id/run_id, policy_version, error. One compact trace panel. Nothing more until P0 done. See `OBSERVABILITY.md`.

## 12. Credit rules
Read balance + entitlements first; per-run cap; search-first, enrich-selectively; log actual `X-Credits-Used`; 30-day SLA watches only by default; no `is_realtime` / 1-day watches without explicit approval; stop on 402/403. See `CREDIT_BUDGET.md`.

## 13. Scope
**MVP (P0):** intake, preflight, resolve, evidence, normalize/dedupe, deterministic scoring, two persona views, brief, one company entity watch + test + run reconciliation + webhook receiver, NL feedback governance loop, essential edge cases, run trace fields, single-command local run, README + demo.
**Deferred:** auth/RBAC beyond a reviewer flag, more personas, social-post/person watchers, cross-dataset watches (unless proven in 5 min), email/Teams delivery, schedulers, 32-screen admin, ops copilot, dashboards, Azure, legacy adapters.

## 14. Acceptance criteria × judging rubric
| Criterion (pts) | Must demonstrate |
|---|---|
| End-to-end (25) | Unseen brief → resolved entities → live Crustdata evidence → watch created/read back → finished two-persona brief, one command, no manual steps. |
| Facts & verification (20) | Every finding links to URL/record + timestamp + excerpt; fact/inference labels; ambiguous entities surfaced; abstention on gaps. |
| Robustness (20) | Ambiguous name, empty search, 429 retry w/ backoff, 402/403 stop, timeout → partial result, duplicate webhook ignored, bad signature rejected, test payload isolated. Pytest covers these. |
| Customer value (20) | Same event ranked differently for CI Lead vs VC Partner with score breakdown; NL feedback → governed, persona-scoped, reversible change. |
| Demo (15) | Two-minute Loom per `DEMO_SCRIPT.md`; README answers the event's README questions. |

## 15. Two-minute demo
See `DEMO_SCRIPT.md`.

## 16. Risks & assumptions
| Risk | Mitigation |
|---|---|
| No public HTTPS for webhooks | Use run-history pull (documented); webhook endpoint still built + tested locally with signed test payloads. |
| Watcher baseline/run takes hours; no real change during demo | Show watch create/read-back/test + run list honestly; brief comes from Search/Enrich/Web. Never fake events. |
| No runtime LLM key | Deterministic planner + feedback parser, labelled "deterministic parser"; briefs built from templates over evidence. |
| Credit figure mismatch ($4,500 user-reported vs 15,000 credits/builder in deck) | `/account/credits` is the only truth; never convert. |
| Exact request/response field names differ from assumptions | Verify against live responses during 13:45 preflight; adapt parsers. |
| Time | Feature freeze 15:00; cut order in `BUILD_BACKLOG.md`. |

Assumptions: Python 3.12.4 available (verified); no Crustdata API key or LLM key is present in the environment (verified: no env vars) — **user must supply `CRUSTDATA_API_KEY` in `.env`**.
