"""Crustdata Watcher webhook ingestion.

Signature (docs: watcher-docs/company/entity.md): header
`x-crustdata-signature: t=<unix>,v1=<hex>` where v1 = HMAC-SHA256 over
`<t>.<raw-body>` keyed by the Crustdata API key.
"""
import hashlib
import hmac
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import policy as pol
from .config import settings
from .models import Entity, Evidence, WatcherEnvelope
from .pipeline import fp, news_category, upsert_event

MAX_BODY = 1_000_000


def sign(raw: bytes, ts: int, key: str) -> str:
    return hmac.new(key.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()


def verify(raw: bytes, header: str | None, key: str, now: float | None = None) -> tuple[bool, str]:
    if not key:
        return False, "no_key_configured"
    if not header:
        return False, "missing_signature"
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    try:
        ts = int(parts.get("t", ""))
    except ValueError:
        return False, "bad_signature_header"
    if abs((now or time.time()) - ts) > settings.webhook_tolerance_s:
        return False, "stale_timestamp"
    if not hmac.compare_digest(sign(raw, ts, key), parts.get("v1", "")):
        return False, "bad_signature"
    return True, "ok"


FIELD_CAT = {"headcount": "headcount_change", "news": "news_mention", "funding": "funding"}


def ingest_payload(db, payload: dict, via: str, event_id_header: str | None = None) -> dict:
    meta = payload.get("metadata") or {}
    watch_id = meta.get("watch_id")
    nid = str(event_id_header or meta.get("notification_id") or f"run_{meta.get('run_id')}")
    is_test = bool(meta.get("test"))
    results = payload.get("results") or []
    if is_test:
        state = "test"
    elif results and all(not (r.get("changes") or []) for r in results):
        state = "baseline_sample"
    else:
        state = "received"
    env = WatcherEnvelope(crustdata_watch_id=watch_id, run_id=str(meta.get("run_id", "")), notification_id=nid,
                          is_test=is_test, payload=payload, state=state, via=via)
    db.add(env)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"state": "duplicate", "events": 0}
    if state != "received":  # test + baseline never enter the intelligence stream
        return {"state": state, "events": 0}
    created = []
    for r in results:
        changes = r.get("changes") or []
        if not changes:
            continue
        rec = r.get("record") or {}
        cid = rec.get("crustdata_company_id") or (rec.get("basic_info") or {}).get("crustdata_company_id")
        name = (rec.get("basic_info") or {}).get("name") or str(cid)
        ent = db.scalar(select(Entity).where(Entity.crustdata_id == cid))
        for ch in changes:
            field = ch.get("field", "")
            cat = FIELD_CAT.get(field.split(".")[0], "news_mention")
            if field.startswith("news"):
                for art in ch.get("new_elements") or []:
                    url, title = art.get("article_url") or art.get("url") or "", art.get("article_title") or art.get("title") or ""
                    ev = Evidence(entity_id=ent.id if ent else None, crustdata_company_id=cid, source_type=f"watcher_{via}",
                                  source_url=url, record_ref=f"watch {watch_id} run {meta.get('run_id')} notification {nid}",
                                  excerpt=title, source_ts=str(meta.get("delivered_at", ""))[:40])
                    db.add(ev)
                    db.flush()
                    created.append(upsert_event(db, None, cid, name, news_category(title), f"{name}: {title}", 0.7,
                                                "Watcher-delivered news (new element)", fp("url", url), [ev],
                                                [f"Watcher reported new article: \"{title}\"."], origin="watcher"))
                continue
            desc = f"{field} changed from {ch.get('from')} to {ch.get('to')}"
            ev = Evidence(entity_id=ent.id if ent else None, crustdata_company_id=cid, source_type=f"watcher_{via}",
                          record_ref=f"watch {watch_id} run {meta.get('run_id')} notification {nid} field={field}",
                          excerpt=desc, source_ts=str(meta.get("delivered_at", ""))[:40])
            db.add(ev)
            db.flush()
            base = 0.6
            try:
                a, b = float(ch.get("from")), float(ch.get("to"))
                base = min(1.0, 0.3 + abs(b - a) / max(a, 1) * 5)
            except (TypeError, ValueError):
                pass
            created.append(upsert_event(db, None, cid, name, cat, f"{name}: {desc}", base, "Watcher change magnitude",
                                        fp("watch", cid, field, ch.get("from"), ch.get("to")), [ev],
                                        [f"Watcher reported {desc}."], origin="watcher"))
    db.commit()
    pol.ensure_presets(db)
    pol.assess_all_personas(db, created)
    env.state = "processed"
    db.commit()
    return {"state": "processed", "events": len(created)}
