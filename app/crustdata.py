"""Crustdata REST client (docs.crustdata.com, x-api-version 2025-11-01).

Every call is recorded in `api_call` with status, duration, result count and the
actual `X-Credits-Used` header. The API key is only ever placed in the
Authorization header and is never logged or stored.
"""
import random
import time

import httpx

from .config import settings
from .models import ApiCall

# Public list-price ESTIMATES (docs.crustdata.com/general/pricing). Not the account price;
# used only for the pre-call budget guard. Actual spend comes from X-Credits-Used.
ESTIMATES = {
    "/account/credits": 0, "/account/endpoints": 0, "/company/identify": 0,
    "/company/search": 0.5, "/company/enrich": 4, "/person/search": 0.5,
    "/job/search": 1, "/web/search/live": 1, "/watch": 0,
}


class CrustdataError(Exception):
    terminal = False

    def __init__(self, msg: str, status: int | None = None, body=None):
        super().__init__(msg)
        self.status, self.body = status, body


class NotConfigured(CrustdataError):
    terminal = True


class CreditsExhausted(CrustdataError):  # 402: terminal, never retried
    terminal = True


class Forbidden(CrustdataError):  # 403: endpoint or fields denied
    pass


class BudgetExceeded(CrustdataError):
    pass


class Malformed(CrustdataError):
    pass


def _estimate(path: str) -> float:
    for k, v in ESTIMATES.items():
        if path.startswith(k):
            return v
    return 1.0


def _count(data) -> int | None:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for k in ("companies", "profiles", "job_listings", "results", "runs"):
            if isinstance(data.get(k), list):
                return len(data[k])
    return None


