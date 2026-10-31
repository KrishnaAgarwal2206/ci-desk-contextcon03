# WATCHER INGESTION

## Families [FACT-API]
| Kind | Create | Read/manage | Use |
|---|---|---|---|
| Company entity | `POST /watch/company` | `GET /watch/company/{id}`, `/runs`, `/runs/{run_id}/summary`, `PATCH`, `DELETE`, `POST …/test` | **MVP watch** — known competitor set |
| Person entity | `POST /watch/person` | same pattern | Deferred (key executives) |
| Company discovery | `POST /watch/company/search` | reads drop `search/`: `GET /watch/company/{id}/runs` | Deferred |
| Person discovery | `POST /watch/person/search` | | Deferred |
| Job discovery | `POST /watch/job/search` | `GET /watch/job/{id}/runs` | Optional P0+ (narrow filter) |
| Social post discovery | `POST /watch/social_post/search` | | Deferred, account-enabled only |

## Semantics we must respect
- **Baseline:** first run snapshots tracked fields, diffs nothing, is free, and sends one sample notification of ≤5 records with `changes: []`. It is **not** history. `last_run_at` is `null` until baseline completes. Our receiver ignores entries with empty `changes` for event creation (stored raw, state `baseline_sample`).
- **Entity watch fires only on transitions**; never re-notifies a reported change. Newly added entities are baselined silently.
- **Test notification** (`POST /watch/company/{id}/test`, optional `count`): free, exact real envelope + signature, `metadata.test: true`, placeholder values; persists nothing. Stored with state `test` — never shown as intelligence.
- **Schedule vs SLA:** `config.trigger = {"type":"interval","every_hours":N}` is cadence; `config.refresh_frequency_days` is data freshness/price tier. Company entity watches are **30-day SLA only** (5 credits/changed company). Faster cadence only surfaces changes sooner; it does not raise freshness. UI wording: "scheduled monitoring", never "real time".
- `max_results_per_run` default 25 (1–10000; >1000 needs `payload_delivery_type: "link"`).
- Discovery 1-day SLA = `config.is_realtime: true` (150 credits/record, `every_hours ≥ 24`, refuses `filters`). **Forbidden by default.**
- Cross-dataset filters: existence only ("at least one matching record"), no counts, no growth on the other dataset, no cross-dataset negation; social posts join one-way; people join via current employer only; payload carries only the watch's own dataset records.

## MVP watch definition
```json
POST /watch/company
{ "entities": { "crustdata_company_ids": [ ... resolved IDs ... ] },   // key name [VERIFY-LIVE]; domains also allowed
  "track": { "op": "or", "conditions": [
      { "field": "headcount.total", "type": "changed" },
      { "field": "news", "type": "added", "keys": ["article_url"] } ] },  // funding field name [VERIFY-LIVE]
  "fields": ["basic_info", "headcount", "news"],
  "config": { "trigger": { "type": "interval", "every_hours": 168 }, "max_results_per_run": 25 },
  "notifications": [ { "type": "webhook", "url": "<PUBLIC_WEBHOOK_URL>" } ]   // or [] for pull-only
}
```
Cap: ≤10 companies per watch, one watch per request (shared by both personas — personas never create duplicate watches).

## Webhook receiver `POST /webhooks/crustdata`
1. Read **raw body** before parsing; reject > 1 MB.
2. Parse `x-crustdata-signature: t=<unix>,v1=<hex>`. Compute `HMAC-SHA256(key=API key, msg=f"{t}.{raw_body}")`; `hmac.compare_digest`. Mismatch → 401, stored as `rejected_signature` (headers only).
3. Timestamp tolerance ±300 s → else 401 `rejected_stale` (replay protection).
4. Idempotency: unique on `x-crustdata-event-id` / `metadata.notification_id` (+ `watch_id`). Duplicate → 200, `duplicate`, no reprocess.
5. Persist `watcher_envelope` (watch_id, run_id, notification_id, is_test, raw payload, received_at, state). Return 2xx quickly, then process in-process.
6. `metadata.test=true` → state `test`, stop. Empty `changes` → `baseline_sample`, stop. Else → normalize each `results[i]` (`changes` + `record.crustdata_company_id`) into evidence/claims/events.

## Pull reconciliation (fallback / primary if no public URL)
`GET /watch/company/{id}` (status, `last_run_at`) → `GET /watch/company/{id}/runs?limit=20` → for unseen run_ids `GET …/runs/{run_id}/summary` → feed records through the same path with source `run_history`. Check `notification_http_status` on runs: non-2xx means matches were found but delivery failed. Pull-only watch = `notifications: []`. Exposed as `POST /watches/{id}/reconcile` + a button.

## Honest demo framing
"Watch created at 13:xx, ID N, 30-day SLA, weekly schedule, baseline pending/complete, test delivery verified signature." No fabricated change events.
