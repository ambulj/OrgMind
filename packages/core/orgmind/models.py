"""SQLAlchemy Relational Database Models for OrgMind Application Layer.

Stores users, workspaces, memberships, audit logs, chat sessions, and review items.
Graph data (people, docs, decisions, tickets) remains in FalkorDB.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from orgmind.config import settings


class Base(DeclarativeBase):
    pass


class Role(str, Enum):
    """Role-based access control tiers."""

    ADMIN = "Admin"
    EDITOR = "Editor"
    VIEWER = "Viewer"
    AUDITOR = "Auditor"


class User(Base):
    """User account model for local auth and federated identities."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Workspace(Base):
    """Multi-tenant workspace partition model.
    Maps 1-to-1 with isolated FalkorDB graph 'org_<slug>'.
    """

    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    memberships = relationship(
        "Membership", back_populates="workspace", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="workspace", cascade="all, delete-orphan")


class Membership(Base):
    """User membership in a workspace with assigned RBAC role."""

    __tablename__ = "memberships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False)
    role = Column(String(50), default=Role.VIEWER.value, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    user = relationship("User", back_populates="memberships")
    workspace = relationship("Workspace", back_populates="memberships")


class AuditLog(Base):
    """Immutable audit trail of actions, mutations, and decision updates."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    actor_id = Column(String(100), nullable=False)
    actor_email = Column(String(255), nullable=False)
    action = Column(
        String(100), nullable=False
    )  # e.g. 'commit_decision', 'create_ticket', 'redact_source'
    entity_type = Column(String(100), nullable=True)  # e.g. 'Decision', 'Ticket', 'Source'
    entity_id = Column(String(100), nullable=True)
    before_state = Column(Text, nullable=True)
    after_state = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)

    workspace = relationship("Workspace", back_populates="audit_logs")


class AnswerTrace(Base):
    """Execution telemetry and grounded verification trace for an answer."""

    __tablename__ = "answer_traces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources_cited = Column(Text, default="[]", nullable=False)  # JSON array of Source IDs
    validation_status = Column(String(50), default="ok", nullable=False)  # ok | repaired | blocked
    confidence_label = Column(String(50), default="Medium", nullable=False)  # High | Medium | Low
    confidence_score = Column(Float, default=0.8, nullable=False)
    trace_data = Column(Text, default="{}", nullable=False)  # JSON details (tool calls, timings)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)

    feedbacks = relationship("Feedback", back_populates="answer", cascade="all, delete-orphan")


class Feedback(Base):
    """User feedback and rating on an answer."""

    __tablename__ = "feedbacks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_id = Column(String(36), ForeignKey("answer_traces.id"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    rating = Column(Integer, nullable=False)  # +1 (thumbs up) or -1 (thumbs down)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    answer = relationship("AnswerTrace", back_populates="feedbacks")


class IngestionJob(Base):
    """Background ingestion tracking job."""

    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    connector_type = Column(
        String(100), nullable=False
    )  # file_upload | sample_data | watched_folder
    source_uri = Column(String(500), nullable=False)
    status = Column(
        String(50), default="pending", nullable=False
    )  # pending | running | completed | failed
    items_processed = Column(Integer, default=0, nullable=False)
    items_failed = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)


class ReviewItem(Base):
    """Items queued for human-in-the-loop review (e.g. unknown handles, decision reversals)."""

    __tablename__ = "review_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    item_type = Column(
        String(100), nullable=False
    )  # unknown_person | decision_reversal | low_confidence
    status = Column(
        String(50), default="pending", nullable=False
    )  # pending | approved | rejected | edited
    summary = Column(Text, nullable=False)
    payload = Column(Text, default="{}", nullable=False)  # JSON payload
    before_diff = Column(Text, nullable=True)
    after_diff = Column(Text, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)


class ProposedAction(Base):
    """Two-phase safety propose-then-confirm action records."""

    __tablename__ = "proposed_actions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)  # create_ticket | draft_message | assign_task
    status = Column(
        String(50), default="proposed", nullable=False
    )  # proposed | confirmed | cancelled
    payload = Column(Text, default="{}", nullable=False)  # JSON payload
    proposed_by = Column(String(100), nullable=False)
    confirmed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)


# Database engine and session factories
def get_engine():
    """Returns SQLAlchemy engine configured from settings."""
    connect_args = (
        {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
    )
    return create_engine(settings.DATABASE_URL, connect_args=connect_args)


def get_session_factory():
    """Returns sessionmaker bound to current engine."""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_app_db():
    """Creates all relational database tables if they do not exist, ensuring a default workspace."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        default_ws = session.query(Workspace).filter_by(slug="default").first()
        if not default_ws:
            default_ws = Workspace(id="default", slug="default", name="Default Workspace")
            session.add(default_ws)
            session.commit()
