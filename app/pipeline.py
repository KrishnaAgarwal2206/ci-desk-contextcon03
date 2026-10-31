"""Fresh request -> Crustdata evidence -> events -> persona briefs -> shared Watcher.

Runs in-process (no queue/worker). Every stage writes a run_step row; every API
call writes an api_call row (see crustdata.py).
"""
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field
from sqlalchemy import select

from . import policy as pol
from .config import settings
from .crustdata import CreditsExhausted, CrustdataClient, CrustdataError, Forbidden, NotConfigured
from .llm import LLMProvider
from .models import Brief, Claim, Entity, Event, Evidence, Request, RunStep, Watch

# ---------------- planning ----------------


class ResearchPlan(BaseModel):
    market: str = ""
    companies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    geography: str = ""
    signals: list[str] = Field(default_factory=list)
    time_window: str = ""
    people_roles: list[str] = Field(default_factory=list)
    personas: list[str] = Field(default_factory=lambda: ["ci_lead", "vc_partner"])


PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["market", "companies", "domains", "geography", "signals", "time_window", "people_roles", "personas"],
    "properties": {
        "market": {"type": "string"}, "companies": {"type": "array", "items": {"type": "string"}},
        "domains": {"type": "array", "items": {"type": "string"}}, "geography": {"type": "string"},
        "signals": {"type": "array", "items": {"type": "string", "enum": pol.CATEGORIES}},
        "time_window": {"type": "string"}, "people_roles": {"type": "array", "items": {"type": "string"}},
        "personas": {"type": "array", "items": {"type": "string", "enum": list(pol.PERSONAS)}}},
}

PLAN_SYSTEM = ("You convert a competitive-intelligence research brief into a structured plan. Extract ONLY what the "
               "user wrote: company names exactly as written (no guessing of other companies), any web domains, the "
               "market/category, geography, signal categories of interest, time window and people roles. Never invent "
               "identifiers. If no companies are named, leave companies empty and describe the market.")

DOMAIN_RE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|io|ai|co|in|net|org|app|dev|tech|xyz|so))\b", re.I)
STOP = {"the", "and", "a", "an", "of", "for", "on", "in", "to", "me", "us", "our", "we", "track", "build", "show",
        "what", "which", "who", "tell", "find", "brief", "intelligence", "ongoing", "competitors", "competitor",
        "market", "companies", "company", "these", "those", "vc", "partner", "corporate", "strategy", "investment"}


def deterministic_plan(text: str) -> ResearchPlan:
    domains = sorted({d.lower() for d in DOMAIN_RE.findall(text)})
    t = DOMAIN_RE.sub(" ", text)
    companies: list[str] = []
    m = re.search(r"(?:competitors?|companies|players|including|such as|like|vs\.?|versus|on)\s*[:\-]?\s*(.+?)(?:\.|\n|$)",
                  t, re.I)
    seg = m.group(1) if m else ""
    for part in re.split(r",|\band\b|/|;|\bvs\.?\b", seg):
        name = part.strip(" .\"'()")
        words = name.split()
        if 0 < len(words) <= 4 and words[0][:1].isupper() and words[0].lower() not in STOP:
            companies.append(name)
    if not companies:  # fall back to capitalised tokens that are not sentence starters/stopwords
        for tok in re.findall(r"\b([A-Z][a-zA-Z0-9&]+(?:\s[A-Z][a-zA-Z0-9&]+)?)\b", t):
            if tok.lower() not in STOP and tok.split()[0].lower() not in STOP and tok not in companies:
                companies.append(tok)
        companies = companies[:settings.max_companies]
    mk = re.search(r"(?:the|on|in)\s+([a-zA-Z0-9 \-/&]{3,60}?)\s+(?:market|sector|space|industry|landscape)", text, re.I)
    signals = [c for c, p in pol.CAT_PATTERNS if re.search(p, text.lower())]
    geo = re.search(r"\b(India|United States|US|USA|Europe|UK|Germany|Singapore|Southeast Asia|global)\b", text, re.I)
    return ResearchPlan(market=mk.group(1).strip() if mk else "", companies=companies[:settings.max_companies],
                        domains=domains[:settings.max_companies], geography=geo.group(1) if geo else "",
                        signals=signals or ["funding", "leadership_change", "senior_hiring", "headcount_change"])


def plan(db, req: Request, llm: LLMProvider) -> ResearchPlan:
    data, mode = llm.complete_json("plan", PLAN_SYSTEM, req.brief_text, PLAN_SCHEMA,
                                   validator=lambda d: ResearchPlan(**d))
    if data is None:
        data = deterministic_plan(req.brief_text)
        mode = "deterministic_v1 — " + mode.replace("deterministic ", "")
    data.companies = data.companies[:settings.max_companies]
    req.plan, req.planner_mode = data.model_dump(), mode
    db.commit()
    return data


