"""Append-only, tenant-scoped audit trail."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScoped
from app.db.types import enum_type


class ActorKind(StrEnum):
    USER = "user"
    PLATFORM_ADMIN = "platform_admin"
    SYSTEM = "system"


class AuditLog(TenantScoped):
    """Who did what, when — cheap now, because enterprise buyers will ask.

    Append-only is enforced by the database, not by convention: the migration
    REVOKEs UPDATE and DELETE on this table from the application role. The API
    physically cannot rewrite history even through a bug or a SQL injection, which
    is the entire value of an audit log. Purging for retention is a migrator-role
    operation, i.e. a deliberate, reviewed act.

    Deliberately not normalised into per-entity tables: it is written on every
    mutation and read rarely, so write cost matters and query flexibility does not.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        # The two access patterns: "what happened at this academy recently" and
        # "what happened to this specific record". Both lead with tenant_id.
        Index("ix_audit_log_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_log_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_audit_log_tenant_actor", "tenant_id", "actor_id"),
    )

    # Nullable: platform admins and cron jobs are not rows in app_user. No FK for
    # the same reason, plus a deleted staff member must not take their audit trail
    # with them.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    actor_kind: Mapped[ActorKind] = mapped_column(
        enum_type(ActorKind, name="audit_actor_kind"), nullable=False
    )
    actor_label: Mapped[str | None] = mapped_column(String(320))  # email at time of action

    action: Mapped[str] = mapped_column(String(100), nullable=False)  # "booking.cancelled"
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))

    # {"before": {...}, "after": {...}} — only the fields that changed.
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    ip_address: Mapped[str | None] = mapped_column(String(45))  # 45 = max IPv6 text length
    user_agent: Mapped[str | None] = mapped_column(Text)

    # How the tenant was resolved for this request: "host" | "header" | "impersonation".
    # When something lands in the wrong academy, this is the field that says why.
    tenant_source: Mapped[str | None] = mapped_column(String(20))

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.actor_label}>"
