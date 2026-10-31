"""Persona-aware Competitive Intelligence Desk — FastAPI app.  Run: uvicorn app.main:app --reload"""
import json
from pathlib import Path

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Request as HttpRequest
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from . import policy as pol
from .config import settings
from .crustdata import CrustdataClient, CrustdataError
from .llm import LLMProvider
from .models import (ApiCall, Assessment, AuditLog, Brief, Claim, Entity, Event, Evidence, LlmCall, PolicyVersion,
                     Proposal, Request, RunStep, SessionLocal, Watch, WatcherEnvelope, init_db)
from .pipeline import choose_candidate, reconcile, run_request
from .webhook import MAX_BODY, ingest_payload, verify

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Persona-aware Competitive Intelligence Desk")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


@app.on_event("startup")
def _startup():
    init_db()
    with SessionLocal() as db:
        pol.ensure_presets(db)


def modes():
    return {"crustdata": "live" if settings.crustdata_api_key else "NOT CONFIGURED (no live data)",
            "llm": (f"llm:{settings.anthropic_model}" if settings.anthropic_api_key and settings.llm_enabled
                    else "deterministic fallback (no ANTHROPIC_API_KEY)" if settings.llm_enabled else "deterministic (disabled)"),
            "webhook": "webhook" if settings.public_webhook_url else "pull-only (run-history reconciliation)"}


@app.get("/health")
def health():
    with SessionLocal() as db:
        db.execute(select(1))
    return {"status": "ok", **modes()}


@app.get("/", response_class=HTMLResponse)
def index(request: HttpRequest):
    with SessionLocal() as db:
        reqs = list(db.scalars(select(Request).order_by(Request.id.desc()).limit(15)))
        return templates.TemplateResponse("index.html", {"request": request, "reqs": reqs, "modes": modes()})


def _run(rid: int):
    with SessionLocal() as db:
        run_request(db, rid)


@app.post("/api/requests")
def create_request(bg: BackgroundTasks, payload: dict = Body(...)):
    text = (payload.get("brief") or "").strip()
    if len(text) < 8:
        raise HTTPException(400, "Brief is too short — describe the market and/or name companies.")
    if len(text) > 4000:
        raise HTTPException(400, "Brief too long (max 4000 characters).")
    with SessionLocal() as db:
        r = Request(brief_text=text)
        db.add(r)
        db.commit()
        rid = r.id
    bg.add_task(_run, rid)
    return {"id": rid, "url": f"/requests/{rid}"}


def _req_view(db, rid: int) -> dict:
    req = db.get(Request, rid)
    if not req:
        raise HTTPException(404)
    ents = list(db.scalars(select(Entity).where(Entity.request_id == rid)))
    events = list(db.scalars(select(Event).where(Event.request_id == rid)))
    ev_ids = [e.id for e in events]
    evidence = {e.id: e for e in db.scalars(select(Evidence).where(Evidence.request_id == rid))}
    claims = {}
    for c in db.scalars(select(Claim).where(Claim.event_id.in_(ev_ids or [0]))):
        claims.setdefault(c.event_id, []).append(c)
    personas = {}
    for pid, meta in pol.PERSONAS.items():
        pv = pol.active(db, pid)
        rows = []
        for e in events:
            a = db.scalar(select(Assessment).where(Assessment.event_id == e.id, Assessment.policy_version_id == pv.id))
            if a is None:
                a = pol.assess(db, e, pv)
                db.commit()
            rows.append({"event": e, "a": a})
        rows.sort(key=lambda r: (-r["a"].score, r["event"].id))
        brief = db.scalar(select(Brief).where(Brief.request_id == rid, Brief.persona_id == pid).order_by(Brief.id.desc()))
        personas[pid] = {"label": meta["label"], "pv": pv, "rows": rows, "brief": brief,
                         "versions": list(db.scalars(select(PolicyVersion).where(PolicyVersion.persona_id == pid)
                                                     .order_by(PolicyVersion.version.desc())))}
    watch = db.scalar(select(Watch).where(Watch.request_id == rid).order_by(Watch.id.desc()))
    if watch is None:
        watch = db.scalar(select(Watch).where(Watch.crustdata_watch_id.is_not(None)).order_by(Watch.id.desc()))
    envs = list(db.scalars(select(WatcherEnvelope).order_by(WatcherEnvelope.id.desc()).limit(10)))
    calls = list(db.scalars(select(ApiCall).where(ApiCall.request_id == rid).order_by(ApiCall.id)))
    llm_calls = list(db.scalars(select(LlmCall).where((LlmCall.request_id == rid) | (LlmCall.request_id.is_(None)))
                                .order_by(LlmCall.id)))
    steps = list(db.scalars(select(RunStep).where(RunStep.request_id == rid).order_by(RunStep.id)))
    proposals = list(db.scalars(select(Proposal).order_by(Proposal.id.desc()).limit(10)))
    return {"req": req, "ents": ents, "events": events, "evidence": evidence, "claims": claims, "personas": personas,
            "watch": watch, "envs": envs, "calls": calls, "llm_calls": llm_calls, "steps": steps, "proposals": proposals,
            "credits_used": round(sum(c.credits_used or 0 for c in calls), 3),
            "llm_cost": round(sum(c.est_cost_usd for c in llm_calls), 4),
            "llm_total": round(float(db.scalar(select(func.coalesce(func.sum(LlmCall.est_cost_usd), 0.0))) or 0), 4),
            "audit": list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(10))), "modes": modes()}


@app.get("/requests/{rid}", response_class=HTMLResponse)
def request_page(request: HttpRequest, rid: int):
    with SessionLocal() as db:
        ctx = _req_view(db, rid)
        return templates.TemplateResponse("request.html", {"request": request, **ctx, "json": json})