# ---------------- resolution ----------------

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def classify_matches(query: str, matches: list[dict]) -> dict:
    """Deterministic identity decision. Never guesses between equally-likely candidates."""
    cands = []
    for m in matches or []:
        cd = m.get("company_data") or {}
        bi = cd.get("basic_info") or {}
        cid = cd.get("crustdata_company_id") or bi.get("crustdata_company_id")
        if cid is None:
            continue
        cands.append({"crustdata_company_id": cid, "name": bi.get("name") or "", "domain": bi.get("primary_domain") or "",
                      "confidence": float(m.get("confidence_score") or 0), "employee_count_range": bi.get("employee_count_range"),
                      "website": bi.get("website") or ""})
    if not cands:
        return {"resolution": "unresolved", "chosen": None, "alternatives": [], "via": "identify: no match"}
    cands.sort(key=lambda c: -c["confidence"])
    top = cands[0]
    close = [c for c in cands if c["confidence"] >= top["confidence"] - 0.05 and c["crustdata_company_id"] != top["crustdata_company_id"]]
    if not close:
        if top["confidence"] < 0.5:
            return {"resolution": "ambiguous", "chosen": None, "alternatives": cands[:5], "via": "identify: low confidence"}
        return {"resolution": "resolved", "chosen": top, "alternatives": cands[1:5], "via": "identify: single top match"}
    q = _norm(query)
    tied = [top] + close
    exact = [c for c in tied if _norm(c["domain"].split(".")[0]) == q]
    if len(exact) == 1:
        rest = [c for c in cands if c is not exact[0]]
        return {"resolution": "resolved", "chosen": exact[0], "alternatives": rest[:5],
                "via": "identify: tie broken by exact domain-name match"}
    return {"resolution": "ambiguous", "chosen": None, "alternatives": cands[:5],
            "via": f"identify: {len(tied)} equally ranked matches — not guessed"}


def resolve(db, req: Request, cd: CrustdataClient, p: ResearchPlan) -> list[Entity]:
    out = []
    queries = [("domain", d) for d in p.domains] + [("name", n) for n in p.companies
                                                     if not any(_norm(n) in _norm(d) for d in p.domains)]
    for kind, q in queries[:settings.max_companies]:
        try:
            res = cd.identify(domains=[q]) if kind == "domain" else cd.identify(names=[q])
            matches = res[0].get("matches", []) if isinstance(res, list) and res else []
            dec = classify_matches(q, matches)
        except (NotConfigured, CreditsExhausted):
            raise
        except CrustdataError as e:
            dec = {"resolution": "unresolved", "chosen": None, "alternatives": [], "via": f"identify failed: {e}"}
        ch = dec["chosen"] or {}
        ent = Entity(request_id=req.id, query=q, crustdata_id=ch.get("crustdata_company_id"), name=ch.get("name", ""),
                     domain=ch.get("domain", ""), resolution=dec["resolution"], confidence=ch.get("confidence"),
                     alternatives=dec["alternatives"], resolved_via=dec["via"])
        db.add(ent)
        out.append(ent)
    if not queries and p.market:  # market-level discovery
        try:
            res = cd.company_search(p.market + (f" {p.geography}" if p.geography else ""), limit=5)
            for c in (res or {}).get("companies", [])[:5]:
                bi = c.get("basic_info") or {}
                ent = Entity(request_id=req.id, query=f"market: {p.market}", crustdata_id=c.get("crustdata_company_id"),
                             name=bi.get("name", ""), domain=bi.get("primary_domain", ""), resolution="resolved",
                             confidence=None, resolved_via="company_search (ranked hybrid)", profile=c)
                db.add(ent)
                out.append(ent)
        except (NotConfigured, CreditsExhausted):
            raise
        except CrustdataError as e:
            req.notes = req.notes + [f"Company Search failed: {e}"]
    # de-duplicate the same canonical company reached by two queries
    seen = set()
    for e in out:
        if e.crustdata_id and e.resolution == "resolved":
            if e.crustdata_id in seen:
                e.resolution, e.resolved_via = "duplicate", e.resolved_via + " (same canonical ID as another input)"
            seen.add(e.crustdata_id)
    db.commit()
    return out


# ---------------- evidence + events ----------------

