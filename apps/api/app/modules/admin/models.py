"""Admin: notifications, per-tenant channel config and metering, and the jobs table."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScoped
from app.db.types import enum_type


class NotificationKind(StrEnum):
    """Matches the icon/colour switch in src/pages/Notifications.tsx."""

    BOOKING = "booking"
    PAYMENT = "payment"
    ALERT = "alert"
    EQUIPMENT = "equipment"
    MEMBERSHIP = "membership"
    ACADEMY = "academy"
    ADVERTISING = "advertising"


class Channel(StrEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"


class DeliveryState(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class JobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Notification(TenantScoped):
    """An in-app notification. ← the `notifications` array in Notifications.tsx."""

    __tablename__ = "notification"
    __table_args__ = (
        Index("ix_notification_tenant_created", "tenant_id", "created_at"),
        # The unread badge is read on every page load, so it gets its own partial
        # index rather than scanning the whole history to count three rows.
        Index(
            "ix_notification_tenant_unread",
            "tenant_id",
            "created_at",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    kind: Mapped[NotificationKind] = mapped_column(
        enum_type(NotificationKind, name="notification_kind"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    severity_color: Mapped[str | None] = mapped_column(String(9))

    # NULL means the whole academy sees it, which is how the frontend's list behaves.
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationChannelConfig(TenantScoped):
    """Which channels fire for which event. ← Settings → Notifications matrix.

    Per-tenant from the start, because WhatsApp and SMS are real variable costs and
    every academy will want a different mix. One row per event key.
    """

    __tablename__ = "notification_channel_config"
    __table_args__ = (
        Index("uq_notification_channel_tenant_event", "tenant_id", "event_key", unique=True),
    )

    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Negative lead time = after the event; the frontend's "1 hour before booking".
    lead_time_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class NotificationDelivery(TenantScoped):
    """One outbound message, with what it cost.

    The metering the plan asked for. WhatsApp and SMS are billed per message, so
    per-tenant spend has to be attributable from day one — retrofitting it means
    guessing at historical usage when the first invoice arrives.
    """

    __tablename__ = "notification_delivery"
    __table_args__ = (
        # The billing query: spend per channel per month, per academy.
        Index("ix_notification_delivery_tenant_channel", "tenant_id", "channel", "created_at"),
        CheckConstraint("cost >= 0", name="cost_non_negative"),
    )

    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[Channel] = mapped_column(
        enum_type(Channel, name="notification_channel"), nullable=False
    )
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    state: Mapped[DeliveryState] = mapped_column(
        enum_type(DeliveryState, name="notification_delivery_state"),
        default=DeliveryState.QUEUED,
        nullable=False,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    # 4 decimal places: a single SMS is fractions of a rupee, and rounding each one
    # to paise would lose most of the month's bill.
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(TenantScoped):
    """A background task, queued in Postgres.

    Standing in for Celery deliberately: renewal reminders and expiry sweeps are a
    handful of rows a day, and a Redis worker fleet is infrastructure to pay for and
    operate before a single customer has asked for it.

    Claimed with `FOR UPDATE SKIP LOCKED`, so adding a second worker later is safe
    without changing anything here. If the volume ever justifies Celery, this table
    becomes its outbox rather than being thrown away.
    """

    __tablename__ = "job"
    __table_args__ = (
        # The claim query: pending work that is due, oldest first.
        Index(
            "ix_job_tenant_due",
            "tenant_id",
            "run_at",
            postgresql_where=text("state = 'pending'"),
        ),
        CheckConstraint("attempts >= 0 AND max_attempts > 0", name="attempts_sane"),
    )

    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    state: Mapped[JobState] = mapped_column(
        enum_type(JobState, name="job_state"), default=JobState.PENDING, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
