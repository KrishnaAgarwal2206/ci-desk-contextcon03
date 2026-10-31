"""Bounded Anthropic Messages API provider (raw HTTPX, structured JSON output).

Used for exactly three tasks: research planning, brief synthesis, feedback
interpretation. Any failure (no key, disabled, budget, timeout, 429, refusal,
invalid JSON/schema) returns None so the caller falls back to deterministic
logic and labels the mode. The LLM never resolves identities, scores events or
activates policies.
"""
import json
import time

import httpx
from sqlalchemy import func, select

from .config import settings
from .models import LlmCall


class LLMProvider:
    def __init__(self, db, request_id: int | None = None, transport: httpx.BaseTransport | None = None,
                 api_key: str | None = None):
        self.db = db
        self.request_id = request_id
        self.api_key = settings.anthropic_api_key if api_key is None else api_key
        self.http = httpx.Client(timeout=150.0, transport=transport)
        self.last_reason = ""

    def total_spend(self) -> float:
        return float(self.db.scalar(select(func.coalesce(func.sum(LlmCall.est_cost_usd), 0.0))) or 0.0)

    def calls_this_request(self) -> int:
        if self.request_id is None:
            return 0
        return int(self.db.scalar(select(func.count()).select_from(LlmCall).where(
            LlmCall.request_id == self.request_id, LlmCall.outcome != "skipped")) or 0)

    def _record(self, task, outcome, **kw):
        self.db.add(LlmCall(request_id=self.request_id, task=task, model=settings.anthropic_model, outcome=outcome, **kw))
        self.db.commit()
        self.last_reason = outcome

    def cost(self, tin: int, tout: int) -> float:
        return tin / 1e6 * settings.price_in_per_mtok + tout / 1e6 * settings.price_out_per_mtok

    def complete_json(self, task: str, system: str, user: str, schema: dict, validator=None, max_tokens: int | None = None):
        """Returns (data, mode_label). data is None on any failure."""
        if not settings.llm_enabled:
            self.last_reason = "llm_disabled"
            return None, "deterministic (LLM disabled)"
        if not self.api_key:
            self.last_reason = "no_key"
            return None, "deterministic (no ANTHROPIC_API_KEY)"
        if self.total_spend() >= settings.llm_spend_cap_usd:
            self._record(task, "skipped", error="spend cap reached")
            return None, f"deterministic (LLM spend cap ${settings.llm_spend_cap_usd} reached)"
        if self.calls_this_request() >= settings.llm_max_calls_per_request:
            self._record(task, "skipped", error="per-request call limit")
            return None, "deterministic (LLM call limit reached)"
        body = {
            "model": settings.anthropic_model,
            "max_tokens": max_tokens or settings.llm_max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        }
        headers = {"x-api-key": self.api_key, "anthropic-version": settings.anthropic_api_version,
                   "content-type": "application/json"}
        t0 = time.monotonic()
        try:
            r = self.http.post(settings.anthropic_url, json=body, headers=headers)
        except httpx.HTTPError as e:
            self._record(task, "timeout_or_network", duration_ms=int((time.monotonic() - t0) * 1000),
                         error=type(e).__name__)
            return None, "deterministic (LLM timeout/network error)"
        dur = int((time.monotonic() - t0) * 1000)
        if r.status_code != 200:
            outcome = "rate_limited" if r.status_code == 429 else f"http_{r.status_code}"
            self._record(task, outcome, duration_ms=dur, error=r.text[:300])
            return None, f"deterministic (LLM {outcome})"
        try:
            data = r.json()
        except ValueError:
            self._record(task, "malformed", duration_ms=dur)
            return None, "deterministic (LLM malformed response)"
        usage = data.get("usage") or {}
        tin, tout = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        cost = self.cost(tin, tout)
        base = dict(duration_ms=dur, input_tokens=tin, output_tokens=tout, est_cost_usd=cost)
        if data.get("stop_reason") in ("refusal", "max_tokens"):
            self._record(task, data["stop_reason"], **base)
            return None, f"deterministic (LLM stop_reason={data['stop_reason']})"
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        try:
            parsed = json.loads(text)
            if validator:
                parsed = validator(parsed)
        except Exception as e:  # invalid JSON or schema validation error
            self._record(task, "invalid_output", error=str(e)[:300], **base)
            return None, "deterministic (LLM output failed validation)"
        self._record(task, "ok", **base)
        return parsed, f"llm:{settings.anthropic_model}"
