"""SQLite schema (docs/product-v2/DATA_MODEL.md)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Request(Base):
    __tablename__ = "request"
    id: Mapped[int] = mapped_column(primary_key=True)
    brief_text: Mapped[str] = mapped_column(Text)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    planner_mode: Mapped[str] = mapped_column(String(80), default="")
    brief_mode: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(20), default="running")
    notes: Mapped[list] = mapped_column(JSON, default=list)
    credits_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    credits_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Entity(Base):
    __tablename__ = "entity"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("request.id"))
    kind: Mapped[str] = mapped_column(String(10), default="company")
    query: Mapped[str] = mapped_column(String(300))
    crustdata_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(300), default="")
    domain: Mapped[str] = mapped_column(String(300), default="")
    resolution: Mapped[str] = mapped_column(String(20))  # resolved / ambiguous / unresolved
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    alternatives: Mapped[list] = mapped_column(JSON, default=list)
    resolved_via: Mapped[str] = mapped_column(String(60), default="")
    profile: Mapped[dict] = mapped_column(JSON, default=dict)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("request.id"), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entity.id"), nullable=True)
    crustdata_company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str] = mapped_column(Text, default="")
    record_ref: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    source_ts: Mapped[str] = mapped_column(String(40), default="")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    api_call_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Event(Base):
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("request.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(40))
    crustdata_company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_name: Mapped[str] = mapped_column(String(300), default="")
    title: Mapped[str] = mapped_column(Text)
    base_significance: Mapped[float] = mapped_column(Float)
    significance_basis: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String(30), default="initial_research")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Claim(Base):
    __tablename__ = "claim"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"))
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(12))  # fact / inference / unknown
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)


class PolicyVersion(Base):
    __tablename__ = "policy_version"
    __table_args__ = (UniqueConstraint("persona_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[str] = mapped_column(String(40))
    workspace_id: Mapped[str] = mapped_column(String(40), default="default")
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(80), default="system")
    source_proposal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Assessment(Base):
    __tablename__ = "assessment"
    __table_args__ = (UniqueConstraint("event_id", "policy_version_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"))
    persona_id: Mapped[str] = mapped_column(String(40))
    policy_version_id: Mapped[int] = mapped_column(ForeignKey("policy_version.id"))
    score: Mapped[float] = mapped_column(Float)
    components: Mapped[dict] = mapped_column(JSON)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    above_threshold: Mapped[bool] = mapped_column(Boolean, default=False)


class Brief(Base):
    __tablename__ = "brief"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("request.id"))
    persona_id: Mapped[str] = mapped_column(String(40))
    policy_version_id: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(80))
    body: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Proposal(Base):
    __tablename__ = "policy_proposal"
    id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[str] = mapped_column(String(40))
    feedback_text: Mapped[str] = mapped_column(Text)
    body: Mapped[dict] = mapped_column(JSON)
    parser: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(30))  # invalid / pending_review / approved / rejected
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    diff: Mapped[dict] = mapped_column(JSON, default=dict)
    replay: Mapped[dict] = mapped_column(JSON, default=dict)
    base_version_id: Mapped[int] = mapped_column(Integer)
    risk: Mapped[str] = mapped_column(String(10), default="low")
    requires_credit_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewer: Mapped[str] = mapped_column(String(80), default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(60))
    object_type: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Watch(Base):
    __tablename__ = "watch"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("request.id"), nullable=True)
    crustdata_watch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset: Mapped[str] = mapped_column(String(20), default="company")
    kind: Mapped[str] = mapped_column(String(20), default="entity")
    definition: Mapped[dict] = mapped_column(JSON, default=dict)
    readback: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="")
    delivery: Mapped[str] = mapped_column(String(20), default="pull")
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    runs: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WatcherEnvelope(Base):
    __tablename__ = "watcher_envelope"
    __table_args__ = (UniqueConstraint("crustdata_watch_id", "notification_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    crustdata_watch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_id: Mapped[str] = mapped_column(String(60), default="")
    notification_id: Mapped[str] = mapped_column(String(120))
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(30))
    via: Mapped[str] = mapped_column(String(20))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ApiCall(Base):
    __tablename__ = "api_call"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage: Mapped[str] = mapped_column(String(40))
    method: Mapped[str] = mapped_column(String(8))
    endpoint: Mapped[str] = mapped_column(String(200))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_credits: Mapped[float] = mapped_column(Float, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LlmCall(Base):
    __tablename__ = "llm_call"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(20), default="anthropic")
    model: Mapped[str] = mapped_column(String(60))
    outcome: Mapped[str] = mapped_column(String(40))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RunStep(Base):
    __tablename__ = "run_step"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def make_engine(url: str | None = None):
    url = url or settings.database_url
    kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **kw)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(eng=None):
    Base.metadata.create_all(eng or engine)
