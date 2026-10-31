"""Persona policies, deterministic scoring and governed feedback proposals.

One suppression path: `rules[].action == "suppress"` inside a persona policy
version. Global integrity rules below are code constants and cannot be changed
by any proposal.
"""
import copy
import json
import re
from pathlib import Path
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from .models import Assessment, AuditLog, Event, PolicyVersion, Proposal

CATEGORIES = ["leadership_change", "funding", "founder_move", "gtm_expansion", "product_launch", "partnership",
              "senior_hiring", "junior_hiring", "headcount_change", "news_mention"]
GLOBAL_MIN_SOURCES = 1  # immutable: every scored event must have >= 1 evidence record
WEIGHT_MIN, WEIGHT_MAX, MAX_DELTA = 0.0, 1.0, 0.5
THRESHOLD_MIN, THRESHOLD_MAX = 0.2, 0.9

PERSONAS = {
    "ci_lead": {
        "label": "Corporate Strategy / CI Lead",
        "objective": "Understand competitor positioning, market entry, capability build and partnerships to inform strategy.",
        "lens": "strategy",
        "category_weights": {"leadership_change": 0.8, "funding": 0.6, "founder_move": 0.5, "gtm_expansion": 0.8,
                             "product_launch": 1.0, "partnership": 0.9, "senior_hiring": 0.8, "junior_hiring": 0.4,
                             "headcount_change": 0.6, "news_mention": 0.5},
        "rules": [], "alert_threshold": 0.3, "min_sources": 1,
    },
    "vc_partner": {
        "label": "VC Investment Partner",
        "objective": "Track founders, funding, team growth, GTM momentum and new entrants for theses and portfolio risk.",
        "lens": "investor",
        "category_weights": {"leadership_change": 1.0, "funding": 1.0, "founder_move": 1.0, "gtm_expansion": 0.9,
                             "product_launch": 0.6, "partnership": 0.5, "senior_hiring": 0.8, "junior_hiring": 0.4,
                             "headcount_change": 0.7, "news_mention": 0.3},
        "rules": [], "alert_threshold": 0.35, "min_sources": 1,
    },
    "rd_technology": {
        "label": "R&D / Technology Lead",
        "objective": "Spot competitor capability build, technical hiring and product launches that affect our roadmap.",
        "lens": "technology",
        "category_weights": {"leadership_change": 0.6, "funding": 0.4, "founder_move": 0.3, "gtm_expansion": 0.2,
                             "product_launch": 1.0, "partnership": 0.7, "senior_hiring": 1.0, "junior_hiring": 0.6,
                             "headcount_change": 0.4, "news_mention": 0.3},
        "rules": [], "alert_threshold": 0.35, "min_sources": 1,
    },
    "sales_marketing": {
        "label": "Sales / Marketing Lead",
        "objective": "Anticipate competitor go-to-market pushes, partnerships and launches that affect deals and positioning.",
        "lens": "commercial",
        "category_weights": {"leadership_change": 0.5, "funding": 0.5, "founder_move": 0.2, "gtm_expansion": 1.0,
                             "product_launch": 0.9, "partnership": 1.0, "senior_hiring": 0.4, "junior_hiring": 0.3,
                             "headcount_change": 0.4, "news_mention": 0.6},
        "rules": [], "alert_threshold": 0.35, "min_sources": 1,
    },
    "talent_recruiting": {
        "label": "Talent / Recruiting Lead",
        "objective": "Track competitor hiring demand, team growth and leadership churn that affect our talent market.",
        "lens": "talent",
        "category_weights": {"leadership_change": 0.8, "funding": 0.3, "founder_move": 0.6, "gtm_expansion": 0.6,
                             "product_launch": 0.2, "partnership": 0.1, "senior_hiring": 1.0, "junior_hiring": 0.9,
                             "headcount_change": 1.0, "news_mention": 0.2},
        "rules": [], "alert_threshold": 0.35, "min_sources": 1,
    },
}