class CrustdataClient:
    def __init__(self, db, request_id: int | None = None, transport: httpx.BaseTransport | None = None,
                 api_key: str | None = None, run_cap: float | None = None, sleep=time.sleep):
        self.db = db
        self.request_id = request_id
        self.api_key = settings.crustdata_api_key if api_key is None else api_key
        self.run_cap = settings.run_credit_cap if run_cap is None else run_cap
        self.sleep = sleep
        self.http = httpx.Client(base_url=settings.crustdata_base_url, timeout=settings.crustdata_timeout_s,
                                 transport=transport)
        self.spent = 0.0  # actual credits this run (X-Credits-Used)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _log(self, **kw) -> ApiCall:
        row = ApiCall(request_id=self.request_id, **kw)
        self.db.add(row)
        self.db.commit()
        return row

    def call(self, method: str, path: str, stage: str, json=None, params=None, max_retries: int = 2):
        est = _estimate(path)
        if not self.configured:
            self._log(stage=stage, method=method, endpoint=path, outcome="not_configured", estimated_credits=est,
                      error="CRUSTDATA_API_KEY not set")
            raise NotConfigured("CRUSTDATA_API_KEY is not configured")
        if est and self.spent + est > self.run_cap:
            self._log(stage=stage, method=method, endpoint=path, outcome="skipped_budget", estimated_credits=est,
                      error=f"run cap {self.run_cap} would be exceeded (spent {self.spent})")
            raise BudgetExceeded(f"run credit cap {self.run_cap} reached")
        headers = {"Authorization": f"Bearer {self.api_key}", "x-api-version": settings.crustdata_api_version,
                   "Content-Type": "application/json"}
        attempts, t0 = 0, time.monotonic()
        while True:
            attempts += 1
            try:
                resp = self.http.request(method, path, json=json, params=params, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempts <= 1:
                    self.sleep(1.0)
                    continue
                self._log(stage=stage, method=method, endpoint=path, outcome="timeout", estimated_credits=est,
                          attempts=attempts, duration_ms=int((time.monotonic() - t0) * 1000), error=type(e).__name__)
                raise CrustdataError(f"{path}: network error/timeout ({type(e).__name__})")
            retryable = resp.status_code == 429 or resp.status_code >= 500
            if retryable and attempts <= max_retries:
                reset = resp.headers.get("X-RateLimit-Reset") or resp.headers.get("retry-after")
                try:
                    wait = min(float(reset), 10.0)
                except (TypeError, ValueError):
                    wait = 1.5 * attempts
                self.sleep(wait + random.uniform(0, 0.5))
                continue
            break
        dur = int((time.monotonic() - t0) * 1000)
        used = resp.headers.get("X-Credits-Used")
        credits = float(used) if used not in (None, "") else None
        if credits:
            self.spent += credits
        status = resp.status_code
        body = None
        if resp.content:
            try:
                body = resp.json()
            except ValueError:
                body = None
        base = dict(stage=stage, method=method, endpoint=path, http_status=status, duration_ms=dur,
                    credits_used=credits, estimated_credits=est, attempts=attempts)
        if status == 402:
            self._log(outcome="insufficient_credits", error=_err(body), **base)
            raise CreditsExhausted("Crustdata returned 402: insufficient credits", status, body)
        if status == 403:
            self._log(outcome="forbidden", error=_err(body), **base)
            raise Forbidden(f"{path}: 403 access denied ({_err(body)})", status, body)
        if status == 429:
            self._log(outcome="rate_limited", error=_err(body), **base)
            raise CrustdataError(f"{path}: rate limited after {attempts} attempts", status, body)
        if status >= 400:
            self._log(outcome="http_error", error=_err(body)[:500], **base)
            raise CrustdataError(f"{path}: HTTP {status} {_err(body)[:200]}", status, body)
        if status == 204:
            self._log(outcome="ok", result_count=0, **base)
            return None
        if body is None:
            self._log(outcome="malformed", error="non-JSON response", **base)
            raise Malformed(f"{path}: malformed (non-JSON) response", status)
        n = _count(body)
        self._log(outcome="empty" if n == 0 else "ok", result_count=n, **base)
        return body

    # ---- endpoint helpers (shapes from the 2025-11-01 API reference) ----
    def credits(self):
        return self.call("GET", "/account/credits", "preflight")

    def endpoints(self):
        return self.call("GET", "/account/endpoints", "preflight")

    def identify(self, names=None, domains=None):
        body = {"domains": domains, "exact_match": True} if domains else {"names": names}
        return self.call("POST", "/company/identify", "resolve", json=body)

    def company_search(self, query: str, limit: int = 5):
        return self.call("POST", "/company/search", "discover",
                         json={"search": {"query": query, "mode": "hybrid"}, "limit": limit,
                               "fields": ["crustdata_company_id", "basic_info", "headcount", "funding"]})

    def enrich(self, ids: list[int], fields: list[str]):
        return self.call("POST", "/company/enrich", "evidence", json={"crustdata_company_ids": ids, "fields": fields})

    def jobs(self, company_id: int, limit: int):
        return self.call("POST", "/job/search", "evidence", json={
            "filters": {"field": "company.basic_info.company_id", "type": "=", "value": company_id},
            "fields": ["job_details.title", "job_details.category", "job_details.url", "metadata.date_added",
                       "location.country"],
            "sorts": [{"field": "metadata.date_added", "order": "desc"}], "limit": limit})

    def people(self, company_id: int, limit: int):
        roles = ["founder", "chief", "ceo", "cto", "vp", "head"]
        return self.call("POST", "/person/search", "evidence", json={
            "filters": {"op": "and", "conditions": [
                {"field": "experience.employment_details.current.company_id", "type": "=", "value": company_id},
                {"op": "or", "conditions": [{"field": "experience.employment_details.current.title", "type": "(.)",
                                             "value": r} for r in roles]}]},
            "limit": limit})

    def web_search(self, query: str):
        return self.call("POST", "/web/search/live", "evidence", json={"query": query, "sources": ["news"]})

    # Watcher (company entity watch)
    def watch_create(self, definition: dict):
        return self.call("POST", "/watch/company", "watch", json=definition, max_retries=1)

    def watch_get(self, watch_id: int):
        return self.call("GET", f"/watch/company/{watch_id}", "watch")

    def watch_test(self, watch_id: int):
        return self.call("POST", f"/watch/company/{watch_id}/test", "watch", json={})

    def watch_runs(self, watch_id: int, limit: int = 20):
        return self.call("GET", f"/watch/company/{watch_id}/runs", "watch", params={"limit": limit})

    def watch_run_summary(self, watch_id: int, run_id):
        return self.call("GET", f"/watch/company/{watch_id}/runs/{run_id}/summary", "watch")


def _err(body) -> str:
    if isinstance(body, dict):
        e = body.get("error")
        if isinstance(e, dict):
            return str(e.get("message") or e.get("type") or e)
        return str(e or body.get("message") or "")[:500]
    return ""
