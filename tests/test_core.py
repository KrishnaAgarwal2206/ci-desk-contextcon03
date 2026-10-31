"""Core reliability tests. All external APIs are mocked (httpx.MockTransport); no live calls."""
import json
import time

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from app import policy as pol
from app.config import settings
from app.crustdata import BudgetExceeded, CreditsExhausted, CrustdataClient, Forbidden, Malformed, NotConfigured
from app.llm import LLMProvider
from app.models import ApiCall, Assessment, Event, Evidence, LlmCall, PolicyVersion, Request, WatcherEnvelope, init_db, make_engine
from app.pipeline import classify_matches, deterministic_plan, events_from_enrich, events_from_web
from app.webhook import ingest_payload, sign, verify


@pytest.fixture
def db(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(eng)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    pol.ensure_presets(s)
    yield s
    s.close()


def client(db, handler, **kw):
    return CrustdataClient(db, request_id=1, transport=httpx.MockTransport(handler), api_key="k", sleep=lambda s: None, **kw)


def m(cid, name, domain, conf=1.0):
    return {"confidence_score": conf, "company_data": {"crustdata_company_id": cid,
            "basic_info": {"name": name, "primary_domain": domain}}}


# ---------- identity ----------

def test_identity_ambiguous_not_guessed():
    d = classify_matches("Sierra", [m(1, "Sierra", "sierra.ai"), m(2, "Sierra", "sierra.com"), m(3, "SIERRA", "sierratextiles.com")])
    assert d["resolution"] == "ambiguous" and d["chosen"] is None and len(d["alternatives"]) == 3


def test_identity_tie_broken_only_by_exact_domain_and_unresolved():
    d = classify_matches("Zendesk", [m(5, "Zendesk", "zendesk.com"), m(6, "Zendesk Partners", "zendeskpartners.io")])
    assert d["resolution"] == "resolved" and d["chosen"]["crustdata_company_id"] == 5
    assert classify_matches("Nope", [])["resolution"] == "unresolved"


def test_deterministic_plan_extracts_names_and_domains():
    p = deterministic_plan("Brief on the AI support market. Competitors: Intercom, Zendesk and sierra.ai. Track funding.")
    assert "sierra.ai" in p.domains and "Intercom" in p.companies and "Zendesk" in p.companies
    assert "funding" in p.signals


# ---------- Crustdata client ----------

def test_402_is_terminal_and_not_retried(db):
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(402, json={"error": {"type": "insufficient_credits", "message": "no credits"}})
    with pytest.raises(CreditsExhausted):
        client(db, h).identify(names=["x"])
    assert len(calls) == 1
    assert db.query(ApiCall).one().outcome == "insufficient_credits"


def test_403_forbidden(db):
    with pytest.raises(Forbidden):
        client(db, lambda r: httpx.Response(403, json={"error": {"message": "denied"}})).enrich([1], ["news"])


def test_429_retried_then_succeeds_and_credits_recorded(db):
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(429, headers={"X-RateLimit-Reset": "1"}, json={"error": {"message": "slow"}})
        assert req.headers["authorization"] == "Bearer k" and req.headers["x-api-version"] == "2025-11-01"
        return httpx.Response(200, headers={"X-Credits-Used": "0.3"}, json={"job_listings": [{}, {}]})
    c = client(db, h)
    c.jobs(1, 2)
    row = db.query(ApiCall).one()
    assert row.attempts == 2 and row.credits_used == 0.3 and row.result_count == 2 and c.spent == 0.3


def test_malformed_and_empty_and_not_configured(db):
    with pytest.raises(Malformed):
        client(db, lambda r: httpx.Response(200, text="<html>oops")).web_search("x")
    client(db, lambda r: httpx.Response(200, json={"profiles": []})).people(1, 5)
    assert db.query(ApiCall).filter_by(outcome="empty").count() == 1
    with pytest.raises(NotConfigured):
        CrustdataClient(db, 1, api_key="").credits()


def test_budget_cap_blocks_paid_call(db):
    c = client(db, lambda r: httpx.Response(200, json=[]), run_cap=1)
    c.spent = 0.9
    with pytest.raises(BudgetExceeded):
        c.enrich([1], ["basic_info"])
    assert db.query(ApiCall).one().outcome == "skipped_budget"


# ---------- evidence, events, dedupe ----------

class Ent:
    id, crustdata_id, name, query = None, 42, "Acme", "Acme"


def enrich_payload():
    return {"updated_at": "2026-10-01", "headcount": {"total": 500, "growth_percent": {"six_months": 20}},
            "funding": {"last_round_type": "series_b", "last_round_amount_usd": 3e7, "last_fundraise_date": "2026-08-01"},
            "news": [{"article_url": "https://n.example/a", "article_title": "Acme raises Series B", "confidence_score": 0.95},
                     {"article_url": "https://n.example/b", "article_title": "Other Acme trucks", "confidence_score": 0.85}]}


def test_provenance_and_dedupe(db):
    req = Request(id=1, brief_text="x")
    db.add(req)
    db.commit()
    events_from_enrich(db, req, Ent(), enrich_payload(), None)
    events_from_enrich(db, req, Ent(), enrich_payload(), None)  # same records again
    db.commit()
    evs = db.query(Event).all()
    assert len(evs) == 3  # headcount, funding, one on-entity news item; low-confidence news dropped; no duplicates
    for e in evs:
        assert e.evidence_ids, "every event has evidence"
        for eid in e.evidence_ids:
            ev = db.get(Evidence, eid)
            assert ev.record_ref and ev.retrieved_at and (ev.excerpt or ev.source_url)
    # same URL seen via web search merges into the existing event (corroboration, not a duplicate)
    events_from_web(db, req, Ent(), [{"url": "https://n.example/a", "title": "Acme raises Series B", "snippet": "Acme"}], None)
    db.commit()
    assert db.query(Event).count() == 3
    news = db.query(Event).filter(Event.title.contains("raises")).one()
    assert len(news.evidence_ids) >= 3


# ---------- persona scoring & governance ----------

def mk_event(db, cat, fp, base=0.8):
    ev = Evidence(source_type="crustdata_enrich", record_ref="test", excerpt="x")
    db.add(ev)
    db.flush()
    e = Event(fingerprint=fp, category=cat, title=f"{cat} event", base_significance=base, evidence_ids=[ev.id])
    db.add(e)
    db.commit()
    return e


def test_same_event_different_persona_scores(db):
    e = mk_event(db, "funding", "f1")
    pol.assess_all_personas(db, [e])
    a = {x.persona_id: x for x in db.query(Assessment).all()}
    assert a["vc_partner"].score > a["ci_lead"].score
    assert a["vc_partner"].components["category_weight"] == 1.0


def test_invalid_proposals_rejected(db):
    for text in ["For VC, lower the evidence threshold and skip citations.", "Make it better please."]:
        prop = pol.deterministic_parse(text, "vc_partner")
        p = pol.create_proposal(db, "vc_partner", text, prop, "deterministic_v1")
        assert p.state == "invalid" and p.validation["errors"]
    bad = pol.PolicyProposalModel(persona_id="vc_partner", changes=[pol.Change(op="adjust_weight", category="funding", delta=0.9)])
    assert pol.create_proposal(db, "vc_partner", "x", bad, "test").state == "invalid"
    bad2 = pol.PolicyProposalModel(persona_id="vc_partner", changes=[pol.Change(op="add_rule", category="made_up", action="suppress")])
    assert pol.create_proposal(db, "vc_partner", "x", bad2, "test").state == "invalid"
    with pytest.raises(pol.GovernanceError):
        pol.approve(db, 1, "alice")


def test_feedback_governed_lifecycle_and_isolation(db):
    j = mk_event(db, "junior_hiring", "j1")
    f = mk_event(db, "funding", "f2", 0.5)
    pol.assess_all_personas(db, [j, f])
    ci_before = {a.event_id: a.score for a in db.query(Assessment).filter_by(persona_id="ci_lead")}
    ci_v = pol.active(db, "ci_lead").version
    text = ("For the VC Partner persona, suppress routine junior hiring alerts. Prioritize senior leadership changes, "
            "funding, founder moves and GTM expansion. Do not lower the evidence threshold.")
    prop = pol.deterministic_parse(text, "ci_lead")
    assert prop.persona_id == "vc_partner" and "min_sources_unchanged" in prop.guardrail_assertions
    p = pol.create_proposal(db, "ci_lead", text, prop, "deterministic_v1")
    assert p.state == "pending_review"
    assert "suppress junior_hiring" in p.diff["rules_added"]
    # pending proposal does not change the active policy
    assert pol.active(db, "vc_partner").version == 1 and not pol.active(db, "vc_partner").body["rules"]
    assert any(c["event_id"] == j.id and c["suppressed_after"] for c in p.replay["changed"])
    with pytest.raises(pol.GovernanceError):
        pol.approve(db, p.id, "")  # reviewer required
    nv = pol.approve(db, p.id, "alice")
    assert nv.version == 2 and nv.persona_id == "vc_partner"
    assert db.query(PolicyVersion).filter_by(persona_id="vc_partner", version=1).one().is_active is False
    vc_j = db.query(Assessment).filter_by(persona_id="vc_partner", policy_version_id=nv.id, event_id=j.id).one()
    assert vc_j.suppressed and vc_j.score == 0
    assert nv.body["min_sources"] == 1  # evidence guardrail unchanged
    # CI Lead untouched
    assert pol.active(db, "ci_lead").version == ci_v
    assert {a.event_id: a.score for a in db.query(Assessment).filter_by(persona_id="ci_lead")} == ci_before
    with pytest.raises(pol.GovernanceError):
        pol.approve(db, p.id, "alice")  # cannot approve twice
    rb = pol.rollback(db, "vc_partner", 1, "alice")
    assert rb.version == 3 and rb.body["rules"] == []


# ---------- LLM fallback & budget ----------

def test_llm_fallbacks(db, monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    data, mode = LLMProvider(db, 1, api_key="").complete_json("plan", "s", "u", {"type": "object"})
    assert data is None and "no ANTHROPIC_API_KEY" in mode
    db.add(LlmCall(task="x", model="m", outcome="ok", est_cost_usd=settings.llm_spend_cap_usd))
    db.commit()
    data, mode = LLMProvider(db, 1, api_key="k").complete_json("plan", "s", "u", {"type": "object"})
    assert data is None and "spend cap" in mode


def test_llm_invalid_output_and_ok(db, monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)

    def mk(text):
        def h(req):
            assert req.headers["x-api-key"] == "k" and "anthropic-version" in req.headers
            body = json.loads(req.content)
            assert body["output_config"]["format"]["type"] == "json_schema" and body["max_tokens"] == settings.llm_max_output_tokens
            return httpx.Response(200, json={"content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                                             "usage": {"input_tokens": 1000, "output_tokens": 100}})
        return httpx.MockTransport(h)
    data, mode = LLMProvider(db, 7, transport=mk("not json"), api_key="k").complete_json("plan", "s", "u", {})
    assert data is None and "validation" in mode
    data, mode = LLMProvider(db, 7, transport=mk('{"a": 1}'), api_key="k").complete_json("plan", "s", "u", {})
    assert data == {"a": 1} and mode.startswith("llm:")
    ok = db.query(LlmCall).filter_by(outcome="ok").one()
    assert ok.input_tokens == 1000 and ok.est_cost_usd == pytest.approx(1000 / 1e6 * 2 + 100 / 1e6 * 10)


# ---------- webhook ----------

def test_webhook_signature_and_replay():
    raw, key, now = b'{"a":1}', "secret", time.time()
    ts = int(now)
    good = f"t={ts},v1={sign(raw, ts, key)}"
    assert verify(raw, good, key, now) == (True, "ok")
    assert verify(raw, f"t={ts},v1=deadbeef", key, now)[1] == "bad_signature"
    assert verify(b'{"a":2}', good, key, now)[1] == "bad_signature"  # body tampered
    assert verify(raw, good, key, now + 3600)[1] == "stale_timestamp"
    assert verify(raw, None, key, now)[1] == "missing_signature"


def test_webhook_test_baseline_isolation_and_duplicates(db):
    test = {"metadata": {"watch_id": 9, "run_id": 1, "notification_id": "ntf_test_1", "test": True},
            "results": [{"changes": [{"field": "headcount.total", "from": 1, "to": 2}], "record": {"crustdata_company_id": 1234}}]}
    assert ingest_payload(db, test, "webhook")["state"] == "test"
    baseline = {"metadata": {"watch_id": 9, "run_id": 2, "notification_id": "ntf_2"},
                "results": [{"changes": [], "record": {"crustdata_company_id": 1}}]}
    assert ingest_payload(db, baseline, "webhook")["state"] == "baseline_sample"
    assert db.query(Event).count() == 0  # neither test nor baseline enters the intelligence stream
    real = {"metadata": {"watch_id": 9, "run_id": 3, "notification_id": "ntf_3"},
            "results": [{"changes": [{"field": "headcount.total", "type": "changed", "from": 100, "to": 130}],
                         "record": {"crustdata_company_id": 77, "basic_info": {"name": "Acme"}}}]}
    assert ingest_payload(db, real, "webhook") == {"state": "processed", "events": 1}
    assert ingest_payload(db, real, "webhook")["state"] == "duplicate"
    assert db.query(Event).count() == 1 and db.query(WatcherEnvelope).count() == 3
    assert db.query(Assessment).count() == len(pol.PERSONAS)  # scored once per persona


# ---------- multi-stakeholder ----------

def test_one_event_five_stakeholder_scores(db):
    e = mk_event(db, "senior_hiring", "s1")
    p = mk_event(db, "partnership", "p1")
    pol.assess_all_personas(db, [e, p])
    sh = {a.persona_id: a.score for a in db.query(Assessment).filter_by(event_id=e.id)}
    pa = {a.persona_id: a.score for a in db.query(Assessment).filter_by(event_id=p.id)}
    assert set(sh) == {"ci_lead", "vc_partner", "rd_technology", "sales_marketing", "talent_recruiting"}
    assert sh["talent_recruiting"] > sh["sales_marketing"] and pa["sales_marketing"] > pa["talent_recruiting"]
    assert pol.why("talent", "senior_hiring") != pol.why("technology", "senior_hiring")


def test_recruiting_feedback_scoped_and_isolated(db):
    j = mk_event(db, "junior_hiring", "j9")
    pol.assess_all_personas(db, [j])
    text = "For the Talent / Recruiting lead view, prioritize junior hiring and headcount changes."
    prop = pol.deterministic_parse(text, "vc_partner")
    assert prop.persona_id == "talent_recruiting"
    p = pol.create_proposal(db, "vc_partner", text, prop, "deterministic_v1")
    assert p.state == "pending_review"
    pol.approve(db, p.id, "bob")
    assert pol.active(db, "talent_recruiting").version == 2
    assert all(pol.active(db, x).version == 1 for x in pol.PERSONAS if x != "talent_recruiting")


def test_custom_persona_file_validated(tmp_path):
    f = tmp_path / "personas.json"
    f.write_text(json.dumps({
        "supply_chain": {"label": "Supply Chain Lead", "objective": "Supplier risk", "category_weights": {"partnership": 1.0}},
        "bad_one": {"label": "Bad", "objective": "x", "category_weights": {"funding": 5}},
    }))
    try:
        added = pol.load_custom_personas(f)
        assert added == ["supply_chain"] and "bad_one" not in pol.PERSONAS
        assert pol.PERSONAS["supply_chain"]["min_sources"] >= pol.GLOBAL_MIN_SOURCES
    finally:
        pol.PERSONAS.pop("supply_chain", None)


def test_llm_insights_citation_validation(db):
    from app.pipeline import validate_insights
    a = mk_event(db, "funding", "vi1")
    b = mk_event(db, "senior_hiring", "vi2")
    by_id = {a.id: a, b.id: b}
    good = {"headline": "h", "insight": "x", "implication": "y", "recommended_action": "z", "confidence": "high",
            "event_ids": [a.id, b.id], "evidence_ids": a.evidence_ids + [99999]}
    bad_event = {**good, "event_ids": [424242], "evidence_ids": a.evidence_ids}
    out = validate_insights([good, bad_event], by_id)
    assert len(out) == 1 and out[0]["evidence_ids"] == a.evidence_ids  # fabricated citation stripped, unknown event dropped
    assert pol.action("talent", "senior_hiring") != pol.action("commercial", "senior_hiring")