# Personas that get LLM brief synthesis (cost/token cap). Others use labelled templates over the same evidence.
LLM_SYNTH_PERSONAS = ("ci_lead", "vc_partner")
CUSTOM_PERSONAS_FILE = Path(__file__).resolve().parent.parent / "config" / "personas.json"


def load_custom_personas(path: Path = CUSTOM_PERSONAS_FILE) -> list[str]:
    """Optional extension point: add stakeholder presets in config/personas.json (same shape as PERSONAS).
    Entries are validated against the same bounds as proposals; invalid entries are skipped, never partially used."""
    if not path.exists():
        return []
    added = []
    for pid, body in json.loads(path.read_text(encoding="utf8")).items():
        w = body.get("category_weights", {})
        ok = (re.fullmatch(r"[a-z][a-z0-9_]{1,39}", pid) and body.get("label") and body.get("objective")
              and set(w) <= set(CATEGORIES) and all(WEIGHT_MIN <= float(v) <= WEIGHT_MAX for v in w.values())
              and THRESHOLD_MIN <= float(body.get("alert_threshold", 0.35)) <= THRESHOLD_MAX)
        if ok and pid not in PERSONAS:
            PERSONAS[pid] = {"label": body["label"], "objective": body["objective"], "lens": body.get("lens", "custom"),
                             "category_weights": {c: float(w.get(c, 0.3)) for c in CATEGORIES}, "rules": [],
                             "alert_threshold": float(body.get("alert_threshold", 0.35)),
                             "min_sources": max(GLOBAL_MIN_SOURCES, int(body.get("min_sources", 1)))}
            added.append(pid)
    return added


WHY = {  # inference templates, always labelled "inference"
    ("strategy", "product_launch"): "May signal a move into adjacent segments; check overlap with our portfolio.",
    ("strategy", "partnership"): "May extend the competitor's distribution or capability; assess channel impact.",
    ("strategy", "senior_hiring"): "Senior hiring concentration may indicate capability build in these functions.",
    ("strategy", "gtm_expansion"): "GTM hiring may precede a push into new accounts or regions.",
    ("strategy", "funding"): "New capital can fund pricing pressure or expansion against us.",
    ("strategy", "leadership_change"): "Leadership change may shift strategic direction.",
    ("strategy", "headcount_change"): "Headcount trajectory indicates investment or retrenchment.",
    ("investor", "funding"): "Funding sets valuation context and runway; relevant to thesis and competitive pressure on portfolio.",
    ("investor", "leadership_change"): "Leadership moves are a key execution-quality signal.",
    ("investor", "founder_move"): "Founder moves can precede new company formation or execution risk.",
    ("investor", "gtm_expansion"): "GTM hiring suggests commercial momentum and go-to-market maturity.",
    ("investor", "senior_hiring"): "Senior hiring indicates execution capacity being built.",
    ("investor", "headcount_change"): "Team growth rate is a momentum proxy.",
    ("investor", "product_launch"): "New product may expand addressable market.",
    ("technology", "product_launch"): "May indicate where the competitor's roadmap is heading; compare with ours.",
    ("technology", "senior_hiring"): "Senior technical hiring may signal a new capability being built.",
    ("technology", "junior_hiring"): "Volume engineering hiring may indicate scaling of an existing product.",
    ("technology", "partnership"): "Technology partnerships may close capability gaps faster than building.",
    ("commercial", "gtm_expansion"): "GTM hiring may mean more competitive pressure in our accounts or regions.",
    ("commercial", "partnership"): "New partners may open channels into our customer base.",
    ("commercial", "product_launch"): "New product may change positioning in active deals; update battlecards.",
    ("commercial", "news_mention"): "Public coverage may shape buyer perception in current deals.",
    ("talent", "senior_hiring"): "Competing demand for senior talent in these functions; expect offer/retention pressure.",
    ("talent", "junior_hiring"): "High-volume hiring competes for the same early-career talent pool.",
    ("talent", "headcount_change"): "Team growth or contraction changes who is hiring and who may be available.",
    ("talent", "leadership_change"): "Leadership churn can trigger team moves; possible hiring opportunity.",
}


