# ARCHITECTURE

Free, local-first. One process: `uvicorn app.main:app --reload`. No queue, no worker, no Docker (fixes legacy "server only enqueues, nothing consumes" trap: the request handler runs the pipeline in-process via `BackgroundTasks`/direct call).

```
Browser (Jinja2 + vanilla JS, one workspace page)
   │
FastAPI app ── /requests ─▶ Orchestrator (sync pipeline, stage-by-stage run_step logging)
   │                          1 planner (LLM or deterministic_v1)
   │                          2 preflight (credits, endpoints)
   │                          3 resolve (identify)          ─┐
   │                          4 evidence (enrich/jobs/people/web) ├─▶ crustdata.client (httpx, retries, ledger)
   │                          5 normalize → claims → events  │
   │                          6 score per persona            │
   │                          7 brief per persona            │
   │                          8 watch create/read/test      ─┘
   ├── /webhooks/crustdata ─▶ verify HMAC → idempotent store → same 5–7
   ├── /watches/{id}/reconcile ─▶ runs pull → same 5–7
   ├── /feedback, /proposals/*, /personas/* ─▶ governance (parse → validate → replay → approve → version)
   └── SQLite (app.db) via SQLAlchemy
```

## Modules
`app/main.py` (routes, templates) · `app/config.py` · `app/db.py`, `app/models.py` · `app/crustdata/client.py`, `app/crustdata/watcher.py` · `app/pipeline/{planner,resolve,evidence,normalize,score,brief}.py` · `app/policy/{presets,engine,proposals,parser}.py` · `app/llm.py` (optional provider, JSON mode) · `templates/` · `static/` · `tests/`.

## Stack (PM decision)
Python 3.11+ (3.12.4 installed) · FastAPI · Uvicorn · Pydantic v2 · httpx · SQLAlchemy 2 · SQLite · Jinja2 · pytest. **Not used:** React/Vite, Redis, Celery, Kafka, Temporal, LangChain, vector DBs, Azure, paid hosting.

## Legacy layer mapping
| Legacy | Decision |
|---|---|
| Layer 1 scanners/adapters (web, careers, news) | REVAMP → Crustdata APIs + Watcher; legacy adapters DEFER |
| Layer 1 cheap deterministic gates | RETAIN (dedupe/fingerprint before scoring) |
| Layer 2 15-step pipeline | SIMPLIFY → 7 stages above |
| Layer 3 delivery (email/Teams/digest) | DEFER → in-app brief only |
| LLM abstraction | SIMPLIFY → one provider, JSON only, optional |
| 32-screen admin panel | DEFER → one workspace + proposal review + trace panel |
| Azure deployment | REMOVE |
