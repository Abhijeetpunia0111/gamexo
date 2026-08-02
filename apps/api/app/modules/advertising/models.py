"""Advertising: sellable ad inventory and the contracts against it."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB, ExcludeConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScoped
from app.db.types import enum_type, money


class SpotStatus(StrEnum):
    """Only `maintenance` and `blocked` are stored.

    `available`, `reserved`, `occupied` and `expired` are derived from contract state
    on a given date — exactly the same treatment as `court.status`, and for the same
    reason: a stored value goes stale the day a campaign starts or ends, and nothing
    is responsible for correcting it.
    """

    MAINTENANCE = "maintenance"
    BLOCKED = "blocked"


class ContractStatus(StrEnum):
    DRAFT = "draft"
    QUOTATION = "quotation"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    RENEWED = "renewed"
    CANCELLED = "cancelled"


# The states in which a contract actually holds the spot. Quotes and drafts do not:
# sending competing proposals for the same hoarding to two advertisers is how the
# sales pipeline works, and blocking that would break it.
HOLDING_STATUSES = (
    ContractStatus.CONFIRMED,
    ContractStatus.ACTIVE,
    ContractStatus.RENEWED,
)


class ContractPaymentStatus(StrEnum):
    PAID = "paid"
    PENDING = "pending"
    PARTIAL = "partial"


class SpotType(StrEnum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


class AdSpot(TenantScoped):
    """A sellable advertising position. ← `AdSpot` in src/pages/Advertising.tsx."""

    __tablename__ = "ad_spot"
    __table_args__ = (
        Index("uq_ad_spot_tenant_code", "tenant_id", "code", unique=True),
        Index("ix_ad_spot_tenant_zone", "tenant_id", "zone"),
        CheckConstraint(
            "visibility_rating >= 0 AND visibility_rating <= 10", name="visibility_in_range"
        ),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)  # "Z1-B01"
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    zone: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(Text)
    dimensions: Mapped[str | None] = mapped_column(String(64))  # "8ft × 4ft", '75" Display'
    type: Mapped[SpotType] = mapped_column(
        enum_type(SpotType, name="ad_spot_type"), default=SpotType.INDOOR, nullable=False
    )
    display_type: Mapped[str | None] = mapped_column(String(64))  # "Vinyl Banner", "LED Display"
    visibility_rating: Mapped[Decimal] = mapped_column(Numeric(3, 1), default=0, nullable=False)

    price_monthly: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    price_quarterly: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    price_yearly: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)

    # Stored state only. See the SpotStatus docstring.
    is_sellable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    blocked_status: Mapped[SpotStatus | None] = mapped_column(
        enum_type(SpotStatus, name="ad_spot_blocked_status")
    )
    image: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<AdSpot {self.code} {self.name}>"


class AdContract(TenantScoped):
    """A sold campaign. ← `AdContract`.

    An ad spot is as double-bookable as a court, and the frontend's own mock data
    already has two future-dated contracts on spots marked reserved. The same
    mechanism prevents it, with one difference: the constraint applies only to
    contracts that actually hold the spot, so overlapping *quotations* to competing
    advertisers remain legal.
    """

    __tablename__ = "ad_contract"
    __table_args__ = (
        ExcludeConstraint(
            ("tenant_id", "="),
            ("spot_id", "="),
            ("period", "&&"),
            name="ad_contract_no_overlap",
            using="gist",
            where=text("status IN ('confirmed', 'active', 'renewed')"),
        ),
        Index("ix_ad_contract_tenant_spot", "tenant_id", "spot_id"),
        Index("ix_ad_contract_tenant_status", "tenant_id", "status"),
        Index("ix_ad_contract_tenant_end", "tenant_id", "end_date"),
        CheckConstraint("end_date >= start_date", name="end_after_start"),
        CheckConstraint("paid >= 0 AND total >= 0", name="amounts_non_negative"),
    )

    spot_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ad_spot.id", ondelete="RESTRICT"), nullable=False
    )
    # Snapshots: a contract records which position was sold under what name, and
    # must not rewrite itself when the spot is renamed or re-zoned.
    spot_name: Mapped[str] = mapped_column(String(150), nullable=False)
    zone: Mapped[str | None] = mapped_column(String(100))

    company: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(150))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    gst: Mapped[str | None] = mapped_column(String(20))

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Generated from the dates, so the two can never disagree. Inclusive on both
    # ends ('[]') because a campaign runs to the close of its last day — unlike a
    # court booking, where the half-open boundary is what allows back-to-back slots.
    period: Mapped[Any] = mapped_column(
        DATERANGE,
        Computed("daterange(start_date, end_date, '[]')", persisted=True),
        nullable=False,
    )
    duration_label: Mapped[str | None] = mapped_column(String(32))  # "6 Months"

    total: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    paid: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    deposit: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    installation_fee: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    printing_fee: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    discount: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)

    status: Mapped[ContractStatus] = mapped_column(
        enum_type(ContractStatus, name="ad_contract_status"),
        default=ContractStatus.DRAFT,
        nullable=False,
    )
    payment_status: Mapped[ContractPaymentStatus] = mapped_column(
        enum_type(ContractPaymentStatus, name="ad_contract_payment_status"),
        default=ContractPaymentStatus.PENDING,
        nullable=False,
    )

    # [{"time": "1 Mar 2024", "label": "Contract Created", "type": "created"}]
    # JSONB per the plan: read as a unit with the contract, never queried across them.
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)

    @property
    def balance_due(self) -> Decimal:
        return self.total - self.paid

    def __repr__(self) -> str:
        return f"<AdContract {self.company} {self.spot_name}>"