ACTIONS = {  # deterministic recommended next steps (used when LLM synthesis is unavailable)
    ("strategy", "product_launch"): "Run a feature/positioning comparison against our offering and brief product leadership.",
    ("strategy", "partnership"): "Map the partner's channel overlap with our accounts; assess whether a counter-partnership is needed.",
    ("strategy", "senior_hiring"): "Review the roles posted to infer which capability is being built; add it to the competitor profile.",
    ("strategy", "gtm_expansion"): "Check which regions/segments the GTM roles target and alert the affected business unit.",
    ("strategy", "funding"): "Update the competitor's resourcing assumptions and stress-test our pricing and roadmap plans.",
    ("strategy", "leadership_change"): "Profile the new leader's background for likely strategic shifts.",
    ("strategy", "headcount_change"): "Track headcount trend quarterly; flag to strategy review if growth persists.",
    ("investor", "funding"): "Refresh valuation comps and assess competitive pressure on portfolio companies in this segment.",
    ("investor", "leadership_change"): "Assess leadership quality; schedule a reference check if relevant to a live deal.",
    ("investor", "founder_move"): "Track the founder for a potential new venture; add to sourcing pipeline.",
    ("investor", "gtm_expansion"): "Ask portfolio companies in this space whether they see this competitor in deals.",
    ("investor", "senior_hiring"): "Note execution capacity being built; revisit in next market map.",
    ("investor", "headcount_change"): "Compare growth against peers in the market map; flag outliers for a sourcing call.",
    ("technology", "product_launch"): "Have engineering assess the launch's technical approach against our roadmap.",
    ("technology", "senior_hiring"): "Review job descriptions for the technology stack and capabilities being built.",
    ("technology", "partnership"): "Evaluate whether the partner's technology closes a gap we compete on.",
    ("commercial", "gtm_expansion"): "Warn account teams in the targeted regions and refresh the competitive battlecard.",
    ("commercial", "partnership"): "Identify shared customers and prepare a positioning response for sales.",
    ("commercial", "product_launch"): "Update battlecards and objection handling before the next pipeline review.",
    ("talent", "senior_hiring"): "Review retention risk for comparable senior roles; check our compensation benchmarks.",
    ("talent", "junior_hiring"): "Adjust campus/early-career outreach timing; expect competition for the same pool.",
    ("talent", "headcount_change"): "If the competitor is shrinking, open targeted outreach to affected teams.",
    ("talent", "leadership_change"): "Watch for team moves following the leadership change; prepare outreach.",
}


def action(lens: str, category: str) -> str:
    return ACTIONS.get((lens, category), "Monitor for corroborating signals before acting.")


def why(lens: str, category: str) -> str:
    return WHY.get((lens, category), "Relevance depends on context; treat as background signal.")


# ---------------- versions ----------------

def ensure_presets(db):
    load_custom_personas()
    for pid, body in PERSONAS.items():
        if not db.scalar(select(PolicyVersion).where(PolicyVersion.persona_id == pid)):
            db.add(PolicyVersion(persona_id=pid, version=1, body=copy.deepcopy(body), is_active=True, created_by="preset"))
    db.commit()


def active(db, persona_id: str) -> PolicyVersion:
    return db.scalar(select(PolicyVersion).where(PolicyVersion.persona_id == persona_id, PolicyVersion.is_active))


# ---------------- scoring ----------------

def score_event(event: Event, policy: dict) -> dict:
    n = len(event.evidence_ids or [])
    w = float(policy["category_weights"].get(event.category, 0.3))
    min_sources = max(GLOBAL_MIN_SOURCES, int(policy.get("min_sources", 1)))
    evidence_factor = 0.0 if n < min_sources else min(1.0, 0.7 + 0.15 * n)
    suppressed_by = next((r.get("id") for r in policy.get("rules", [])
                          if r.get("action") == "suppress" and r.get("when", {}).get("category") == event.category), None)
    score = 0.0 if suppressed_by else round(event.base_significance * w * evidence_factor, 4)
    return {"score": score, "suppressed": bool(suppressed_by), "above_threshold": score >= policy["alert_threshold"],
            "components": {"base_significance": event.base_significance, "basis": event.significance_basis,
                           "category": event.category, "category_weight": w, "evidence_count": n,
                           "evidence_factor": round(evidence_factor, 3), "suppressed_by_rule": suppressed_by,
                           "threshold": policy["alert_threshold"],
                           "formula": "base_significance x category_weight x evidence_factor"}}