def fp(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def add_evidence(db, req, ent, source_type, url, ref, excerpt, ts="", api_call_id=None) -> Evidence:
    ev = Evidence(request_id=req.id if req else None, entity_id=ent.id if ent else None,
                  crustdata_company_id=ent.crustdata_id if ent else None, source_type=source_type, source_url=url or "",
                  record_ref=ref, excerpt=(excerpt or "")[:1000], source_ts=str(ts or "")[:40], api_call_id=api_call_id)
    db.add(ev)
    db.flush()
    return ev


def upsert_event(db, req, company_id, company_name, category, title, base, basis, fingerprint, evidence: list[Evidence],
                 facts: list[str], origin="initial_research") -> Event:
    """Store one event per underlying development; repeated sightings merge evidence (dedupe)."""
    ev = db.scalar(select(Event).where(Event.fingerprint == fingerprint))
    ids = [e.id for e in evidence]
    if ev:
        ev.evidence_ids = sorted(set(ev.evidence_ids) | set(ids))
        ev.last_seen_at = datetime.now(timezone.utc)
        db.add(Claim(event_id=ev.id, text=f"Corroborated by {', '.join(e.source_type for e in evidence)}",
                     kind="fact", evidence_ids=ids))
        return ev
    ev = Event(fingerprint=fingerprint, request_id=req.id if req else None, category=category,
               crustdata_company_id=company_id, company_name=company_name, title=title, base_significance=round(base, 3),
               significance_basis=basis, evidence_ids=ids, origin=origin)
    db.add(ev)
    db.flush()
    for f in facts:
        db.add(Claim(event_id=ev.id, text=f, kind="fact", evidence_ids=ids))
    return ev


NEWS_CATS = [("funding", r"rais|funding|series [a-h]|seed round|investment|valuation"),
             ("leadership_change", r"appoint|names .* (ceo|cto|cfo|chief)|joins as|steps down|resign|new (ceo|cto|cfo)|hires .* (chief|head)"),
             ("founder_move", r"founder (leaves|exits|departs|steps)|co-?founder"),
             ("product_launch", r"launch|unveil|introduc|release|rolls out"),
             ("partnership", r"partner|collaborat|alliance|tie[- ]up|integrat"),
             ("gtm_expansion", r"expan|enters|opens .* office|new market|international")]


def news_category(title: str) -> str:
    t = (title or "").lower()
    for c, p in NEWS_CATS:
        if re.search(p, t):
            return c
    return "news_mention"


def recency(date_str: str) -> float:
    try:
        d = datetime.fromisoformat(str(date_str)[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.5
    days = (datetime.now(timezone.utc) - d).days
    return 1.0 if days <= 90 else 0.8 if days <= 180 else 0.6 if days <= 365 else 0.35


def _g(d: dict, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return None


NEWS_MIN_CONF = 0.93
SENIOR = re.compile(r"\b(head|director|vp|vice president|chief|principal|staff|lead|senior|sr\.?|manager)\b", re.I)
GTM = re.compile(r"\b(sales|account executive|business development|bdr|sdr|marketing|partnerships|customer success|growth|revenue)\b", re.I)


def events_from_enrich(db, req, ent: Entity, cdata: dict, call_id):
    cid, name = ent.crustdata_id, ent.name or ent.query
    ref = f"POST /company/enrich crustdata_company_id={cid}"
    hc = cdata.get("headcount") or {}
    total = hc.get("total")
    gp = hc.get("growth_percent") or {}
    g6 = _g(gp, "six_months", "6m")
    g12 = _g(gp, "yoy", "12m")
    if total is not None:
        excerpt = f"headcount.total={total}; growth_percent.6m={g6}; growth_percent.12m={g12}"
        e = add_evidence(db, req, ent, "crustdata_enrich", "", ref + " field=headcount", excerpt, cdata.get("updated_at"), call_id)
        g = float(g6) if g6 is not None else (float(g12) if g12 is not None else 0.0)
        upsert_event(db, req, cid, name, "headcount_change",
                     f"{name}: headcount {total:,} ({g:+.1f}% over {'6 months' if g6 is not None else '12 months'})",
                     min(1.0, 0.25 + abs(g) / 30), f"|growth| {abs(g):.1f}% → 0.25 + |g|/30 (cap 1.0)",
                     fp("headcount", cid, total, g6), [e],
                     [f"Headcount is {total:,} (Crustdata headcount.total)."] +
                     ([f"6-month headcount growth is {float(g6):+.1f}%."] if g6 is not None else []))
    fu = cdata.get("funding") or {}
    if fu.get("last_fundraise_date") or fu.get("total_investment_usd"):
        amt = fu.get("last_round_amount_usd")
        excerpt = (f"last_round_type={fu.get('last_round_type')}; last_round_amount_usd={amt}; "
                   f"last_fundraise_date={fu.get('last_fundraise_date')}; total_investment_usd={fu.get('total_investment_usd')}")
        e = add_evidence(db, req, ent, "crustdata_enrich", "", ref + " field=funding", excerpt, fu.get("last_fundraise_date"), call_id)
        r = recency(fu.get("last_fundraise_date") or "")
        title = (f"{name}: last round {fu.get('last_round_type') or 'unknown type'}"
                 + (f" of ${amt / 1e6:,.1f}M" if amt else "") + f" on {fu.get('last_fundraise_date') or 'unknown date'}")
        upsert_event(db, req, cid, name, "funding", title, 0.9 * r + 0.1, f"recency factor {r} (date {fu.get('last_fundraise_date')})",
                     fp("funding", cid, fu.get("last_fundraise_date"), amt), [e],
                     [f"Last funding round: {fu.get('last_round_type')} on {fu.get('last_fundraise_date')}"
                      + (f", ${amt:,.0f}." if amt else "; amount not reported."),
                      f"Total investment reported: {fu.get('total_investment_usd') or 'not reported'}."])
    news = cdata.get("news")
    items = news if isinstance(news, list) else (news or {}).get("articles", []) if isinstance(news, dict) else []
    # Crustdata attaches an entity-match confidence to news; in live testing off-entity articles
    # (e.g. "GMC Sierra" trucks for Sierra AI) scored 0.85-0.90 and on-entity ones 0.95.
    kept = [a for a in items if a.get("confidence_score") is None or float(a["confidence_score"]) >= NEWS_MIN_CONF]
    if len(kept) < len(items):
        req.notes = req.notes + [f"{name}: {len(items) - len(kept)} enrich news items dropped (entity-match confidence < {NEWS_MIN_CONF})"]
    for a in kept[:5]:
        url, title = a.get("article_url"), a.get("article_title") or ""
        if not url:
            continue
        e = add_evidence(db, req, ent, "crustdata_enrich", url, ref + " field=news", title + f" — {a.get('article_publisher_name') or ''}",
                         a.get("article_publish_date"), call_id)
        cat = news_category(title)
        r = recency(a.get("article_publish_date") or "")
        upsert_event(db, req, cid, name, cat, f"{name}: {title}", 0.7 * r, f"news item, recency factor {r}",
                     fp("url", url), [e], [f"Reported: \"{title}\" ({a.get('article_publisher_name') or 'publisher n/a'}, "
                                          f"{str(a.get('article_publish_date') or 'date n/a')[:10]})."])
    ppl = cdata.get("people") or {}
    for group in ("founders", "cxos"):
        for person in (ppl.get(group) or [])[:4]:
            if isinstance(person, dict):
                nm = person.get("name") or _g(person.get("basic_profile") or {}, "name")
                tt = person.get("title") or _g(person.get("basic_profile") or {}, "current_title")
                if nm:
                    add_evidence(db, req, ent, "crustdata_enrich", person.get("profile_url") or "",
                                 ref + f" field=people.{group}", f"{nm} — {tt or group}", "", call_id)


def events_from_jobs(db, req, ent: Entity, listings: list[dict], call_id):
    cid, name = ent.crustdata_id, ent.name or ent.query
    groups = {"senior_hiring": [], "junior_hiring": [], "gtm_expansion": []}
    for j in listings:
        jd = j.get("job_details") or {}
        title, url = jd.get("title") or "", jd.get("url") or ""
        e = add_evidence(db, req, ent, "job_search", url, f"POST /job/search company.basic_info.company_id={cid}",
                         f"{title} ({(j.get('location') or {}).get('country') or 'location n/a'})",
                         (j.get("metadata") or {}).get("date_added"), call_id)
        if GTM.search(title):
            groups["gtm_expansion"].append((e, title))
        groups["senior_hiring" if SENIOR.search(title) else "junior_hiring"].append((e, title))
    for cat, items in groups.items():
        if not items:
            continue
        label = {"senior_hiring": "senior roles", "junior_hiring": "non-senior roles", "gtm_expansion": "GTM roles"}[cat]
        sample = "; ".join(t for _, t in items[:3])
        n = len(items)
        upsert_event(db, req, cid, name, cat, f"{name}: {n} recent {label} posted (e.g. {sample[:120]})",
                     min(1.0, 0.3 + 0.07 * n), f"{n} postings → 0.3 + 0.07n (cap 1.0)",
                     fp("jobs", cat, cid, *sorted(e.source_url for e, _ in items)), [e for e, _ in items],
                     [f"{n} of the {len(listings)} most recent indexed postings are {label}.", f"Examples: {sample}."])


def events_from_web(db, req, ent: Entity, results: list[dict], call_id):
    cid, name = ent.crustdata_id, ent.name or ent.query
    for r in results[:settings.max_web_results_per_company]:
        url, title = r.get("url"), r.get("title") or ""
        if not url:
            continue
        e = add_evidence(db, req, ent, "web_search", url, f"POST /web/search/live q=\"{name}\"",
                         f"{title} — {r.get('snippet') or ''}", r.get("date") or "", call_id)
        if _norm(name.split()[0]) not in _norm(title + (r.get("snippet") or "")):
            continue  # keep as evidence only; not clearly about this company
        cat = news_category(title)
        upsert_event(db, req, cid, name, cat, f"{name}: {title}", 0.55, "web/news result (no publish date) 0.55",
                     fp("url", url), [e], [f"Public source reports: \"{title}\"."])


def collect_evidence(db, req: Request, cd: CrustdataClient, ents: list[Entity]):
    resolved = [e for e in ents if e.resolution == "resolved" and e.crustdata_id][:settings.max_companies]
    if not resolved:
        return
    by_id = {e.crustdata_id: e for e in resolved}
    # "people" is omitted: it returned ~6.8 MB per company in live testing; Person Search covers leadership.
    fields = ["basic_info", "headcount", "funding", "news"]
    res = None
    for attempt_fields in (fields, ["basic_info", "headcount", "funding"]):
        try:
            res = cd.enrich(list(by_id), attempt_fields)
            break
        except Forbidden as e:
            req.notes = req.notes + [f"Enrich fields {attempt_fields} denied ({e}); retrying with fewer fields"]
        except (NotConfigured, CreditsExhausted):
            raise
        except CrustdataError as e:
            req.notes = req.notes + [f"Company Enrich failed: {e}"]
            break
    call_id = _last_call_id(db, req.id)
    for item in res or []:
        for m in (item.get("matches") or [])[:1]:
            c = m.get("company_data") or {}
            ent = by_id.get(c.get("crustdata_company_id"))
            if ent:
                ent.profile = {k: c.get(k) for k in ("basic_info", "headcount", "funding") if c.get(k)}
                events_from_enrich(db, req, ent, c, call_id)
    db.commit()
    for ent in resolved:
        for label, fn in (("jobs", lambda: cd.jobs(ent.crustdata_id, settings.max_jobs_per_company)),
                          ("people", lambda: cd.people(ent.crustdata_id, settings.max_people_per_company)),
                          ("web", lambda: cd.web_search(f"{ent.name or ent.query} company news"))):
            try:
                data = fn() or {}
            except (NotConfigured, CreditsExhausted):
                raise
            except CrustdataError as e:
                req.notes = req.notes + [f"{label} for {ent.name}: {e}"]
                continue
            cid = _last_call_id(db, req.id)
            if label == "jobs":
                events_from_jobs(db, req, ent, data.get("job_listings") or [], cid)
            elif label == "people":
                for pr in (data.get("profiles") or [])[:settings.max_people_per_company]:
                    cur = ((pr.get("experience") or {}).get("employment_details") or {}).get("current") or []
                    title = cur[0].get("title") if cur and isinstance(cur[0], dict) else ""
                    add_evidence(db, req, ent, "person_search", "",
                                 f"POST /person/search crustdata_person_id={pr.get('crustdata_person_id')}",
                                 f"{(pr.get('basic_profile') or {}).get('name')} — {title}", "", cid)
            else:
                events_from_web(db, req, ent, data.get("results") or [], cid)
            db.commit()


def _last_call_id(db, request_id):
    from .models import ApiCall
    return db.scalar(select(ApiCall.id).where(ApiCall.request_id == request_id).order_by(ApiCall.id.desc()))


# ---------------- briefs ----------------

INSIGHT_ITEM = {
    "type": "object", "additionalProperties": False,
    "required": ["headline", "insight", "implication", "recommended_action", "confidence", "event_ids", "evidence_ids"],
    "properties": {"headline": {"type": "string"}, "insight": {"type": "string"}, "implication": {"type": "string"},
                   "recommended_action": {"type": "string"},
                   "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                   "event_ids": {"type": "array", "items": {"type": "integer"}},
                   "evidence_ids": {"type": "array", "items": {"type": "integer"}}}}


def brief_schema(pids) -> dict:
    # One array of stakeholder objects (a per-persona object schema compiled too large for structured output).
    return {"type": "object", "additionalProperties": False, "required": ["stakeholders"],
            "properties": {"stakeholders": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["persona_id", "executive_summary", "insights", "watch_next"],
                "properties": {"persona_id": {"type": "string", "enum": list(pids)},
                               "executive_summary": {"type": "string"},
                               "insights": {"type": "array", "items": INSIGHT_ITEM},
                               "watch_next": {"type": "array", "items": {"type": "string"}}}}}}}


BRIEF_SYSTEM = (
    "You are a senior competitive-intelligence analyst writing decision briefs for several stakeholders from ONE shared "
    "evidence base. Use ONLY the supplied events and their facts. Return one entry in 'stakeholders' for every "
    "stakeholder listed (persona_id = its key). For each stakeholder:\n"
    "- executive_summary: 3-4 sentences in plain business English: what is happening across these competitors and what "
    "it means for this stakeholder's objective.\n"
    "- insights: 3-4 insights. Connect related events where the facts support it (e.g. funding plus hiring at the same "
    "company), rather than restating one change. Each has a short headline; 'insight' (2-3 sentences explaining the "
    "pattern, quoting concrete numbers from the facts); 'implication' for this stakeholder (1-2 sentences); "
    "'recommended_action' (one concrete, specific next step this stakeholder could take this week); confidence "
    "(high = multiple corroborating facts, medium = one solid fact, low = thin or indirect); event_ids and evidence_ids "
    "taken ONLY from the events you used.\n"
    "- watch_next: 2-3 specific signals to monitor next.\n"
    "Rules: never invent facts, numbers, people or companies; interpretations are hypotheses ('suggests', 'may'); "
    "different stakeholders must get genuinely different angles on the same events; do not rescore or rerank.")


def _event_payload(e: Event, claims) -> dict:
    return {"event_id": e.id, "company": e.company_name, "category": e.category, "title": e.title[:160],
            "facts": claims.get(e.id, [])[:3], "evidence_ids": e.evidence_ids[:5]}


def validate_insights(raw: list, by_id: dict) -> list:
    """Keep only insights whose event_ids exist and whose evidence_ids belong to those events."""
    out = []
    for ins in raw or []:
        eids = [i for i in ins.get("event_ids") or [] if i in by_id]
        allowed = set().union(*[set(by_id[i].evidence_ids) for i in eids]) if eids else set()
        cited = [i for i in ins.get("evidence_ids") or [] if i in allowed]
        if not eids or not cited or not ins.get("insight"):
            continue
        out.append({**ins, "event_ids": eids, "evidence_ids": cited,
                    "companies": sorted({by_id[i].company_name for i in eids})})
    return out


def deterministic_insights(ranked, by_id, claims, lens) -> list:
    out = []
    for r in [x for x in ranked if x["above_threshold"]][:4] or ranked[:3]:
        e = by_id[r["event_id"]]
        out.append({"headline": e.title, "insight": " ".join(claims.get(e.id, [])[:2]),
                    "implication": pol.why(lens, e.category), "recommended_action": pol.action(lens, e.category),
                    "confidence": "medium" if len(e.evidence_ids) > 1 else "low", "event_ids": [e.id],
                    "evidence_ids": e.evidence_ids[:4], "companies": [e.company_name]})
    return out


def build_briefs(db, req: Request, llm: LLMProvider, ents: list[Entity]):
    events = list(db.scalars(select(Event).where(Event.request_id == req.id)))
    per = {}
    for pid in pol.PERSONAS:
        pv = pol.active(db, pid)
        ranked = [r for r in pol.ranking(events, pv.body) if not r["suppressed"]][:8]
        per[pid] = (pv, ranked)
    by_id = {e.id: e for e in events}
    claims = {}
    for c in db.scalars(select(Claim).where(Claim.event_id.in_(list(by_id) or [0]))):
        claims.setdefault(c.event_id, []).append(c.text)
    llm_out, mode = None, "deterministic (no events)"
    if events:
        shared = sorted({r["event_id"] for _, ranked in per.values() for r in ranked[:5]})[:14]
        payload = {"events": [_event_payload(by_id[i], claims) for i in shared],
                   "stakeholders": {pid: {"label": pol.PERSONAS[pid]["label"], "objective": pv.body["objective"],
                                          "priority_order": [{"event_id": r["event_id"], "score": r["score"]}
                                                             for r in ranked[:5]]}
                                    for pid, (pv, ranked) in per.items()}}
        llm_out, mode = llm.complete_json("synthesis", BRIEF_SYSTEM, json.dumps(payload), brief_schema(list(per)),
                                          max_tokens=settings.llm_synth_max_output_tokens)
        if llm_out:
            llm_out = {x.get("persona_id"): x for x in llm_out.get("stakeholders", []) if isinstance(x, dict)}
    unknowns = [f"'{e.query}' — {e.resolution}: {e.resolved_via}" for e in ents if e.resolution != "resolved"]
    unknowns += [n for n in req.notes]
    for pid, (pv, ranked) in per.items():
        lens = pv.body["lens"]
        llm_p = (llm_out or {}).get(pid) or {}
        insights = validate_insights(llm_p.get("insights"), by_id)
        rich = bool(insights and llm_p.get("executive_summary"))
        findings = []
        for r in ranked:
            e = by_id[r["event_id"]]
            findings.append({"event_id": e.id, "company": e.company_name, "category": e.category, "title": e.title,
                             "score": r["score"], "above_threshold": r["above_threshold"],
                             "facts": claims.get(e.id, [])[:4], "evidence_ids": e.evidence_ids,
                             "why_it_matters": pol.why(lens, e.category), "action": pol.action(lens, e.category),
                             "why_source": "template (inference)"})
        if rich:
            summary = llm_p["executive_summary"]
        else:
            insights = deterministic_insights(ranked, by_id, claims, lens)
            top = [f for f in findings if f["above_threshold"]][:3]
            summary = (f"{len(findings)} ranked developments across {len({f['company'] for f in findings})} companies; "
                       f"{len(top)} above this stakeholder's alert threshold."
                       + (" Most important: " + "; ".join(f["title"] for f in top) + "." if top else ""))
        body = {"persona": pol.PERSONAS[pid]["label"], "policy_version": pv.version, "summary": summary,
                "summary_kind": "llm synthesis (inference over cited facts)" if rich else "deterministic",
                "insights": insights, "insights_source": "llm (validated citations)" if rich else "template",
                "watch_next": (llm_p.get("watch_next") or [])[:4] if rich else [],
                "findings": findings, "unknowns": unknowns,
                "next_steps": ["Review ambiguous entities and re-run with a domain to resolve them."] if any(
                    e.resolution == "ambiguous" for e in ents) else []}
        db.add(Brief(request_id=req.id, persona_id=pid, policy_version_id=pv.id,
                     mode=mode if rich else "deterministic — " + mode.replace("deterministic ", ""), body=body))
    req.brief_mode = mode
    db.commit()


# ---------------- watcher ----------------

def watch_definition(company_ids: list[int]) -> dict:
    return {
        "entities": {"crustdata_company_ids": company_ids[:settings.watch_max_entities]},
        "track": {"op": "or", "conditions": [{"field": "headcount.total", "type": "changed"},
                                             {"field": "news", "type": "added", "keys": ["article_url"]}]},
        "fields": ["basic_info", "headcount", "news"],
        "config": {"trigger": {"type": "interval", "every_hours": settings.watch_every_hours},
                   "max_results_per_run": settings.watch_max_results_per_run},
        "notifications": ([{"type": "webhook", "url": settings.public_webhook_url}] if settings.public_webhook_url else []),
    }


def create_watch(db, req: Request, cd: CrustdataClient, ents: list[Entity]) -> Watch | None:
    ids = sorted({e.crustdata_id for e in ents if e.resolution == "resolved" and e.crustdata_id})
    if not ids:
        return None
    existing = db.scalar(select(Watch).where(Watch.crustdata_watch_id.is_not(None), Watch.status != "cancelled")
                         .order_by(Watch.id.desc()))
    if existing and set(ids) <= set(existing.definition.get("entities", {}).get("crustdata_company_ids", [])):
        req.notes = req.notes + [f"Reusing shared watch {existing.crustdata_watch_id} (already covers these companies)"]
        return existing
    d = watch_definition(ids)
    w = Watch(request_id=req.id, definition=d, delivery="webhook" if d["notifications"] else "pull")
    db.add(w)
    try:
        created = cd.watch_create(d) or {}
        w.crustdata_watch_id = created.get("id")
        w.status = created.get("status", "created")
        if w.crustdata_watch_id:
            w.readback = cd.watch_get(w.crustdata_watch_id) or {}
            w.status = w.readback.get("status", w.status)
            if w.delivery == "webhook":
                try:
                    cd.watch_test(w.crustdata_watch_id)
                except CrustdataError as e:
                    w.error = f"test notification failed: {e}"
    except (CreditsExhausted, NotConfigured):
        raise
    except CrustdataError as e:
        w.status, w.error = "failed", str(e)
    db.commit()
    return w


def reconcile(db, w: Watch, cd: CrustdataClient) -> dict:
    """Pull run history; process unseen runs through the same ingestion path as webhooks."""
    from .webhook import ingest_payload
    w.readback = cd.watch_get(w.crustdata_watch_id) or w.readback
    w.status = w.readback.get("status", w.status)
    data = cd.watch_runs(w.crustdata_watch_id) or {}
    runs = data.get("runs", data if isinstance(data, list) else [])
    w.runs = runs[:20]
    processed = 0
    for run in runs:
        if (run.get("new_records_count") or 0) == 0:
            continue
        summary = cd.watch_run_summary(w.crustdata_watch_id, run.get("id")) or {}
        meta = summary.get("metadata") or {"watch_id": w.crustdata_watch_id, "run_id": run.get("id")}
        meta.setdefault("notification_id", f"run_{run.get('id')}")
        r = ingest_payload(db, {"metadata": meta, "results": summary.get("results", [])}, via="run_history")
        processed += r.get("events", 0)
    w.last_reconciled_at = datetime.now(timezone.utc)
    db.commit()
    return {"runs": len(runs), "events_created": processed, "status": w.status, "last_run_at": w.readback.get("last_run_at")}


# ---------------- orchestrator ----------------

def step(db, req, stage, fn):
    t0 = time.monotonic()
    try:
        out = fn()
        db.add(RunStep(request_id=req.id, stage=stage, status="ok", duration_ms=int((time.monotonic() - t0) * 1000)))
        db.commit()
        return out
    except Exception as e:
        db.rollback()
        db.add(RunStep(request_id=req.id, stage=stage, status="failed", duration_ms=int((time.monotonic() - t0) * 1000),
                       detail=f"{type(e).__name__}: {e}"[:500]))
        db.commit()
        raise


def choose_candidate(db, entity_id: int, crustdata_company_id: int, cd: CrustdataClient | None = None,
                     llm: LLMProvider | None = None) -> Entity:
    """Human exception handling: a reviewer picks one of the Identify candidates for an ambiguous input."""
    ent = db.get(Entity, entity_id)
    if not ent or ent.resolution != "ambiguous":
        raise ValueError("only ambiguous entities can be resolved by selection")
    cand = next((a for a in ent.alternatives if a.get("crustdata_company_id") == crustdata_company_id), None)
    if not cand:
        raise ValueError("candidate is not one of the Crustdata Identify matches")
    req = db.get(Request, ent.request_id)
    ent.resolution, ent.crustdata_id, ent.name, ent.domain = "resolved", cand["crustdata_company_id"], cand["name"], cand["domain"]
    ent.confidence, ent.resolved_via = cand.get("confidence"), "reviewer selected from Crustdata Identify candidates"
    db.commit()
    cd = cd or CrustdataClient(db, req.id)
    llm = llm or LLMProvider(db, req.id)
    step(db, req, "evidence(selected)", lambda: collect_evidence(db, req, cd, [ent]))
    events = list(db.scalars(select(Event).where(Event.request_id == req.id)))
    pol.assess_all_personas(db, events)
    ents = list(db.scalars(select(Entity).where(Entity.request_id == req.id)))
    step(db, req, "brief(rebuild)", lambda: build_briefs(db, req, llm, ents))
    if settings.watch_auto_create:
        try:
            step(db, req, "watch(update)", lambda: create_watch(db, req, cd, ents))
        except CrustdataError as e:
            req.notes = req.notes + [f"Watch: {e}"]
    if events:
        req.status = "complete"
    db.commit()
    return ent


def run_request(db, request_id: int, cd: CrustdataClient | None = None, llm: LLMProvider | None = None):
    req = db.get(Request, request_id)
    cd = cd or CrustdataClient(db, request_id)
    llm = llm or LLMProvider(db, request_id)
    pol.ensure_presets(db)
    ents: list[Entity] = []
    try:
        p = step(db, req, "plan", lambda: plan(db, req, llm))
        if cd.configured:
            try:
                req.credits_before = (step(db, req, "preflight", cd.credits) or {}).get("account", {}).get("credits")
                step(db, req, "preflight_endpoints", cd.endpoints)
            except CrustdataError as e:
                req.notes = req.notes + [f"Preflight: {e}"]
        ents = step(db, req, "resolve", lambda: resolve(db, req, cd, p))
        step(db, req, "evidence", lambda: collect_evidence(db, req, cd, ents))
        events = list(db.scalars(select(Event).where(Event.request_id == req.id)))
        step(db, req, "score", lambda: pol.assess_all_personas(db, events))
        step(db, req, "brief", lambda: build_briefs(db, req, llm, ents))
        if settings.watch_auto_create:
            try:
                step(db, req, "watch", lambda: create_watch(db, req, cd, ents))
            except CrustdataError as e:
                req.notes = req.notes + [f"Watch: {e}"]
        req.status = "complete" if events else "partial"
    except NotConfigured:
        req.status = "partial"
        req.notes = req.notes + ["Crustdata API key not configured: no live data retrieved (nothing fabricated)."]
        try:
            build_briefs(db, req, llm, ents)
        except Exception:
            pass
    except CreditsExhausted:
        req.status = "partial"
        req.notes = req.notes + ["Crustdata 402: insufficient credits — run stopped (no retry)."]
        build_briefs(db, req, llm, ents)
    except Exception as e:  # visible failure, never a silent success
        db.rollback()
        req = db.get(Request, request_id)
        req.status = "failed"
        req.notes = req.notes + [f"{type(e).__name__}: {e}"[:300]]
    if cd.configured:
        try:
            req.credits_after = (cd.credits() or {}).get("account", {}).get("credits")
        except CrustdataError:
            pass
    db.commit()
    return req
