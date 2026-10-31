# PERSONA POLICY MODEL

## Hierarchy
| Scope | Controls | Changeable by persona feedback? |
|---|---|---|
| Global integrity (code constants) | provenance required, fact/inference labels, min evidence count per material claim (≥1), no fabrication, identity handling, secrets | **No — immutable** |
| Workspace | watch scope, budget cap, common exclusions | Only via workspace reviewer |
| Persona | category weights, thresholds, evidence-depth *increase*, lens text, output style | Yes, via approved proposal only |
| Individual | presentation (length, order) | User, within persona bounds |

## Policy document (versioned JSON, one row per version)
```json
{ "persona_id": "vc_partner", "workspace_id": "default", "version": 3,
  "objective": "Identify execution capacity, momentum and competitive threats to theses/portfolio.",
  "category_weights": { "leadership_change": 1.0, "funding": 1.0, "founder_move": 1.0,
    "gtm_expansion": 0.9, "senior_hiring": 0.8, "junior_hiring": 0.2, "product_launch": 0.6,
    "partnership": 0.5, "headcount_change": 0.7, "news_mention": 0.3 },
  "rules": [ { "id": "r1", "when": {"category": "junior_hiring"}, "action": "suppress" } ],
  "alert_threshold": 0.55, "min_sources": 1, "source_preferences": ["crustdata_record", "news", "company_site"],
  "lens": "investor", "output_style": "bullet, thesis-oriented" }
```
Bounds: weights ∈ [0, 1]; delta per proposal ≤ 0.5; threshold ∈ [0.2, 0.9]; `min_sources` may only go **up** from the global minimum.

## Presets (v1)
| Category | CI Lead | VC Partner |
|---|---|---|
| leadership_change | 0.8 | 1.0 |
| funding | 0.6 | 1.0 |
| founder_move | 0.5 | 1.0 |
| gtm_expansion | 0.8 | 0.9 |
| product_launch | 1.0 | 0.6 |
| partnership | 0.9 | 0.5 |
| senior_hiring | 0.8 | 0.8 |
| junior_hiring | 0.4 | 0.4 (→0.2 / suppress in demo feedback) |
| headcount_change | 0.6 | 0.7 |
| news_mention | 0.5 | 0.3 |
| threshold | 0.5 | 0.55 |

## Scoring (deterministic, explainable)
`persona_score = base_significance × category_weight × evidence_factor`, where `base_significance` ∈ [0,1] from signal magnitude (e.g. headcount Δ%, seniority, funding amount presence), `evidence_factor` = min(1, sources/2) × confidence. Suppression rules zero the score but keep the event (visible under "suppressed"). Each assessment row stores components + `policy_version`.

## Shared vs persona scope
Events and Watchers are shared per workspace; personas only change **assessment**. Persona-specific watcher requests become proposals with a separate credit approval.

## Single suppression path (fixes legacy dual system)
Suppression exists **only** as a `rules[].action = "suppress"` entry inside a persona (or workspace) policy version, applied in one function `apply_policy(event, policy)`. No separate suppression table.

## Legacy mapping
Single `ScoringWeightProfile` → REVAMP to persona-scoped versions. Godrej/FMCG competitor YAML → REMOVE from core; optional `examples/legacy_fmcg.yaml` labelled LEGACY EXAMPLE.