def assess(db, event: Event, pv: PolicyVersion):
    existing = db.scalar(select(Assessment).where(Assessment.event_id == event.id, Assessment.policy_version_id == pv.id))
    s = score_event(event, pv.body)
    if existing:
        existing.score, existing.components = s["score"], s["components"]
        existing.suppressed, existing.above_threshold = s["suppressed"], s["above_threshold"]
        return existing
    a = Assessment(event_id=event.id, persona_id=pv.persona_id, policy_version_id=pv.id, **s)
    db.add(a)
    return a


def assess_all_personas(db, events):
    for pid in PERSONAS:
        pv = active(db, pid)
        for e in events:
            assess(db, e, pv)
    db.commit()


def ranking(events, policy: dict) -> list[dict]:
    rows = [{"event_id": e.id, "title": e.title, "category": e.category, **score_event(e, policy)} for e in events]
    rows.sort(key=lambda r: (-r["score"], r["event_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


# ---------------- proposals ----------------

class Change(BaseModel):
    op: str
    category: str | None = None
    delta: float | None = None
    value: float | None = None
    action: str | None = None
    detail: str | None = None


class PolicyProposalModel(BaseModel):
    persona_id: str
    scope: str = "persona"
    changes: list[Change] = Field(default_factory=list)
    guardrail_assertions: list[str] = Field(default_factory=list)
    rationale: str = ""
    risk: str = "low"
    affected_categories: list[str] = Field(default_factory=list)

    @field_validator("risk")
    @classmethod
    def _risk(cls, v):
        return v if v in ("low", "medium", "high") else "medium"


PROPOSAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["persona_id", "scope", "changes", "guardrail_assertions", "rationale", "risk", "affected_categories"],
    "properties": {
        "persona_id": {"type": "string", "enum": list(PERSONAS)},
        "scope": {"type": "string", "enum": ["persona"]},
        "changes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["op", "category", "delta", "value", "action", "detail"],
            "properties": {
                "op": {"type": "string", "enum": ["add_rule", "remove_rule", "adjust_weight", "set_threshold",
                                                    "raise_min_sources", "lower_min_sources", "change_watch", "unsupported"]},
                "category": {"type": ["string", "null"]}, "delta": {"type": ["number", "null"]},
                "value": {"type": ["number", "null"]}, "action": {"type": ["string", "null"]},
                "detail": {"type": ["string", "null"]}}}},
        "guardrail_assertions": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"}, "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "affected_categories": {"type": "array", "items": {"type": "string"}}},
}

CAT_PATTERNS = [
    ("junior_hiring", r"junior|entry[- ]level|routine hiring|intern"),
    ("senior_hiring", r"senior hir|executive hir|senior roles"),
    ("founder_move", r"founder"),
    ("leadership_change", r"leadership|executive change|c-suite|ceo|cto"),
    ("funding", r"fund|raise|investment round|financing"),
    ("gtm_expansion", r"gtm|go[- ]to[- ]market|sales expansion|market expansion"),
    ("product_launch", r"product launch|launch"),
    ("partnership", r"partner"),
    ("headcount_change", r"headcount|team growth"),
    ("news_mention", r"news|press|media mention"),
]


