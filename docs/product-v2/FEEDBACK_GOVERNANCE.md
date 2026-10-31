# FEEDBACK GOVERNANCE

Rule: **natural-language feedback proposes; it never activates.** Legacy `POST /admin/feedback/nl-command` (immediate execution) is REMOVED, not reused.

## Lifecycle & states
`captured → parsed → (invalid | pending_review) → simulated → approved | rejected → active_version_created`; any version can be the target of `rollback` (itself a new version pointing to an old body).

1. **Capture** `POST /feedback` `{persona_id, text, event_id?}` → `feedback` row.
2. **Parse** → `PolicyProposal` (Pydantic, strict):
```json
{ "persona_id": "vc_partner", "scope": "persona",
  "changes": [
    {"op": "add_rule", "when": {"category": "junior_hiring"}, "action": "suppress"},
    {"op": "adjust_weight", "category": "leadership_change", "delta": 0.0},
    {"op": "adjust_weight", "category": "funding", "delta": 0.1},
    {"op": "adjust_weight", "category": "founder_move", "delta": 0.1},
    {"op": "adjust_weight", "category": "gtm_expansion", "delta": 0.1} ],
  "guardrail_assertions": ["min_sources_unchanged"],
  "rationale": "...", "risk": "low|medium|high", "affected_categories": [...],
  "proposed_tests": [{"event_id": 12, "expect": "suppressed"}],
  "parser": "llm:<model>" | "deterministic_v1" }
```
   LLM (only if a runtime key is supplied) returns JSON only; no tools, no code. Without a key: `deterministic_v1` keyword parser for the supported taxonomy, labelled as such in UI.
3. **Validate** (deterministic): allowed ops/categories only; weights in bounds; |delta| ≤ 0.5; cannot touch global rules or lower `min_sources`; persona must match request scope; conflicts flagged; Watcher changes → `requires_credit_approval=true` with estimate.
4. **Diff** — before/after policy JSON.
5. **Replay** on stored events for that persona → before/after rank table, moved/suppressed events, proposed tests pass/fail. Failing tests block approval.
6. **Approve** `POST /proposals/{id}/approve` `{reviewer}` — requires reviewer ≠ empty; `risk=high` needs `confirm_high_risk=true`; blocked if validation/tests failed.
7. **Version** — new immutable `policy_version` row + `audit_log` (who, when, proposal_id, diff hash). Previous versions retained.
8. **Isolation** — only that `persona_id` re-scored; test asserts the other persona's active version and scores are unchanged.
9. **Rollback** `POST /personas/{id}/rollback` `{to_version}` → new version, audited.

## Supported taxonomy (MVP)
| Feedback type | Supported | Maps to |
|---|---|---|
| Suppress category / pattern | Yes | `add_rule` suppress |
| Prioritize / de-prioritize category | Yes | `adjust_weight` |
| Change alert threshold | Yes | `set_threshold` (bounded) |
| Require more evidence | Yes | `raise_min_sources` (up only) |
| Lower evidence / skip citations | **Rejected** | guardrail violation |
| Missed signal / false negative | **Partial** | weight increase on named category; no automatic new-signal detector |
| Change Watcher scope/cadence | **Proposal only**, separate credit approval, not executed in MVP | — |
| Free-form prompt rewrite | **Unsupported** | invalid |

Legacy mapping: proposals/human review/policy packs/eval harness → REVAMP (persona-scoped, replay-based). `approve_proposal` regardless of risk → REPLACED by risk gates.
