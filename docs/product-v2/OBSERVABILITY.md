# OBSERVABILITY — minimal, passive, last

## P1 (captured in the core path, not a separate build)
`run_step` and `api_call` rows (see `DATA_MODEL.md`): request_id, stage, endpoint, status, duration_ms, counts, `X-Credits-Used`, watch_id/run_id, policy_version, error. Shown as one compact collapsible "Run trace" table on the request page, plus credits balance before/after.

Never logged: API keys, Authorization headers, webhook signing material, full raw prompts.

## P2 / LAST — DEFERRED
Agent telemetry dashboards, P95 charts, source-health analytics, cost dashboards, incident records, remediation workflows, operations copilot. Only after every P0 acceptance criterion and the demo are reliable — under the stop rule, effectively not in this hackathon.

Legacy mapping: pipeline runs / cost ledger → RETAIN/SIMPLIFY; source health, incidents, ops copilot, monitoring screens → DEFER.
