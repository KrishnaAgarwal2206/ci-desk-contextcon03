# BUILD BACKLOG

Clock (IST, 31 Oct 2026): docs pass ended ~13:50 (ran over the 10-min target). **Feature freeze 15:00. Submit by 15:30.** ≈70 min build.

## P0 — strict order
| # | Task | Acceptance | Target |
|---|---|---|---|
| 0 | Scaffold: `app/`, `requirements.txt`, `.env.example`, `.gitignore` (.env, app.db), `git init`, models, `uvicorn` boots | `GET /health` 200; `.env` ignored | 13:55 |
| 1 | Crustdata client + preflight (credits, endpoints) + ledger | Real balance shown; `api_call` rows with `X-Credits-Used`; 429/402/403/timeout handled | 14:05 |
| 2 | Planner (deterministic_v1; LLM only if key) + Company Identify with ambiguous/unresolved states | Unseen brief → entity list with Crustdata IDs/confidence | 14:12 |
| 3 | Evidence: enrich + job search + person search + web search (capped) → evidence rows | Every row has source URL/record ref + retrieved_at | 14:22 |
| 4 | Normalize → claims (fact/inference) → events (fingerprint dedupe) | Re-running same input adds no duplicate events | 14:27 |
| 5 | Persona presets + scoring + per-persona brief + UI page | Same events, different ranks + score breakdown for CI vs VC | 14:37 |
| 6 | Watch: create company entity watch, read back, test, runs reconcile; webhook receiver w/ HMAC, ±300 s, idempotency, test isolation | Real watch ID visible; signed test payload stored as `test`; dup ignored; bad sig 401 | 14:47 |
| 7 | Feedback governance: parse → validate → diff → replay → approve → version → rollback; persona isolation | Demo sentence → pending proposal; approval changes VC ranks only; CI unchanged | 14:57 |
| 8 | pytest: webhook sig/dup/test, proposal guardrail rejection, persona isolation, dedupe, 402/empty handling (mock transport) | `pytest` green | 15:00 |
| — | **FEATURE FREEZE 15:00** | | |
| 9 | README (service, who pays, what it does/needs a person for, next, how to run, where Crustdata is called, approaches tried), fresh-request run, record Loom, push public repo, verify Loom in private window, submit | Submitted | 15:25 |

## Critical path
1 → 2 → 3 → 5 (request-to-brief) is the spine. 6 and 7 hang off stored events.

## Cut first (in this order)
1. Web Fetch (keep Web Search). 2. Person Enrich (keep Person Search). 3. LLM provider (deterministic only). 4. Rollback endpoint (keep versions). 5. Job discovery watch. 6. Trace panel styling (keep table). Never cut: real Crustdata calls, provenance, watch create/read-back, two personas, pending-review proposal + approval.

## P1 (only if P0 done before 15:00)
Compact run-trace panel polish; job discovery watch with narrow filter; cluster view.

## P2 / deferred
Full observability, dashboards, ops copilot, incidents, more personas, auth/RBAC, email/Teams, schedulers, cross-dataset watches, social posts, legacy adapters, deployment.

## Stop-building checklist (all true → stop)
- [ ] Fresh request completes end-to-end with live Crustdata records
- [ ] Findings cited; facts vs inference labelled; ambiguous entities shown
- [ ] ≥1 watch created + read back; test delivery or run-history pull verified
- [ ] Same events ranked differently for two personas
- [ ] NL feedback → pending proposal → approval → new version → VC result changes, CI unchanged
- [ ] Trace shows calls, failures, actual credits
- [ ] App starts with one command; Loom recordable
