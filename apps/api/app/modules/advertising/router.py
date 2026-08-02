"""Advertising endpoints: inventory, contracts, the sales pipeline."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api_utils import Page, Params, get_or_404, paginate
from app.auth.deps import RequireManager, RequireStaff
from app.core.errors import ConflictError
from app.modules.advertising.models import (
    HOLDING_STATUSES,
    AdContract,
    AdSpot,
    ContractPaymentStatus,
    ContractStatus,
)
from app.modules.advertising.schemas import (
    AdContractCreate,
    AdContractOut,
    AdContractUpdate,
    AdSpotCreate,
    AdSpotOut,
    AdSpotUpdate,
    AdSpotWithStatus,
    AdvertisingOverview,
    ContractPayment,
    ContractRenew,
)
from app.modules.booking.pricing import money, percent
from app.modules.finance.service import add_months
from app.tenancy.deps import Db

router = APIRouter(prefix="/advertising", tags=["advertising"])

DURATION_LABELS = {1: "1 Month", 3: "3 Months", 6: "6 Months", 12: "12 Months"}


def _price_for(spot: AdSpot, months: int) -> Decimal:
    """Price a term from the spot's rate card.

    Quarterly and yearly rates are discounted in the frontend's own data, so a
    12-month deal uses the yearly price rather than twelve monthlies — charging
    12 × monthly would quietly overcharge every annual advertiser.
    """
    if months >= 12:
        years, remainder = divmod(months, 12)
        return money(spot.price_yearly * years + spot.price_monthly * remainder)
    if months >= 3:
        quarters, remainder = divmod(months, 3)
        return money(spot.price_quarterly * quarters + spot.price_monthly * remainder)
    return money(spot.price_monthly * months)


def _timeline_entry(label: str, kind: str) -> dict:
    return {"time": date.today().strftime("%-d %b %Y"), "label": label, "type": kind}


def _refresh_payment_status(contract: AdContract) -> None:
    if contract.paid <= 0:
        contract.payment_status = ContractPaymentStatus.PENDING
    elif contract.paid < contract.total:
        contract.payment_status = ContractPaymentStatus.PARTIAL
    else:
        contract.payment_status = ContractPaymentStatus.PAID


def _out(contract: AdContract) -> AdContractOut:
    return AdContractOut.model_validate(contract)


# ── Inventory ───────────────────────────────────────────────────────────────


@router.get(
    "/spots",
    response_model=list[AdSpotWithStatus],
    summary="Ad inventory with derived status",
    description=(
        "`status` is computed for `on_date` from contract state — only "
        "`maintenance` and `blocked` are stored. A stored `occupied` goes stale the "
        "day a campaign ends."
    ),
)
async def list_spots(
    db: Db,
    _: RequireStaff,
    zone: str | None = None,
    on_date: Annotated[date | None, Query(description="Defaults to today")] = None,
) -> list[AdSpotWithStatus]:
    today = on_date or date.today()

    stmt = select(AdSpot).order_by(AdSpot.code)
    if zone:
        stmt = stmt.where(AdSpot.zone == zone)
    spots = (await db.execute(stmt)).scalars().all()

    contracts = (
        (
            await db.execute(
                select(AdContract).where(
                    AdContract.status.in_(HOLDING_STATUSES),
                    AdContract.end_date >= today,
                )
            )
        )
        .scalars()
        .all()
    )

    live: dict[uuid.UUID, AdContract] = {}
    future: dict[uuid.UUID, AdContract] = {}
    for contract in contracts:
        if contract.start_date <= today <= contract.end_date:
            live[contract.spot_id] = contract
        elif contract.start_date > today:
            future.setdefault(contract.spot_id, contract)

    out: list[AdSpotWithStatus] = []
    for spot in spots:
        base = AdSpotOut.model_validate(spot).model_dump()
        if not spot.is_sellable:
            state = (spot.blocked_status.value if spot.blocked_status else "blocked")
            out.append(AdSpotWithStatus(**base, status=state))
        elif spot.id in live:
            contract = live[spot.id]
            out.append(
                AdSpotWithStatus(
                    **base,
                    status="occupied",
                    current_contract_id=contract.id,
                    occupied_until=contract.end_date,
                )
            )
        elif spot.id in future:
            contract = future[spot.id]
            out.append(
                AdSpotWithStatus(
                    **base,
                    status="reserved",
                    current_contract_id=contract.id,
                    occupied_until=contract.end_date,
                )
            )
        else:
            out.append(AdSpotWithStatus(**base, status="available"))
    return out


@router.post(
    "/spots", response_model=AdSpotOut, status_code=status.HTTP_201_CREATED, summary="Add an ad spot"
)
async def create_spot(payload: AdSpotCreate, db: Db, _: RequireManager) -> AdSpotOut:
    spot = AdSpot(**payload.model_dump())
    db.add(spot)
    await db.flush()
    return AdSpotOut.model_validate(spot)


@router.patch("/spots/{spot_id}", response_model=AdSpotOut, summary="Update an ad spot")
async def update_spot(
    spot_id: uuid.UUID, payload: AdSpotUpdate, db: Db, _: RequireManager
) -> AdSpotOut:
    spot = await get_or_404(db, AdSpot, spot_id, label="Ad spot")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(spot, field, value)
    await db.flush()
    return AdSpotOut.model_validate(spot)


# ── Contracts ───────────────────────────────────────────────────────────────


@router.get("/contracts", response_model=Page[AdContractOut], summary="List contracts")
async def list_contracts(
    db: Db,
    _: RequireStaff,
    params: Params,
    contract_status: Annotated[ContractStatus | None, Query(alias="status")] = None,
    spot_id: uuid.UUID | None = None,
    expiring_within_days: int | None = Query(default=None, ge=1, le=365),
    search: str | None = None,
) -> Page[AdContractOut]:
    stmt = select(AdContract).order_by(AdContract.start_date.desc())
    if contract_status is not None:
        stmt = stmt.where(AdContract.status == contract_status)
    if spot_id is not None:
        stmt = stmt.where(AdContract.spot_id == spot_id)
    if expiring_within_days is not None:
        stmt = stmt.where(
            AdContract.status.in_(HOLDING_STATUSES),
            AdContract.end_date <= date.today() + timedelta(days=expiring_within_days),
            AdContract.end_date >= date.today(),
        )
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(AdContract.company.ilike(like) | AdContract.brand.ilike(like))
    return await paginate(db, stmt, params, AdContractOut)


@router.post(
    "/contracts",
    response_model=AdContractOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a contract or quotation",
    description=(
        "Two overlapping **quotations** for the same spot are allowed — sending "
        "competing proposals is how the pipeline works. Two overlapping *confirmed* "
        "contracts are refused with **409**, enforced by a GiST exclusion constraint."
    ),
)
async def create_contract(
    payload: AdContractCreate, db: Db, _: RequireStaff
) -> AdContractOut:
    spot = await get_or_404(db, AdSpot, payload.spot_id, label="Ad spot")
    if not spot.is_sellable:
        raise ConflictError(f"{spot.name} is not currently sellable.")

    end_date = add_months(payload.start_date, payload.duration_months) - timedelta(days=1)

    if payload.status in HOLDING_STATUSES:
        await _ensure_spot_free(db, spot.id, payload.start_date, end_date)

    base = _price_for(spot, payload.duration_months)
    total = money(
        base
        - payload.discount
        + payload.installation_fee
        + payload.printing_fee
    )

    contract = AdContract(
        **payload.model_dump(exclude={"spot_id", "duration_months", "start_date", "status", "email"}),
        email=str(payload.email) if payload.email else None,
        spot_id=spot.id,
        spot_name=spot.name,
        zone=spot.zone,
        start_date=payload.start_date,
        end_date=end_date,
        duration_label=DURATION_LABELS.get(payload.duration_months, f"{payload.duration_months} Months"),
        total=total,
        status=payload.status,
        timeline=[_timeline_entry("Contract Created", "created")],
    )
    db.add(contract)
    await db.flush()
    return _out(contract)


async def _ensure_spot_free(
    db,
    spot_id: uuid.UUID,
    start_date: date,
    end_date: date,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Reject an overlapping campaign with a message naming the conflict.

    As with bookings, this is for the message; the exclusion constraint is the
    guarantee under concurrency.
    """
    stmt = select(AdContract).where(
        AdContract.spot_id == spot_id,
        AdContract.status.in_(HOLDING_STATUSES),
        AdContract.start_date <= end_date,
        AdContract.end_date >= start_date,
    )
    if exclude_id is not None:
        stmt = stmt.where(AdContract.id != exclude_id)

    clash = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if clash is not None:
        raise ConflictError(
            f"That spot is already booked by {clash.company} for part of this period.",
            details={
                "conflicting_contract_id": str(clash.id),
                "conflicting_from": clash.start_date.isoformat(),
                "conflicting_to": clash.end_date.isoformat(),
            },
        )


