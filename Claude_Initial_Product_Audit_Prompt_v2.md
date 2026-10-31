# CLAUDE CODE — INITIAL PRODUCT AUDIT, FINAL PLAN & DOCUMENTATION REVAMP

## Your role
You are the implementation engineer working under a decisive Head Product Manager. You are using Claude Sonnet, so follow this specification literally. Do not invent product decisions, expand scope, or spend time debating alternatives. The attached PM Verdict is the product decision. Your job in this first pass is to inspect all source material, resolve the implementation plan, and create a clean revised copy of the product documentation. Do not start application coding in this first pass.

## Objective
Prepare the project for a focused ContextCon 03 submission by transforming the existing FMCG/Godrej-specific Competitive Intelligence Aggregator design into a **Persona-aware Competitive Intelligence Desk** for enterprise teams and venture capital firms.

The new product thesis is:

> **Watcher tells us what changed. Our intelligence engine connects the evidence and explains what it means. Persona policies determine why it matters to each decision-maker. Natural-language feedback teaches the system what that stakeholder values through a governed, testable and reversible policy change.**

Read `PM_Verdict_ContextCon03.docx` first. It is authoritative for product scope and PM decisions. If the file is named differently, find the document with “PM Verdict” in its filename.

## Source material to inspect
Find and inspect all available files under the project directory. Expected source material may be located under `docs/`, `inputs/` or similar folders:

1. Original hackathon problem statement PDF (`ContextCon PS - CrustData.pdf`).
2. Official ContextCon 03 event deck PDF (`ContextCon 03 ... Event Deck ...pdf`).
3. Full themes slide deck (`ContextCon 03 - IIT Bombay - The Themes.pptx`).
4. Original Competitive Intelligence documentation archive, extracted from `Competitive-Intelligence-Docs.zip`.
5. The PM Verdict DOCX supplied with this prompt.
6. Official Crustdata documentation, using `https://docs.crustdata.com/llms.txt` as the machine-readable index and the relevant linked pages.
7. Official event page: https://events.ycombinator.com/lczadh0gm

If the ZIP is not extracted, extract it into a temporary inspection directory. Do not edit or overwrite original source files. There is no application source-code repository in the documentation ZIP; the supplied archive is product documentation, not executable application code. Do not pretend otherwise.

## Resolve the competition requirements carefully
The older five-page problem statement says Crustdata use is mandatory. The later official event deck, slide 33, says Crustdata use is optional and all projects are judged on the same five criteria. Do not silently ignore this discrepancy. Record it in `docs/product-v2/SOURCE_DECISIONS.md`. Our product will use Crustdata deeply because it is the strongest data substrate and the founders specifically recommended Watcher for ingestion; this is a product strategy choice even if the event deck makes API use optional.

The judging rubric from the event deck is definitive for prioritization:
- End-to-end execution: 25 points.
- Facts and verification: 20 points.
- Robustness and edge cases: 20 points.
- Customer value and idea: 20 points.
- Demo and understanding: 15 points.

The event deck frames the hackathon as “Services, Replaced”, says judges assess the product as its paying customer, and contrasts a service outcome with a one-step tool. The primary theme is **Research and Markets**. **Investing** is the second customer segment/persona. Do not pitch this as merely “Infrastructure for Agents”. Governance is a core differentiator of the paid intelligence service. Observability is supporting infrastructure and the **last full product layer to build**. Capture only the minimum execution metadata needed for evidence, debugging and judging during the core build; defer dashboards, incident workflows and operations copilots until all higher-priority requirements work.

## Final product decision — do not reopen this
Build a **Persona-aware Competitive Intelligence Desk**.

It provides a continuous competitive-intelligence service for:
1. Enterprise teams (initial demo persona: Corporate Strategy / Competitive Intelligence Lead).
2. VC firms (initial demo persona: Investment Partner).

The product must be industry-agnostic/configurable. Remove FMCG, Godrej Consumer Products, HUL/P&G/ITC and India-specific assumptions from core prompts, models, scoring and seed data. Keep the old FMCG configuration only as a clearly labelled example if useful.