def deterministic_parse(text: str, persona_id: str) -> PolicyProposalModel:
    """Keyword parser for the supported taxonomy (FEEDBACK_GOVERNANCE.md). Labelled deterministic_v1."""
    t = text.lower()
    if re.search(r"\bvc\b|investor|investment partner", t):
        persona_id = "vc_partner"
    elif re.search(r"(talent|recruiting)\s*(/\s*recruiting\s*)?(lead|team|persona|view)", t):
        persona_id = "talent_recruiting"
    elif re.search(r"(r&d|technology|engineering)\s*(/\s*technology\s*)?(lead|team|persona|view)", t):
        persona_id = "rd_technology"
    elif re.search(r"(sales|marketing)\s*(/\s*marketing\s*)?(lead|team|persona|view)", t):
        persona_id = "sales_marketing"
    elif re.search(r"strategy|\bci\b|competitive intelligence", t):
        persona_id = "ci_lead"
    changes, asserts, cats = [], [], []
    for sent in re.split(r"[.;\n]+", t):
        s = sent.strip()
        if not s:
            continue
        negated_evidence = re.search(r"(do not|don't|never|without)\s+(lower|reduc|weaken)\w*\s+(the\s+)?(evidence|source)", s)
        if negated_evidence:
            asserts.append("min_sources_unchanged")
            continue
        if re.search(r"(lower|reduc|weaken|skip|fewer)\w*\s+(the\s+)?(evidence|source|citation)", s):
            changes.append(Change(op="lower_min_sources", detail=s))
            continue
        if re.search(r"(more|stronger|additional|at least two)\s+(evidence|sources)", s):
            changes.append(Change(op="raise_min_sources", value=2, detail=s))
            continue
        if re.search(r"watch(er)?|monitor (more|daily)|real[- ]time|daily", s):
            changes.append(Change(op="change_watch", detail=s))
            continue
        found = []
        rest = s
        for cat, pat in CAT_PATTERNS:
            if re.search(pat, rest):
                found.append(cat)
                rest = re.sub(pat, " ", rest)
        if not found:
            continue
        if re.search(r"suppress|mute|ignore|hide|stop|exclude|filter out", s):
            changes += [Change(op="add_rule", category=c, action="suppress") for c in found]
        elif re.search(r"less|reduce|deprioriti|lower|downweight", s):
            changes += [Change(op="adjust_weight", category=c, delta=-0.2) for c in found]
        elif re.search(r"prioriti|more|boost|focus|emphasi|increase|care about|highlight", s):
            changes += [Change(op="adjust_weight", category=c, delta=0.2) for c in found]
        else:
            continue
        cats += found
    if not changes:
        changes.append(Change(op="unsupported", detail="no supported instruction recognised"))
    return PolicyProposalModel(persona_id=persona_id, changes=changes, guardrail_assertions=sorted(set(asserts)),
                               rationale=f"Parsed from feedback: {text[:300]}",
                               risk="medium" if any(c.op == "add_rule" for c in changes) else "low",
                               affected_categories=sorted(set(cats)))


def apply_changes(body: dict, prop: PolicyProposalModel) -> dict:
    new = copy.deepcopy(body)
    for i, c in enumerate(prop.changes):
        if c.op == "add_rule":
            if not any(r.get("when", {}).get("category") == c.category for r in new["rules"]):
                new["rules"].append({"id": f"r{len(new['rules']) + 1}", "when": {"category": c.category}, "action": "suppress"})
        elif c.op == "remove_rule":
            new["rules"] = [r for r in new["rules"] if r.get("when", {}).get("category") != c.category]
        elif c.op == "adjust_weight":
            w = new["category_weights"].get(c.category, 0.3) + float(c.delta or 0)
            new["category_weights"][c.category] = round(min(WEIGHT_MAX, max(WEIGHT_MIN, w)), 3)
        elif c.op == "set_threshold":
            new["alert_threshold"] = float(c.value)
        elif c.op == "raise_min_sources":
            new["min_sources"] = max(new.get("min_sources", 1), int(c.value or 2))
    return new