@router.get("/contracts/{contract_id}", response_model=AdContractOut, summary="A contract")
async def get_contract(contract_id: uuid.UUID, db: Db, _: RequireStaff) -> AdContractOut:
    return _out(await get_or_404(db, AdContract, contract_id, label="Contract"))


@router.patch(
    "/contracts/{contract_id}",
    response_model=AdContractOut,
    summary="Update a contract",
    description="Moving a quotation to `confirmed` is where the spot conflict is checked.",
)
async def update_contract(
    contract_id: uuid.UUID, payload: AdContractUpdate, db: Db, _: RequireStaff
) -> AdContractOut:
    contract = await get_or_404(db, AdContract, contract_id, label="Contract")
    updates = payload.model_dump(exclude_unset=True, exclude={"duration_months"})
    if "email" in updates and updates["email"] is not None:
        updates["email"] = str(updates["email"])

    start_date = updates.get("start_date", contract.start_date)
    if payload.duration_months is not None:
        end_date = add_months(start_date, payload.duration_months) - timedelta(days=1)
        contract.duration_label = DURATION_LABELS.get(
            payload.duration_months, f"{payload.duration_months} Months"
        )
    elif "start_date" in updates:
        span = (contract.end_date - contract.start_date).days
        end_date = start_date + timedelta(days=span)
    else:
        end_date = contract.end_date

    new_status = updates.get("status", contract.status)
    if new_status in HOLDING_STATUSES:
        await _ensure_spot_free(db, contract.spot_id, start_date, end_date, exclude_id=contract.id)

    # Captured before the loop below assigns it — comparing afterwards would always
    # find the two equal and never record the pipeline transition.
    previous_status = contract.status

    for field, value in updates.items():
        setattr(contract, field, value)
    contract.start_date = start_date
    contract.end_date = end_date

    if payload.status is not None and payload.status != previous_status:
        contract.timeline = [
            *contract.timeline,
            _timeline_entry(f"Status → {payload.status.value}", payload.status.value),
        ]

    await db.flush()
    return _out(contract)