@app.get("/api/requests/{rid}/status")
def request_status(rid: int):
    with SessionLocal() as db:
        r = db.get(Request, rid)
        if not r:
            raise HTTPException(404)
        steps = [s.stage + ":" + s.status for s in db.scalars(select(RunStep).where(RunStep.request_id == rid))]
        return {"status": r.status, "steps": steps}


FEEDBACK_SYSTEM = ("Translate stakeholder feedback into a typed policy proposal for a competitive-intelligence "
                   "persona. Allowed ops: add_rule (action 'suppress' + category), remove_rule, adjust_weight (category, "
                   "delta between -0.5 and 0.5), set_threshold (value), raise_min_sources (value), lower_min_sources "
                   "(only if the user explicitly asks to weaken evidence), change_watch (any request to change monitoring "
                   "scope/cadence), unsupported. Categories: " + ", ".join(pol.CATEGORIES) + ". Use null for unused "
                   "fields. If the user says NOT to lower evidence, add 'min_sources_unchanged' to guardrail_assertions "
                   "and emit no evidence change. Do not invent instructions the user did not give.")


@app.post("/api/entities/{eid}/choose")
def choose(eid: int, payload: dict = Body(...)):
    with SessionLocal() as db:
        try:
            ent = choose_candidate(db, eid, int(payload.get("crustdata_company_id")))
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e))
        return {"entity_id": ent.id, "crustdata_id": ent.crustdata_id}


@app.post("/api/feedback")
def feedback(payload: dict = Body(...)):
    text = (payload.get("text") or "").strip()
    persona = payload.get("persona_id") or "vc_partner"
    if persona not in pol.PERSONAS or not text:
        raise HTTPException(400, "persona_id and text are required")
    with SessionLocal() as db:
        pol.ensure_presets(db)
        llm = LLMProvider(db, None)
        user = json.dumps({"submitted_under_persona": persona, "feedback": text,
                           "current_policy": pol.active(db, persona).body})
        prop, mode = llm.complete_json("feedback", FEEDBACK_SYSTEM, user, pol.PROPOSAL_SCHEMA,
                                       validator=lambda d: pol.PolicyProposalModel(**d))
        if prop is None:
            prop = pol.deterministic_parse(text, persona)
            mode = "deterministic_v1 — " + mode.replace("deterministic ", "")
        p = pol.create_proposal(db, persona, text, prop, mode)
        return {"id": p.id, "state": p.state, "parser": p.parser, "validation": p.validation, "diff": p.diff,
                "replay": p.replay, "persona_id": p.persona_id}


@app.post("/api/proposals/{pid}/approve")
def approve(pid: int, payload: dict = Body(...)):
    with SessionLocal() as db:
        try:
            nv = pol.approve(db, pid, payload.get("reviewer", ""), bool(payload.get("confirm_high_risk")))
        except pol.GovernanceError as e:
            raise HTTPException(409, str(e))
        return {"persona_id": nv.persona_id, "version": nv.version, "policy_version_id": nv.id}


@app.post("/api/proposals/{pid}/reject")
def reject(pid: int, payload: dict = Body(...)):
    with SessionLocal() as db:
        try:
            pol.reject(db, pid, payload.get("reviewer", ""))
        except pol.GovernanceError as e:
            raise HTTPException(409, str(e))
        return {"state": "rejected"}


@app.post("/api/personas/{persona_id}/rollback")
def rollback(persona_id: str, payload: dict = Body(...)):
    with SessionLocal() as db:
        try:
            nv = pol.rollback(db, persona_id, int(payload.get("to_version", 1)), payload.get("reviewer", ""))
        except pol.GovernanceError as e:
            raise HTTPException(409, str(e))
        return {"persona_id": persona_id, "version": nv.version}


@app.post("/api/watches/{wid}/reconcile")
def reconcile_watch(wid: int):
    with SessionLocal() as db:
        w = db.get(Watch, wid)
        if not w or not w.crustdata_watch_id:
            raise HTTPException(404, "no Crustdata watch")
        try:
            return reconcile(db, w, CrustdataClient(db, w.request_id))
        except CrustdataError as e:
            raise HTTPException(502, str(e))


@app.post("/api/watches/{wid}/test")
def test_watch(wid: int):
    with SessionLocal() as db:
        w = db.get(Watch, wid)
        if not w or not w.crustdata_watch_id:
            raise HTTPException(404, "no Crustdata watch")
        try:
            return CrustdataClient(db, w.request_id).watch_test(w.crustdata_watch_id) or {"sent": True}
        except CrustdataError as e:
            raise HTTPException(502, str(e))


@app.post("/webhooks/crustdata")
async def crustdata_webhook(request: HttpRequest):
    raw = await request.body()
    if len(raw) > MAX_BODY:
        return JSONResponse({"error": "payload too large"}, 413)
    ok, reason = verify(raw, request.headers.get("x-crustdata-signature"), settings.crustdata_api_key)
    if not ok:
        with SessionLocal() as db:
            db.add(WatcherEnvelope(crustdata_watch_id=None, notification_id=f"rejected_{reason}_{id(raw)}",
                                   payload={"headers": {"x-crustdata-event-id": request.headers.get("x-crustdata-event-id")}},
                                   state=f"rejected_{reason}", via="webhook"))
            db.commit()
        return JSONResponse({"error": reason}, 401)
    try:
        payload = json.loads(raw)
    except ValueError:
        return JSONResponse({"error": "malformed json"}, 400)
    with SessionLocal() as db:
        return ingest_payload(db, payload, "webhook", request.headers.get("x-crustdata-event-id"))