def validate(prop: PolicyProposalModel, requested_persona: str, body: dict) -> dict:
    errors, warnings = [], []
    credit = False
    if prop.persona_id not in PERSONAS:
        errors.append(f"unknown persona {prop.persona_id}")
    if prop.persona_id != requested_persona:
        warnings.append(f"feedback text targets {prop.persona_id}; submitted under {requested_persona}. Scoped to {prop.persona_id}.")
    if prop.scope != "persona":
        errors.append("only persona scope is supported")
    for c in prop.changes:
        if c.op in ("add_rule", "remove_rule", "adjust_weight") and c.category not in CATEGORIES:
            errors.append(f"{c.op}: unknown category {c.category!r}")
        if c.op == "add_rule" and c.action != "suppress":
            errors.append("add_rule: only action 'suppress' is supported")
        if c.op == "adjust_weight":
            if c.delta is None or abs(c.delta) > MAX_DELTA:
                errors.append(f"adjust_weight {c.category}: |delta| must be <= {MAX_DELTA}")
            else:
                w = body["category_weights"].get(c.category, 0.3) + c.delta
                if w > WEIGHT_MAX or w < WEIGHT_MIN:
                    warnings.append(f"{c.category} weight clamped to [{WEIGHT_MIN}, {WEIGHT_MAX}]")
        if c.op == "set_threshold" and (c.value is None or not THRESHOLD_MIN <= c.value <= THRESHOLD_MAX):
            errors.append(f"set_threshold must be within [{THRESHOLD_MIN}, {THRESHOLD_MAX}]")
        if c.op == "lower_min_sources":
            errors.append("Guardrail: evidence requirements cannot be lowered by persona feedback (global integrity rule)")
        if c.op == "change_watch":
            credit = True
            warnings.append("Watcher scope/cadence change: requires separate credit approval; not executed in MVP")
        if c.op == "unsupported":
            errors.append("No supported policy instruction found (supported: suppress, prioritise/deprioritise a "
                          "signal category, threshold, require more evidence)")
    new = apply_changes(body, prop) if not errors else body
    if new.get("min_sources", 1) < max(GLOBAL_MIN_SOURCES, body.get("min_sources", 1)):
        errors.append("Guardrail: min_sources would decrease")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "requires_credit_approval": credit,
            "guardrails": {"global_min_sources": GLOBAL_MIN_SOURCES, "provenance_required": True,
                           "fact_inference_labels": True}}


def diff(old: dict, new: dict) -> dict:
    out = {"weights": [], "rules_added": [], "rules_removed": [], "other": []}
    for k in sorted(set(old["category_weights"]) | set(new["category_weights"])):
        a, b = old["category_weights"].get(k), new["category_weights"].get(k)
        if a != b:
            out["weights"].append({"category": k, "before": a, "after": b})
    oc = {r["when"]["category"] for r in old["rules"]}
    nc = {r["when"]["category"] for r in new["rules"]}
    out["rules_added"] = [f"suppress {c}" for c in sorted(nc - oc)]
    out["rules_removed"] = [f"suppress {c}" for c in sorted(oc - nc)]
    for k in ("alert_threshold", "min_sources"):
        if old.get(k) != new.get(k):
            out["other"].append({"field": k, "before": old.get(k), "after": new.get(k)})
    return out


def replay(events, old: dict, new: dict) -> dict:
    before = {r["event_id"]: r for r in ranking(events, old)}
    after = {r["event_id"]: r for r in ranking(events, new)}
    rows = []
    for eid, b in before.items():
        a = after[eid]
        if a["rank"] != b["rank"] or a["score"] != b["score"] or a["suppressed"] != b["suppressed"]:
            rows.append({"event_id": eid, "title": b["title"][:110], "category": b["category"],
                         "rank_before": b["rank"], "rank_after": a["rank"], "score_before": b["score"],
                         "score_after": a["score"], "suppressed_after": a["suppressed"]})
    rows.sort(key=lambda r: r["rank_after"])
    return {"events_replayed": len(events), "changed": rows,
            "alerts_before": sum(r["above_threshold"] for r in before.values()),
            "alerts_after": sum(r["above_threshold"] for r in after.values())}