@router.post(
    "/contracts/{contract_id}/payments",
    response_model=AdContractOut,
    summary="Record a contract payment",
)
async def record_contract_payment(
    contract_id: uuid.UUID, payload: ContractPayment, db: Db, _: RequireStaff
) -> AdContractOut:
    contract = await get_or_404(db, AdContract, contract_id, label="Contract")
    if payload.amount > contract.balance_due:
        raise ConflictError(
            f"That is more than the outstanding balance of {contract.balance_due}.",
            details={"balance_due": str(contract.balance_due)},
        )

    contract.paid = money(contract.paid + payload.amount)
    _refresh_payment_status(contract)
    contract.timeline = [
        *contract.timeline,
        _timeline_entry(f"Payment Received · ₹{payload.amount:,.0f}", "payment"),
    ]
    await db.flush()
    return _out(contract)


@router.post(
    "/contracts/{contract_id}/renew",
    response_model=AdContractOut,
    status_code=status.HTTP_201_CREATED,
    summary="Renew a contract",
    description="Marks the old contract `renewed` and creates the follow-on term.",
)
async def renew_contract(
    contract_id: uuid.UUID, payload: ContractRenew, db: Db, _: RequireStaff
) -> AdContractOut:
    contract = await get_or_404(db, AdContract, contract_id, label="Contract")
    spot = await get_or_404(db, AdSpot, contract.spot_id, label="Ad spot")

    start_date = contract.end_date + timedelta(days=1)
    end_date = add_months(start_date, payload.duration_months) - timedelta(days=1)
    await _ensure_spot_free(db, spot.id, start_date, end_date)

    # The old term must stop holding the spot before the new one takes it, or the
    # exclusion constraint sees two holding contracts touching at the boundary.
    contract.status = ContractStatus.RENEWED
    contract.timeline = [*contract.timeline, _timeline_entry("Contract Renewed", "renewed")]

    successor = AdContract(
        spot_id=spot.id,
        spot_name=spot.name,
        zone=spot.zone,
        company=contract.company,
        brand=contract.brand,
        contact_name=contract.contact_name,
        phone=contract.phone,
        email=contract.email,
        gst=contract.gst,
        start_date=start_date,
        end_date=end_date,
        duration_label=DURATION_LABELS.get(
            payload.duration_months, f"{payload.duration_months} Months"
        ),
        total=_price_for(spot, payload.duration_months),
        deposit=contract.deposit,
        status=ContractStatus.CONFIRMED,
        timeline=[_timeline_entry("Renewal Created", "renewed")],
    )
    db.add(successor)
    await db.flush()
    return _out(successor)


