# DOCUMENTATION CHANGELOG

## 2026-10-31 — v2 docs created
- Copied `Competitive-Intelligence-Docs/` → `docs/competitive-intelligence-v2/` unchanged except for an added `README-FIRST-V2.txt` pointer. Original folder untouched. (No ZIP was present in the project directory.)
- Added 14 authoritative Markdown docs under `docs/product-v2/`.

## Legacy → v2 mapping
| Legacy page(s) | Status | v2 doc |
|---|---|---|
| concepts/system-architecture | REVAMP | ARCHITECTURE.md |
| concepts/layer1-scanning, how-to/add-source-type, configure-news-profile, run-manual-scan | REVAMP → Crustdata/Watcher; adapters DEFER | CRUSTDATA_INTEGRATION.md, WATCHER_INGESTION.md |
| concepts/layer2-pipeline, item-lifecycle | SIMPLIFY (15 → 7 stages) | ARCHITECTURE.md, DATA_MODEL.md |
| concepts/scoring-and-impact, how-to/tune-scoring-weights | REVAMP (persona-scoped, industry-neutral) | PERSONA_POLICY_MODEL.md |
| concepts/feedback-learning, how-to/review-feedback-proposals, compile-policy-packs, run-eval-harness, admin-panel/governance-screens, reference/api/feedback-governance | REVAMP; NL command REMOVE/REBUILD | FEEDBACK_GOVERNANCE.md |
| how-to/manage-suppressions | SIMPLIFY/UNIFY (one path) | PERSONA_POLICY_MODEL.md |
| concepts/data-model-and-lineage, reference/data-model | RETAIN/SIMPLIFY | DATA_MODEL.md |
| concepts/observability-and-telemetry, admin-panel/observability-screens, operations/monitoring, incident-response, reference/api/observability | RETAIN minimal / DEFER rest | OBSERVABILITY.md |
| concepts/llm-abstraction | SIMPLIFY | ARCHITECTURE.md |
| how-to/send-weekly-digest, reference/api/intelligence-delivery | DEFER (in-app only) | — |
| how-to/add-competitor, get-started/configuration, reference/configuration (FMCG/Godrej competitor set) | LEGACY EXAMPLE only | PERSONA_POLICY_MODEL.md |
| admin-panel/* (32 screens) | DEFER | ARCHITECTURE.md |
| operations/deployment, backup-migrations (Azure) | REMOVE | ARCHITECTURE.md |
| release-notes (enqueue-without-worker) | Defect noted, not copied | ARCHITECTURE.md |
| get-started/*, reference/cli, error-handling, troubleshooting, recover-failed-run | Superseded by repo README at build | BUILD_BACKLOG.md |
