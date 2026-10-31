# ContextCon 03 — PM Verdict v3
## Controlled Anthropic runtime + deep Crustdata integration

**Decision: APPROVE Anthropic runtime integration, with strict boundaries and a deterministic fallback.**

The product remains the **Persona-aware Competitive Intelligence Desk**: a continuous, evidence-backed competitive intelligence service with one shared evidence base, two persona-specific interpretations (Corporate Strategy / CI Lead and VC Investment Partner), shared Crustdata Watchers, and governed natural-language feedback.

The Anthropic integration improves request interpretation, intelligence synthesis, and feedback interpretation. It must not become the source of truth or a prerequisite for running the application.

## 1. Product decisions

| Capability | Decision |
|---|---|
| Natural-language research request | Anthropic-assisted structured request planning; deterministic fallback |
| Company discovery and identity | Crustdata APIs; never ask an LLM to invent or resolve canonical IDs |
| Enrichment and evidence collection | Crustdata as primary intelligence infrastructure |
| Evidence provenance and validation | Deterministic |
| Claims, event fingerprints and deduplication | Deterministic |
| Persona scoring and score breakdowns | Deterministic, policy-based and versioned |
| Intelligence brief | Anthropic synthesis grounded only in stored evidence |
| Natural-language feedback | Anthropic creates a typed proposal; it cannot approve or activate it |
| Watcher management | Crustdata Watcher, shared across personas |
| Cost and execution trace | Track Crustdata credits and Anthropic usage separately |

**Core principle:** the LLM improves interpretation and communication; Crustdata supplies the external company and market evidence; deterministic code enforces identity, provenance, scoring, governance and control.

## 2. Anthropic runtime — approved, bounded use

Use the Anthropic Messages API through HTTPX. Keep the provider behind a small service interface and make the model configurable.

- Default model ID: `claude-sonnet-5-5`
- Messages endpoint: `https://api.anthropic.com/v1/messages`
- Default API version: `2026-10-21` (configurable; use the current documented version)
- Authentication: `Authorization: Bearer $ANTHROPIC_API_KEY`
- Required request headers include `anthropic-version` and `content-type: application/json`.

Use the LLM for three bounded tasks:

1. **Research request planning:** convert a plain-English request into a validated structure containing market/category, named companies, geography, signal types, time window, relevant people and requested personas.
2. **Intelligence synthesis:** synthesize stored evidence and events into CI Lead and VC Partner briefs. Prefer one call that returns both persona views where reliable. Every factual statement must point to existing evidence IDs.
3. **Feedback interpretation:** translate natural-language stakeholder feedback into a typed `PolicyProposal`. The proposal must be validated, diffed, replayed against stored events and approved by a human before activation.

Do not use an LLM for company/person canonical identity resolution, API calls, credit accounting, evidence storage, fact validation, claim/event deduplication, numerical scoring, policy validation, approval, activation or Watcher management.

### Runtime spend controls

- Application-level Anthropic spend ceiling: **USD 5** for the hackathon by default; configurable.
- Maximum LLM calls per research request: **3** by default.
- Maximum output tokens: **1,200** by default.
- Track provider, model, request ID, input tokens, output tokens, estimated cost, duration and outcome.
- Estimate cost from the configured model's current pricing; do not hard-code pricing as permanent truth.
- Check the remaining application budget before each request.
- No automatic credit reload and no uncontrolled retries.
- On missing key, timeout, rate limit, budget exhaustion or invalid structured response, fall back to deterministic logic and label the mode in the UI.
- Do not assume the full organization credit balance is dedicated to this application. Other users may share it.

As checked on 31 October 2026, Anthropic's official model overview lists Claude Sonnet 5.5 (`claude-sonnet-5-5`) at USD 2 per million input tokens and USD 10 per million output tokens. Re-check the official pricing before implementation and keep pricing configurable.

## 3. Crustdata — maximize useful coverage, not raw calls

Crustdata remains central to the system. The request workflow should use APIs selectively, according to the request and expected information value.

1. **Preflight:** check balance/entitlements where supported; record starting balance; enforce the existing 150-credit default run cap; record actual `X-Credits-Used`; stop on 402/403; handle 429 and transient failures safely.
2. **Discovery:** use Company Search when the user describes a market/category/landscape without naming all competitors.
3. **Identity:** use Company Identify for named companies and resolve canonical Crustdata IDs. Surface ambiguous and unresolved matches; never guess.
4. **Enrichment:** selectively use Company Enrich for relevant company attributes such as firmographics, funding, headcount and news.
5. **People:** use Person Search for relevant founders, executives and decision-makers.
6. **Hiring signals:** use Job Search when hiring or capability changes are relevant to the research question.
7. **External evidence:** use Web Search for supporting public evidence; use Web Fetch only for a small number of relevant pages when useful and affordable.
8. **Continuous monitoring:** create one shared Company Watcher over resolved competitors, read it back, record its actual ID/configuration, and reconcile future runs. Do not duplicate Watchers for the two personas.

