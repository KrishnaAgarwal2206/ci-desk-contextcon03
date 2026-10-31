# Claude Prompt 2 — Start building now

The product decisions and implementation plan are finalized in `docs/product-v2/`. The updated PM direction is in `PM_Verdict_v3.md`.

**Stop planning. Stop auditing. Start writing application code.**

You are implementing the **Persona-aware Competitive Intelligence Desk** for ContextCon 03. The objective is a working, demonstrable end-to-end service, not a large unfinished architecture.

## 1. First actions

Inspect the current repository, `docs/product-v2/` and Git state. Preserve all existing documentation and the original legacy archive.

Create the application structure, `.env.example`, `.gitignore`, dependencies and SQLite models. Ensure `.env`, local databases, caches and generated secrets are excluded from Git.

The application must boot with:

```bash
uvicorn app.main:app --reload
```

Add a working health endpoint immediately.

Do not wait for API keys before scaffolding or implementing mockable provider interfaces. I will put actual keys in the local `.env` file. Never ask me to paste keys into chat.

## 2. Build priorities — strict order

### P0-A: Crustdata foundation

Build a reusable HTTPX client.

Implement:

- Authentication and request headers, following current official Crustdata documentation.
- Account credit and entitlement preflight where supported.
- Endpoint/request status logging.
- Actual `X-Credits-Used` accounting.
- Per-run budget checks using the documented 150-credit default cap.
- Timeouts and bounded retries for safe transient failures.
- Explicit handling of 402, 403, 429, empty and malformed responses.
- No secret logging.

Verify exact endpoint paths, headers, payloads and response fields against current Crustdata documentation or real API responses. Do not invent or guess fields.

### P0-B: Fresh research request to evidence

Build a user-facing form accepting a plain-English market or competitor brief.

The workflow must:

1. Parse the brief into structured research intent.
2. Use Company Search for market-level discovery where appropriate.
3. Use Company Identify to resolve canonical company IDs.
4. Display confidence, alternatives, ambiguous matches and unresolved matches.
5. Selectively enrich resolved companies.
6. Search relevant people and job postings where appropriate.
7. Use Web Search for supporting public evidence.
8. Store evidence, source references, URLs or field paths, retrieval times and response metadata.

Prefer a few high-information-value API calls over broad uncontrolled discovery.

### P0-C: Claims, events and persona intelligence

Build the evidence-processing pipeline:

- Normalize retrieved records.
- Extract atomic claims and preserve evidence references.
- Distinguish facts, inferences and unknowns.
- Generate event fingerprints and deduplicate repeated records.
- Store one shared event per underlying development.
- Calculate deterministic base significance.
- Apply separate CI Lead and VC Partner policies.
- Store score components and policy versions.

The same event must be capable of receiving different scores and explanations under the two personas.

### P0-D: Anthropic runtime

Implement the Anthropic provider using HTTPX and the current official Messages API.

Defaults:

- Model: `claude-sonnet-5-5`, configurable through `ANTHROPIC_MODEL`.
- Endpoint: `https://api.anthropic.com/v1/messages`.
- API version: `ANTHROPIC_API_VERSION`, default `2026-10-21` from `.env.example`; verify current official docs.
- Load the API key only from the backend environment.

Implement exactly these uses:

**Call 1 — Research request planner**

Natural-language brief → validated structured research plan.

**Call 2 — Intelligence synthesis**

Shared evidence/events → two persona-specific, evidence-grounded briefs. Prefer one call returning both persona views if reliable.

**Call 3 — Feedback interpretation**

Natural-language feedback → typed `PolicyProposal`.

Use validated structured output. Reject malformed or unsupported policy operations.

Enforce the default USD 5 total application spend ceiling, the per-request call limit and output-token cap. Track input/output token usage and estimated USD cost. Estimate current model pricing rather than assuming a permanent price.

On absent key, timeout, rate limit, budget exhaustion or invalid response, fall back to deterministic logic and label the mode clearly in the UI.

The LLM must not resolve canonical company identities, invent facts, change numerical persona scores or activate policies.

### P0-E: Watcher

Implement the shared Company Entity Watcher:

- Create Watcher for resolved competitor IDs.
- Read it back and display the real ID and configuration.
- Respect the approved schedule, freshness constraint, entity limit and result cap.
- Implement test notification handling.
- Implement webhook signature verification, timestamp tolerance and idempotency when a public HTTPS endpoint is configured.
- Otherwise implement run-history pull and reconciliation.
- Keep test and baseline records out of the actual intelligence event stream.

Do not fabricate a live change event for the demo.

### P0-F: Feedback governance

Implement the minimum complete lifecycle:

`Natural-language feedback → typed proposal → validation → before/after policy diff → replay against stored events → reviewer approval → immutable new policy version → persona-specific re-scoring`

Include rollback only if time permits.

Global evidence and integrity rules cannot be weakened. A VC policy change must not silently alter the CI Lead's active policy or scores. Watcher scope or spend-increasing changes require separate approval.

### P0-G: Tests and operational reliability

Implement essential pytest coverage for:

- Canonical identity ambiguity.
- Evidence provenance.
- Event deduplication.
- Different persona scores and persona isolation.
- Invalid policy proposals.
- Approval and policy versioning.
- LLM fallback and budget exhaustion.
- Crustdata 402/403 and 429 handling.
- Webhook signature rejection and duplicate protection.
- Test notification isolation.

Use mocked API responses for automated tests. Avoid unnecessary live API calls.

## 3. User interface

Keep the interface focused and polished. Demonstrate:

1. Submit a research brief.
2. Resolve companies and show Crustdata IDs.
3. Show collected evidence and sources.
4. Show the intelligence brief.
5. Switch between CI Lead and VC Partner views.
6. Inspect event score breakdowns.
7. View Watcher configuration and actual monitoring status.
8. Submit natural-language feedback.
9. Review a proposal and its diff.
10. Approve it and show the resulting policy version and changed ranking.
11. Inspect a compact execution trace showing Crustdata credits and Anthropic token/cost usage.

Do not create a large admin dashboard or unrelated screens.

## 4. Demo integrity

The demo must use a fresh research request, not only preloaded static output.

- Use actual Crustdata responses when credentials are configured.
- Clearly identify deterministic fallback, mock data, test notifications, baseline samples and unavailable APIs.
- Never describe test payloads as real events.
- Every factual claim must trace to an actual evidence record.
- Do not claim real-time monitoring; show actual Watcher schedule and freshness.
- Show whether each brief used LLM-assisted or deterministic mode.

## 5. Scope discipline

Do not introduce Redis, Celery, Kafka, Kubernetes, microservices, Neo4j, LangChain, LangGraph, paid monitoring systems, unnecessary hosting or unrelated dependencies.

Use the local-first stack: Python, FastAPI, Pydantic, HTTPX, SQLAlchemy, SQLite, Jinja2, vanilla JavaScript and pytest.

Do not spend time building full observability dashboards. Keep a compact execution trace.

If time is constrained, cut in this order:

1. Web Fetch.
2. Person Enrich.
3. Extra discovery APIs or watchers.
4. UI polish.
5. Rollback endpoint.

Do not cut the fresh-request-to-evidence workflow, Crustdata identity resolution, evidence provenance, persona differences, pending-review feedback proposal or Watcher creation/read-back.

If Anthropic integration cannot be completed in time, preserve its provider interface and deterministic fallback. Do not sacrifice Crustdata correctness to finish it.

## 6. Feature freeze and submission

Follow the feature-freeze and submission deadline in `BUILD_BACKLOG.md`.

At feature freeze:

- Stop adding features; fix only critical bugs.
- Complete README and run instructions.
- Run tests.
- Execute one fresh-request smoke test.
- Record the two-minute Loom: request → evidence → persona views → feedback approval.
- Push and verify the public GitHub repository.
- Verify the Loom in a private browser window.
- Submit.

Keep Git history meaningful and ensure it reflects actual work.

## 7. Execution rules

Do not ask me to reconfirm product direction. Do not spend another round producing a plan. Do not wait for missing API keys before scaffolding or implementing mockable provider interfaces.

Make sensible engineering decisions independently and document unavoidable deviations.

Start with the application scaffold and Crustdata client. Build the vertical slice incrementally. Keep the application runnable throughout development.

**Start coding now.**
