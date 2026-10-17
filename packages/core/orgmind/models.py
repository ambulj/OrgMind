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
    ForeignKey,
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