The experience should let a user submit a natural-language market/competitor brief and receive:
- Canonically resolved companies and relevant people.
- An initial intelligence brief grounded in actual Crustdata and public-web evidence.
- A Watcher-backed monitored landscape for future company/person/job changes.
- Deduplicated, connected events with atomic claims and provenance.
- Separate persona-specific prioritization, implications and recommendations over the same evidence base.
- A natural-language feedback workflow that proposes a persona-scoped policy change, simulates it, requires approval, versions it and can be rolled back.
- A compact execution trace showing Crustdata calls, Watcher state, failures and actual credit usage.

Do not claim to automate final strategy or investment decisions. The service automates research, monitoring, synthesis, prioritization and briefing.

## Crustdata integration — read the real docs before implementation planning
Use the official docs index: https://docs.crustdata.com/llms.txt
Core auth/version:
- Base URL: `https://api.crustdata.com`
- `Authorization: Bearer <CRUSTDATA_API_KEY>`
- `x-api-version: 2025-11-01`

Relevant APIs include Company Search/Identify/Enrich, Person Search/Identify/Enrich, Job Search, Web Search/Fetch, Social Post Search if enabled, and Watcher.

### Watcher is the primary ongoing ingestion layer
Distinguish these documented watcher families:
- Known companies: `POST /watch/company`.
- Known people: `POST /watch/person`.
- New company matches: `POST /watch/company/search`.
- New person matches: `POST /watch/person/search`.
- New job matches: `POST /watch/job/search`.
- New social-post matches: `POST /watch/social_post/search` if account-enabled.

Use entity watchers for a known list and discovery watchers for saved search filters that should keep finding new matching entities. Where useful, investigate the documented cross-dataset filters that combine company, person and job fields in a discovery watch. Read exact constraints: do not assume arbitrary joins, count conditions or unsupported combinations.

Watcher design rules:
- A Watcher baseline is a before-snapshot and may send a free sample of up to five records; it is not a historical change feed. The initial intelligence brief must separately use Search/Identify/Enrich/Web APIs.
- Watcher test notifications are free and use `metadata.test=true`. They verify webhook plumbing only. Never present them as real business events.
- Verify webhook signatures exactly as documented (HMAC-SHA256 over timestamp plus raw request body using the API key); implement replay protection and idempotency using documented IDs.
- Store `watch_id`, `run_id`, event/notification ID, canonical entity IDs, raw payload, received time and processing state.
- Read Watcher run history/run summaries so missed webhook notifications can be reconciled. A documented pull-only watch with `notifications: []` is a fallback if a public webhook tunnel is not available.
- Distinguish `config.trigger.every_hours` (schedule) from `config.refresh_frequency_days` (data freshness SLA/credit tier). Do not call every Watcher “real time”.
- Company entity Watcher currently has a 30-day SLA only in the published pricing docs. Other Watcher types have tiered rates. Account-specific price/permission responses are authoritative.
- Cross-dataset filters have limitations. For example, filters can ask whether a matching record exists, not arbitrary counts like “five or more new roles”. Respect documented index-tier versus realtime-watch behaviour.

### Credit controls
The user reports approximately **US$4,500 worth of Crustdata credits**. This is a dollar-equivalent entitlement, not necessarily 4,500 API credits. Never convert it yourself or hardcode public list prices as the account price.
Before any meaningful paid usage, call the free endpoints (if key is configured):
- `GET /account/credits`
- `GET /account/endpoints`
Use account-specific prices/entitlements, inspect `X-Credits-Used` response headers and maintain a per-run credit ledger. Search first, enrich only selected records, cap results, and do not create broad 1-day SLA watchers by default. The first Watcher baseline/test paths are free; budget later deliveries.
Never place secrets in frontend code, git, logs, documentation, screenshots or demo video.

The event deck also gives the optional developer MCP setup:
`claude mcp add --transport http crustdata https://install.crustdata.com/mcp`
Check whether it is already configured. MCP may help explore Crustdata data during development, but the product runtime should make auditable backend REST calls unless you have a concrete, reliable reason to deploy an MCP-based runtime.

## Use the prior architecture selectively
The prior documentation describes:
- Layer 1 source scanning/adapters and cheap deterministic gates.
- Layer 2 15-step intelligence pipeline: validation, evidence hydration, normalization, atomic claims, fingerprinting, clustering, classification, deterministic scoring, impact assessment, detected changes, delivery preparation, profiles and history.
- Layer 3 delivery.
- Feedback and policy governance: feedback capture, feature extraction, pattern mining, proposals, human review, policy packs and evaluation.
- Observability: pipeline runs, agent telemetry, LLM cost ledger, source health, incident records and operations copilot.

