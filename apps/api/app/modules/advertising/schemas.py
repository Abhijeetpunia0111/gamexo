"""Pydantic schemas for advertising."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.advertising.models import (
    ContractPaymentStatus,
    ContractStatus,
    SpotStatus,
    SpotType,
)

ORM = ConfigDict(from_attributes=True)


class AdSpotBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    zone: str | None = None
    location: str | None = None
    dimensions: str | None = Field(default=None, max_length=64)
    type: SpotType = SpotType.INDOOR
    display_type: str | None = None
    visibility_rating: Decimal = Field(default=Decimal("0"), ge=0, le=10)
    price_monthly: Decimal = Field(default=Decimal("0"), ge=0)
    price_quarterly: Decimal = Field(default=Decimal("0"), ge=0)
    price_yearly: Decimal = Field(default=Decimal("0"), ge=0)
    is_sellable: bool = True
    blocked_status: SpotStatus | None = None
    image: str | None = None
    notes: str | None = None


class AdSpotCreate(AdSpotBase):
    code: str = Field(min_length=1, max_length=32)


class AdSpotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    zone: str | None = None
    location: str | None = None
    dimensions: str | None = None
    type: SpotType | None = None
    display_type: str | None = None
    visibility_rating: Decimal | None = Field(default=None, ge=0, le=10)
    price_monthly: Decimal | None = Field(default=None, ge=0)
    price_quarterly: Decimal | None = Field(default=None, ge=0)
    price_yearly: Decimal | None = Field(default=None, ge=0)
    is_sellable: bool | None = None
    blocked_status: SpotStatus | None = None
    image: str | None = None
    notes: str | None = None


class AdSpotOut(AdSpotBase):
    model_config = ORM
    id: uuid.UUID
    code: str


class AdSpotWithStatus(AdSpotOut):
    """A spot plus the status the Advertising inventory grid renders.

    `status` is derived for the requested date: `maintenance`/`blocked` come from
    the stored flag, `occupied` from a live contract, `reserved` from a confirmed
    future one, and `available` otherwise. Matches the frontend's `SpotStatus` union.
    """

    status: str
    current_contract_id: uuid.UUID | None = None
    occupied_until: date | None = None


class TimelineEvent(BaseModel):
    time: str
    label: str
    type: str = Field(
        description="created | quotation | payment | artwork | installed | started | reminder | ended | renewed"
    )


class AdContractBase(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    brand: str | None = None
    contact_name: str | None = None
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    gst: str | None = Field(default=None, max_length=20)
    deposit: Decimal = Field(default=Decimal("0"), ge=0)
    installation_fee: Decimal = Field(default=Decimal("0"), ge=0)
    printing_fee: Decimal = Field(default=Decimal("0"), ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    remarks: str | None = None


class AdContractCreate(AdContractBase):
    spot_id: uuid.UUID
    start_date: date
    duration_months: int = Field(ge=1, le=120, description="1, 3, 6 or 12 in the UI")
    status: ContractStatus = ContractStatus.QUOTATION


class AdContractUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=200)
    brand: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    gst: str | None = None
    start_date: date | None = None
    duration_months: int | None = Field(default=None, ge=1, le=120)
    deposit: Decimal | None = Field(default=None, ge=0)
    installation_fee: Decimal | None = Field(default=None, ge=0)
    printing_fee: Decimal | None = Field(default=None, ge=0)
    discount: Decimal | None = Field(default=None, ge=0)
    status: ContractStatus | None = None
    remarks: str | None = None


class AdContractOut(AdContractBase):
    model_config = ORM

    id: uuid.UUID
    spot_id: uuid.UUID
    spot_name: str
    zone: str | None
    start_date: date
    end_date: date
    duration_label: str | None
    total: Decimal
    paid: Decimal
    balance_due: Decimal
    status: ContractStatus
    payment_status: ContractPaymentStatus
    timeline: list[dict[str, Any]]


class ContractPayment(BaseModel):
    amount: Decimal = Field(gt=0)
    note: str | None = None


class ContractRenew(BaseModel):
    duration_months: int = Field(ge=1, le=120)


class AdvertisingOverview(BaseModel):
    """The Advertising dashboard's summary cards."""

    total_spots: int
    available_spots: int
    occupied_spots: int
    active_contracts: int
    expiring_soon: int
    contracted_value: Decimal
    collected: Decimal
    outstanding: Decimal
    occupancy_pct: float