def create_proposal(db, persona_id: str, text: str, prop: PolicyProposalModel, parser: str) -> Proposal:
    target = prop.persona_id if prop.persona_id in PERSONAS else persona_id
    pv = active(db, target)
    v = validate(prop, persona_id, pv.body)
    new_body = apply_changes(pv.body, prop) if v["ok"] else pv.body
    events = list(db.scalars(select(Event)))
    p = Proposal(persona_id=target, feedback_text=text, body=prop.model_dump(), parser=parser,
                 state="pending_review" if v["ok"] else "invalid", validation=v, diff=diff(pv.body, new_body),
                 replay=replay(events, pv.body, new_body) if v["ok"] else {}, base_version_id=pv.id, risk=prop.risk,
                 requires_credit_approval=v["requires_credit_approval"])
    db.add(p)
    db.flush()
    db.add(AuditLog(actor="system", action="proposal_created", object_type="proposal", object_id=p.id,
                    detail={"state": p.state, "parser": parser, "persona_id": target}))
    db.commit()
    return p


class GovernanceError(Exception):
    pass


def approve(db, proposal_id: int, reviewer: str, confirm_high_risk: bool = False) -> PolicyVersion:
    p = db.get(Proposal, proposal_id)
    if not p:
        raise GovernanceError("proposal not found")
    if p.state != "pending_review":
        raise GovernanceError(f"proposal is {p.state}; only pending_review can be approved")
    if not reviewer.strip():
        raise GovernanceError("reviewer name required")
    if p.risk == "high" and not confirm_high_risk:
        raise GovernanceError("high-risk proposal requires explicit confirm_high_risk")
    cur = active(db, p.persona_id)
    if cur.id != p.base_version_id:
        raise GovernanceError("policy changed since proposal was created; re-submit feedback")
    prop = PolicyProposalModel(**p.body)
    v = validate(prop, p.persona_id, cur.body)  # re-validate at approval time
    if not v["ok"]:
        raise GovernanceError("; ".join(v["errors"]))
    new_body = apply_changes(cur.body, prop)
    cur.is_active = False
    nv = PolicyVersion(persona_id=p.persona_id, version=cur.version + 1, body=new_body, is_active=True,
                       created_by=reviewer, source_proposal_id=p.id)
    db.add(nv)
    p.state, p.reviewer, p.decided_at = "approved", reviewer, datetime.now(timezone.utc)
    db.flush()
    db.add(AuditLog(actor=reviewer, action="policy_version_activated", object_type="policy_version", object_id=nv.id,
                    detail={"persona_id": p.persona_id, "from_version": cur.version, "to_version": nv.version,
                            "proposal_id": p.id, "diff": p.diff}))
    for e in db.scalars(select(Event)):  # re-score this persona only
        assess(db, e, nv)
    db.commit()
    return nv


def reject(db, proposal_id: int, reviewer: str):
    p = db.get(Proposal, proposal_id)
    if not p or p.state != "pending_review":
        raise GovernanceError("only pending_review proposals can be rejected")
    p.state, p.reviewer, p.decided_at = "rejected", reviewer or "reviewer", datetime.now(timezone.utc)
    db.add(AuditLog(actor=p.reviewer, action="proposal_rejected", object_type="proposal", object_id=p.id))
    db.commit()


def rollback(db, persona_id: str, to_version: int, reviewer: str) -> PolicyVersion:
    target = db.scalar(select(PolicyVersion).where(PolicyVersion.persona_id == persona_id, PolicyVersion.version == to_version))
    cur = active(db, persona_id)
    if not target or not reviewer.strip():
        raise GovernanceError("unknown version or missing reviewer")
    cur.is_active = False
    nv = PolicyVersion(persona_id=persona_id, version=cur.version + 1, body=copy.deepcopy(target.body), is_active=True,
                       created_by=reviewer)
    db.add(nv)
    db.flush()
    db.add(AuditLog(actor=reviewer, action="policy_rollback", object_type="policy_version", object_id=nv.id,
                    detail={"persona_id": persona_id, "restored_version": to_version, "new_version": nv.version}))
    for e in db.scalars(select(Event)):
        assess(db, e, nv)
    db.commit()
    return nv