Retain and simplify the strongest ideas: provenance, atomic claims, deterministic fingerprints, conservative deduplication, explainable scoring, impact assessment, feedback records, policy versions and execution telemetry.

Do not reproduce all 32 admin screens, all old adapters, complete Azure infrastructure, all delivery channels or the full operations copilot for the hackathon.

### Important defects and architectural gaps to correct in the new design
1. The old impact prompts and scoring are grounded in Godrej/FMCG. Generalize the core to a configurable home organization, market, competitors and persona.
2. The old system has a single active scoring profile. Redesign policy/scoring to be scoped at least by persona (and structurally support workspace scope).
3. The old docs describe two non-unified suppression systems. Define one clear enforcement path for the new runtime; do not preserve confusing parallel semantics in the MVP.
4. The old natural-language endpoint `POST /admin/feedback/nl-command` executes `add_rule`, `suppress`, `adjust_weight`, etc. immediately and returns no proposals. This bypasses governance. Do not reuse it as-is.
5. New natural-language feedback must produce a typed, bounded proposal in `pending_review` state. It must never directly mutate active policies.
6. The old `approve_proposal` path activates regardless of risk level. Add explicit validation, risk gates and reviewer authority.
7. Existing policies are not persona-scoped. Add persona-specific policies and ensure feedback for one persona does not leak into another.
8. Existing missed/false-negative feedback has incomplete proposal-builder coverage. In the new plan, define the minimum supported feedback taxonomy and explicitly mark unsupported types.
9. The supplied ZIP has documentation only, not the app code. Treat the docs as a blueprint. Do not claim to patch or preserve source code you cannot find.
10. Existing release notes say the server enqueues jobs but no worker consumes them automatically in server mode. Do not copy that runtime trap into the MVP; make the end-to-end run path executable from a single local command.

## Technology stack and cost constraints — PM decision, do not reopen
The supplied product archive is documentation, not executable source code. The old documentation already describes a Python/FastAPI backend, SQLite local storage and SQLAlchemy. Reuse that proven direction rather than adding a new stack.

**Default hackathon stack (free/open-source, local-first):**
- Runtime: Python 3.11+.
- Backend/API: FastAPI + Uvicorn + Pydantic v2.
- HTTP/API client: `httpx` for Crustdata REST calls.
- Persistence: SQLite local file + SQLAlchemy 2.x. Use SQLite for requests, canonical entity references, raw Watcher envelopes, normalized events, evidence, persona policies, feedback, policy proposals, policy versions, run records and credit ledger.
- UI: FastAPI-served Jinja2 templates with plain HTML/CSS/vanilla JavaScript. Use one cohesive responsive dashboard. Do not introduce a separate React/Next/Vite build unless an existing working frontend is actually present in the project directory and reusing it is faster than rebuilding.
- Background execution: one in-process async/synchronous orchestration path and FastAPI endpoints. No distributed queue for the demo. Watcher events arrive through a webhook when a reachable HTTPS endpoint is already available; otherwise use Crustdata's documented pull/run-history reconciliation. Do not lose time debugging tunnels.
- LLM integration: one small provider abstraction with structured JSON output. Use an existing runtime LLM API key only if the user explicitly supplies one. A Claude Code subscription is not automatically an application API key. If no runtime LLM key exists, provide a clearly labelled deterministic parser for the limited supported policy commands; never claim that fallback is LLM reasoning.
- Tests: pytest and FastAPI TestClient/httpx. Add tests for key data, policy and webhook paths.
- Local run: a single documented command such as `uvicorn app.main:app --reload`. Keep the complete demo runnable on the local machine.

**Do not add these for the hackathon:** paid hosting, managed databases, Azure services, Redis, Celery, Kafka, Temporal, Kubernetes, Neo4j, a hosted vector database, LangChain/LangGraph, paid monitoring services, paid UI kits or a complex deployment pipeline. Do not require Docker. Do not make deployment a blocker; a reliable local demo plus public GitHub repository and Loom video satisfies the submission format.