@router.get(
    "/overview", response_model=AdvertisingOverview, summary="Advertising dashboard summary"
)
async def advertising_overview(db: Db, _: RequireStaff) -> AdvertisingOverview:
    today = date.today()

    total_spots = int(await db.scalar(select(func.count(AdSpot.id))) or 0)
    occupied = int(
        await db.scalar(
            select(func.count(func.distinct(AdContract.spot_id))).where(
                AdContract.status.in_(HOLDING_STATUSES),
                AdContract.start_date <= today,
                AdContract.end_date >= today,
            )
        )
        or 0
    )
    active_contracts = int(
        await db.scalar(
            select(func.count(AdContract.id)).where(AdContract.status.in_(HOLDING_STATUSES))
        )
        or 0
    )
    expiring = int(
        await db.scalar(
            select(func.count(AdContract.id)).where(
                AdContract.status.in_(HOLDING_STATUSES),
                AdContract.end_date.between(today, today + timedelta(days=30)),
            )
        )
        or 0
    )
    contracted = await db.scalar(
        select(func.coalesce(func.sum(AdContract.total), 0)).where(
            AdContract.status.in_(HOLDING_STATUSES)
        )
    )
    collected = await db.scalar(
        select(func.coalesce(func.sum(AdContract.paid), 0)).where(
            AdContract.status.in_(HOLDING_STATUSES)
        )
    )

    return AdvertisingOverview(
        total_spots=total_spots,
        available_spots=max(0, total_spots - occupied),
        occupied_spots=occupied,
        active_contracts=active_contracts,
        expiring_soon=expiring,
        contracted_value=money(contracted or 0),
        collected=money(collected or 0),
        outstanding=money((contracted or 0) - (collected or 0)),
        occupancy_pct=percent(occupied / total_spots * 100) if total_spots else 0.0,
    )