Respect the documented MVP constraints already captured in `CRUSTDATA_INTEGRATION.md`, `WATCHER_INGESTION.md` and `CREDIT_BUDGET.md`: weekly schedule, 30-day freshness constraint for this watch type, at most 25 results per run, test/baseline separation, webhook signature verification and duplicate protection where a public HTTPS endpoint exists, and run-history polling otherwise.

Verify endpoint paths, field names, authentication and response fields against current official Crustdata documentation and the first real responses. Do not invent payloads or rely on unverified `VERIFY-LIVE` fields. Do not call every endpoint for every company. Maximize useful, verified intelligence coverage per credit.

## 4. Shared evidence base and persona lenses

- Store each underlying event once and associate it with canonical Crustdata company/person identities.
- Generate a separate deterministic score and explanation for each persona using that persona's active policy version.
- Keep score components visible.
- Persona preference changes may alter relevance, weights, prioritization and recommendations; they must not weaken global evidence integrity, provenance or verification rules.
- A policy change for one persona must not silently change the other persona's policy or scores.

## 5. Feedback governance

Required flow:

`Natural-language feedback → typed proposal → validation → before/after diff → replay on stored events → reviewer approval → immutable policy version → persona-specific re-scoring`

The LLM only proposes. Human approval and deterministic validation control activation. Keep audit history. Reject malformed, unsupported, out-of-bounds or integrity-weakening proposals. Watcher scope or spend-increasing changes need separate approval.

## 6. Build priority

1. Runnable scaffold, configuration, health endpoint and SQLite models.
2. Crustdata HTTP client, authentication, preflight and credit accounting.
3. Fresh request → Company Search/Identify → canonical IDs, with ambiguity handling.
4. Selective enrichment and evidence storage with source references and timestamps.
5. Claims, facts/inferences, event fingerprints and deduplication.
6. Deterministic persona scoring with visible breakdowns.
7. Anthropic provider and the three bounded tasks, with fallback and spend tracking.
8. Persona-specific briefs grounded in stored evidence.
9. Shared Watcher creation/read-back and webhook or run-history path.
10. Feedback proposal/review/approval/versioning lifecycle.
11. Essential pytest coverage, smoke test and demo hardening.

If time is constrained, cut Web Fetch, Person Enrich, extra discovery, UI polish and optional rollback before cutting the core request-to-evidence path, persona separation, source provenance, the governed feedback loop or Watcher creation/read-back.

Full observability dashboards, incident management and ops copilot remain out of scope. Keep a compact execution trace including request state, evidence count, Crustdata calls/credits, Anthropic usage/cost, policy versions, errors and timings.

## 7. Exact local environment

Use `.env.example` as the template. Actual secrets belong only in a local `.env` excluded from Git.

Required for live integration:

- `CRUSTDATA_API_KEY`

Optional runtime LLM:

- `ANTHROPIC_API_KEY`

Configuration defaults:

- `ANTHROPIC_MODEL=claude-sonnet-5-5`
- `ANTHROPIC_API_VERSION=2026-10-21`
- `LLM_ENABLED=true`
- `LLM_SPEND_CAP_USD=5`
- `LLM_MAX_CALLS_PER_REQUEST=3`
- `LLM_MAX_OUTPUT_TOKENS=1200`

Do not paste keys into source files, Git, public logs or the frontend.

## 8. Acceptance criteria

- A fresh, previously unseen research brief can be submitted.
- Real Crustdata responses are used when the key is configured; otherwise the UI clearly labels fallback/mock mode.
- Named companies resolve to canonical IDs or are explicitly marked ambiguous/unresolved.
- Evidence has source references and retrieval timestamps.
- Facts, inferences and unknowns are distinguished.
- The same event is stored once and receives meaningfully different CI Lead and VC scores/explanations where appropriate.
- Both briefs trace factual statements to existing evidence records.
- An actual shared Watcher is created and read back; monitoring status is represented honestly.
- Natural-language feedback creates a reviewable proposal; only approval activates a new immutable, scoped policy version.
- Missing/failed Anthropic access does not break the workflow.
- Anthropic spend and Crustdata credits are separately visible.
- Essential tests pass and the app starts with one documented command.

## 9. Official Anthropic references checked 31 October 2026

- Models and IDs: https://platform.claude.com/docs/en/models/overview
- Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- API overview/authentication: https://platform.claude.com/docs/en/api/overview
- Messages API: https://platform.claude.com/docs/en/api/messages/create
- API credit eligibility and coverage: https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-ultra-and-team-plans

**Final PM decision:** add Anthropic as a bounded runtime capability. Do not let it replace Crustdata, evidence verification, deterministic scoring or human governance. The app must remain functional without an Anthropic key.