All application dependencies must be free/open-source to install and run. Crustdata usage is the only planned paid data dependency and must be metered against the user's actual account entitlements. Runtime LLM usage is a separate potential cost and must not be hidden inside the Crustdata credit budget. Before choosing any optional hosted service, prove that a free tier exists, is currently available to this account and is not required for the core demo. Prefer no hosted service.

Inspect installed Python/Node versions and available package managers before setup. Because no app source repository is included in the supplied ZIP, use the default stack above unless the user later supplies a working codebase whose stack should be preserved.

## Priority hierarchy — observability is last
Do not confuse minimum traceability with a full observability product:
1. **P0 — Complete service outcome:** new natural-language request → Crustdata identity resolution and evidence retrieval → connected/deduplicated signals → finished intelligence brief.
2. **P0 — Facts and verification:** canonical IDs, source URLs/records, timestamps, claim evidence, fact/inference separation and abstention when evidence is missing.
3. **P0 — Crustdata Watcher:** create at least one correctly scoped watch, read it back, and prove webhook or pull/run-history ingestion. Initial report must use separate Search/Identify/Enrich/Web calls; a Watcher baseline is not historical change data.
4. **P0 — Customer-value differentiator:** evaluate the shared event set for Corporate Strategy and VC personas; natural-language feedback creates a persona-scoped proposal, before/after simulation, approval and versioned activation.
5. **P0 — Robustness and submission:** handle ambiguous entities, empty/partial data, duplicate events, API failures/rate limits and cost limits; prepare a truthful two-minute demo and public repository.
6. **P1 — Minimum run trace only:** record request ID, pipeline stage, Crustdata endpoint, status, duration, records/counts, Watcher ID/run ID, policy version, failure and actual credits used. Show a compact trace only if the core workflow is already complete. Add these fields as part of the core data path; do not build a separate observability suite.
7. **P2 / LAST — Full observability layer:** detailed agent telemetry dashboards, source-health analytics, P95 charts, cost dashboards, incident management, remediation workflows and an LLM operations copilot. Defer all of this unless every P0 criterion and the demo are already reliable.

**Stop rule:** Once the P0 request-to-report, Watcher path, two persona views, governed feedback path, essential edge cases and demo are working, stop feature development. Do not spend remaining time on full observability. Only fix critical defects, verify the demo and submit.

## Persona-specific policy model — mandatory design
Create two MVP presets:
- Corporate Strategy / Competitive Intelligence Lead.
- VC Investment Partner.

Each persona should define:
- Decision objective and context.
- Market/companies/people of interest.
- Signal categories and relevance weights.
- Evidence requirements and source preferences, without weakening global evidence rules.
- Alert/relevance thresholds.
- Strategic interpretation lens and output style.
- Shared Watcher scope vs persona-specific Watcher requests.

The same event should be stored once and assessed under both persona policies. Demonstrate that it can be important to one persona and low priority to another, with a transparent score breakdown.

### Natural-language feedback governance — mandatory differentiator
Example feedback:
“For the VC Partner persona, suppress routine junior hiring alerts. Prioritize senior leadership changes, funding, founder moves and GTM expansion. Do not lower the evidence threshold.”

Required flow:
1. Capture free text and persona scope.
2. Parse to a strict JSON/typed policy proposal: scope, conditions, action, weight adjustment, rationale, risk, affected signals and proposed tests.
3. Deterministically validate allowed fields/operators, bounds and immutable evidence guardrails.
4. Show before/after policy diff and example events affected.
5. Replay the proposal on the stored event set and show ranking/impact changes.
6. Require human approval.
7. Create an immutable new policy version with audit record; retain rollback.
8. Apply only to that persona; the other persona remains unchanged.

If the proposal modifies Watcher filters or cadence, calculate/estimate account-specific credit impact and require a separate explicit approval before reconfiguring Watchers. Do not silently increase spend.

## The first-pass deliverable: analyze, decide, rewrite docs, then STOP
This is the first prompt, not the implementation prompt. Do not write application code yet. Finish the audit and documentation revamp quickly (target 10 minutes; no open-ended research). Then wait for the implementation prompt.

### Step A — inspect and summarize
- Inventory files and source documents.
- Read the PM Verdict and competition documents.
- Read prior docs covering system architecture, Layer 1, Layer 2, data model, feedback governance, scoring/impact, observability, setup tutorials, API references and release notes.
- Inspect current official Crustdata Watcher docs and the `llms.txt` index. Record exact endpoint families, webhook behaviour, baseline semantics, credits and constraints.
- Distinguish documented old design from verified new API facts and PM decisions.

