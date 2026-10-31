# DATA MODEL (SQLite + SQLAlchemy 2.x)

| Table | Key columns |
|---|---|
| `request` | id, brief_text, plan_json, parser (`llm:<model>`/`deterministic_v1`), status (`running/complete/partial/failed`), budget_cap, created_at |
| `entity` | id, kind (`company/person`), crustdata_id (nullable), name, domain/profile_url, resolution (`resolved/ambiguous/unresolved`), confidence, alternatives_json, request_id |
| `evidence` | id, entity_id, source_type (`crustdata_enrich/job_search/person_search/web_search/web_fetch/watcher_webhook/run_history`), source_url, record_ref (endpoint + id + field path), excerpt_or_value, source_ts, retrieved_at, api_call_id |
| `claim` | id, event_id, text, kind (`fact/inference/hypothesis`), confidence, evidence_ids_json |
| `event` | id, fingerprint (UNIQUE), category, entity_ids_json, title, base_significance, first_seen_at, last_seen_at, source_count, cluster_id, origin (`initial_research/watcher`) |
| `persona_policy_version` | id, persona_id, workspace_id, version, body_json, is_active, created_by, created_at, parent_version — **immutable rows** |
| `assessment` | id, event_id, persona_id, policy_version_id, score, components_json, suppressed, rank, rationale |
| `brief` | id, request_id, persona_id, policy_version_id, body_json, created_at |
| `feedback` | id, persona_id, text, event_id, created_at |
| `policy_proposal` | id, feedback_id, persona_id, body_json, parser, state, validation_json, replay_json, risk, requires_credit_approval, reviewer, decided_at |
| `audit_log` | id, actor, action, object_type, object_id, diff_json, at |
| `watch` | id, crustdata_watch_id, kind, dataset, definition_json, status, last_run_at, created_at, request_id |
| `watcher_envelope` | id, crustdata_watch_id, run_id, notification_id (UNIQUE with watch), is_test, payload_json, signature_ok, received_at, state (`received/test/baseline_sample/processed/duplicate/rejected_signature/rejected_stale/error`), via (`webhook/run_history`) |
| `run_step` | id, request_id, stage, status, started_at, duration_ms, counts_json, error |
| `api_call` | id, request_id, stage, endpoint, http_status, duration_ms, result_count, credits_used (from `X-Credits-Used`), estimated_credits, watch_id, run_id, error — **no keys, no auth headers** |

## Fingerprint & dedupe (deterministic)
`fingerprint = sha256(category | sorted crustdata_ids | normalized key)`, key = e.g. `article_url`, `job_id`, `field:from→to`, funding round date. Same fingerprint → merge evidence, bump `source_count`. Clustering: same company + category within 14 days → shared `cluster_id`. Conflicting values are kept as separate claims, never averaged.

Legacy mapping: lineage/atomic claims/fingerprints → RETAIN/SIMPLIFY; Azure blob/queue tables → REMOVE.