### Step B — produce the final product plan
Create `docs/product-v2/FINAL_PRODUCT_PLAN.md` with:
1. One-sentence product definition.
2. Customer and buyer.
3. Primary theme and adjacent customer segment.
4. Exact job/service being replaced.
5. User inputs and finished outputs.
6. The end-to-end workflow.
7. Crustdata API and Watcher mapping per stage.
8. Persona model and policy hierarchy.
9. Natural-language feedback governance lifecycle.
10. Evidence model and canonical identity requirements.
11. Minimal observability model.
12. Credit-budget rules.
13. Explicit MVP scope and deferred scope.
14. Acceptance criteria mapped to all five judging criteria.
15. Two-minute demo outline.
16. Risk register and unresolved assumptions.

Make decisions, do not merely list alternatives. Use the attached PM Verdict as the decision authority.

### Step C — copy and adapt the old documentation
Preserve originals unchanged.
- Copy the extracted old docs directory to `docs/competitive-intelligence-v2/` (or the closest clear name).
- Keep the copy structurally intact enough that original source material remains traceable.
- Do not edit the original source folder or uploaded ZIP.
- Create `docs/product-v2/README-FIRST.md` explaining that these are the authoritative hackathon docs.
- Rewrite or add concise Markdown versions of the following authoritative documents under `docs/product-v2/`:
  - `PRODUCT_BRIEF.md`
  - `ARCHITECTURE.md`
  - `CRUSTDATA_INTEGRATION.md`
  - `WATCHER_INGESTION.md`
  - `PERSONA_POLICY_MODEL.md`
  - `FEEDBACK_GOVERNANCE.md`
  - `OBSERVABILITY.md`
  - `DATA_MODEL.md`
  - `CREDIT_BUDGET.md`
  - `BUILD_BACKLOG.md`
  - `DEMO_SCRIPT.md`
  - `SOURCE_DECISIONS.md`
  - `DOCUMENTATION_CHANGELOG.md`
- Update the copied `README-FIRST.txt` or add a new README-first file at the top of the copied docs to point to the new authoritative docs.
- In the revised docs, mark old features as RETAIN, REVAMP, SIMPLIFY, DEFER or REMOVE. Mark GCP/FMCG-specific configurations as legacy examples only.
- Do not spend time editing all 98 old HTML pages. The new Markdown files are the authoritative v2 docs; the copy is preserved as traceable legacy reference. Add a clear mapping/change log.

### Step D — create a build-ready backlog
In `docs/product-v2/BUILD_BACKLOG.md`, give:
- P0 tasks in strict implementation order.
- P1/P2 tasks that must be deferred.
- Exact acceptance criteria.
- A critical path and what to cut first.
- A “stop building” checklist.

The event schedule says last call is 3:00 PM IST and code/repo/Loom submission is due 3:30 PM IST on 31 October 2026. At prompt creation it is approximately 1:15 PM IST. Recalculate remaining time if needed. This plan/documentation pass must not take more than 10 minutes. The build must target feature freeze at 3:00 PM, not 3:30 PM.

### Step E — final response
After writing the files, report only:
- The final product definition.
- The five most important product decisions.
- The P0 implementation order.
- The selected free/local-first technology stack and any required user-supplied runtime API keys.
- Confirmation that full observability dashboards/ops copilot are deferred to the final priority tier.
- The exact files created/copied/updated.
- Any blocker requiring the user (especially missing API key or missing source file).

Then STOP. Do not begin application coding until the next instruction.

## Hard constraints
- No FMCG or Godrej assumptions in the core product.
- No fake Crustdata calls, fake Watcher events, fabricated companies or precomputed final reports.
- No direct policy mutation from natural-language feedback.
- No activation of persona policy without approval.
- No weakening global evidence/security guardrails.
- No uncontrolled Watcher creation or broad 1-day SLA feeds.
- No secret values in files, docs, git, logs or UI.
- No mass rewriting of legacy documentation pages; prioritize new authoritative v2 docs.
- No coding during this first prompt.
- No unnecessary clarifying questions. Make the PM decisions above and expose only true blockers.

Begin now.