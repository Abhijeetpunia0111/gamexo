"""Booking domain logic. Routers stay thin; everything tenant-aware lives here."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.modules.booking.models import (
    Booking,
    BookingEvent,
    BookingEventKind,
    BookingStatus,
    Court,
    Customer,
    Equipment,
    EquipmentMovement,
    MovementKind,
    Sport,
)
from app.modules.booking.pricing import EquipmentLine, Quote, money, quote_booking, tenant_zone
from app.modules.booking.schemas import EquipmentSelection
from app.models.tenant import TenantSettings


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-") or "sport"


def initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else parts[0][1:2])).upper()


async def load_settings(session: AsyncSession) -> TenantSettings:
    """The current academy's settings. Tenant-scoped, so no filter is needed."""
    result = await session.execute(select(TenantSettings))
    settings = result.scalar_one_or_none()
    if settings is None:
        raise NotFoundError("This academy has no settings row.")
    return settings


async def resolve_equipment_lines(
    session: AsyncSession, selections: Iterable[EquipmentSelection]
) -> tuple[list[EquipmentLine], dict[uuid.UUID, Equipment]]:
    """Turn equipment ids into priced lines, at the rate current right now.

    The rate is captured onto the booking rather than referenced, so re-pricing the
    catalogue tomorrow does not silently rewrite yesterday's bookings and invoices.
    """
    selections = list(selections)
    if not selections:
        return [], {}

    ids = [s.equipment_id for s in selections]
    rows = (await session.execute(select(Equipment).where(Equipment.id.in_(ids)))).scalars().all()
    by_id = {row.id: row for row in rows}

    missing = set(ids) - set(by_id)
    if missing:
        raise NotFoundError(
            "Unknown equipment.", details={"ids": sorted(str(i) for i in missing)}
        )

    lines = [
        EquipmentLine(name=by_id[s.equipment_id].name, qty=s.qty, rate=by_id[s.equipment_id].rental_price)
        for s in selections
    ]
    return lines, by_id


async def price_booking(
    session: AsyncSession,
    *,
    court: Court,
    starts_at: datetime,
    duration_min: int,
    selections: Iterable[EquipmentSelection],
    discount: Decimal,
) -> tuple[Quote, list[EquipmentLine]]:
    settings = await load_settings(session)
    lines, _ = await resolve_equipment_lines(session, selections)
    quote = quote_booking(
        court=court,
        starts_at=starts_at,
        duration_min=duration_min,
        equipment_lines=lines,
        discount=discount,
        booking_rules=settings.booking_rules,
        tax_config=settings.tax_config,
        timezone_name=settings.timezone,
    )
    return quote, lines


def _apply_quote(booking: Booking, quote: Quote, lines: Sequence[EquipmentLine]) -> None:
    booking.court_charge = quote.court_charge
    booking.equipment_charge = quote.equipment_charge
    booking.discount = quote.discount
    booking.taxes = quote.taxes
    booking.total = quote.total
    booking.equipment = [line.as_json() for line in lines]


async def ensure_slot_free(
    session: AsyncSession,
    *,
    court_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_booking_id: uuid.UUID | None = None,
) -> None:
    """Reject an overlapping slot with a message that names the conflict.

    This check is for the *message*, not for the guarantee. Two reception staff
    hitting Confirm at the same instant can both pass this SELECT — that race is
    closed by the `booking_no_overlap` exclusion constraint, which is why the
    constraint exists rather than this function being trusted on its own. If the
    constraint does fire, the IntegrityError handler in core/errors.py still turns
    it into a 409; the caller just gets a blunter message.

    Half-open comparison (`starts < other_end AND ends > other_start`) mirrors the
    constraint's '[)' bounds, so back-to-back bookings are not reported as clashing.
    """
    stmt = select(Booking.id, Booking.customer_name, Booking.starts_at, Booking.ends_at).where(
        Booking.court_id == court_id,
        Booking.status != BookingStatus.CANCELLED,
        Booking.starts_at < ends_at,
        Booking.ends_at > starts_at,
    )
    if exclude_booking_id is not None:
        stmt = stmt.where(Booking.id != exclude_booking_id)

    row = (await session.execute(stmt.limit(1))).first()
    if row is not None:
        raise ConflictError(
            "That court is already booked for part of this time.",
            details={
                "conflicting_booking_id": str(row.id),
                "conflicting_from": row.starts_at.isoformat(),
                "conflicting_to": row.ends_at.isoformat(),
            },
        )


async def record_event(
    session: AsyncSession,
    booking: Booking,
    *,
    kind: BookingEventKind,
    label: str,
    detail: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> BookingEvent:
    event = BookingEvent(
        booking_id=booking.id,
        kind=kind,
        label=label,
        detail=detail,
        actor_user_id=actor_user_id,
    )
    session.add(event)
    return event


async def apply_movement(
    session: AsyncSession,
    equipment: Equipment,
    *,
    kind: MovementKind,
    qty: int,
    booking_id: uuid.UUID | None = None,
    note: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> EquipmentMovement:
    """Move stock between states and record the ledger row, in one transaction.

    The counters on `equipment` and this ledger cannot disagree: the CHECK
    constraint requires them to balance, so an incorrect transition fails the write
    rather than quietly corrupting the inventory.
    """
    transitions = {
        MovementKind.ISSUE: ("qty_available", "qty_issued"),
        MovementKind.RETURN: ("qty_issued", "qty_available"),
        MovementKind.TO_MAINTENANCE: ("qty_available", "qty_maintenance"),
        MovementKind.FROM_MAINTENANCE: ("qty_maintenance", "qty_available"),
        MovementKind.LOST: ("qty_issued", "qty_lost"),
    }

    if kind is MovementKind.RESTOCK:
        equipment.qty_stock += qty
        equipment.qty_available += qty
    elif kind is MovementKind.ADJUST:
        equipment.qty_stock += qty
        equipment.qty_available += qty
    elif kind is MovementKind.WRITE_OFF:
        # Stock removed straight off the shelf — damage found on a stocktake,
        # a manual correction, anything that never went out issued to begin
        # with. The inverse of RESTOCK: both counters drop together.
        if equipment.qty_available < qty:
            raise ConflictError(
                f"Only {equipment.qty_available} unit(s) of {equipment.name} are available to write off.",
                details={"equipment_id": str(equipment.id), "requested": qty},
            )
        equipment.qty_stock -= qty
        equipment.qty_available -= qty
    else:
        source, target = transitions[kind]
        if getattr(equipment, source) < qty:
            raise ConflictError(
                f"Only {getattr(equipment, source)} unit(s) of {equipment.name} are in "
                f"'{source.removeprefix('qty_')}' state.",
                details={"equipment_id": str(equipment.id), "requested": qty},
            )
        setattr(equipment, source, getattr(equipment, source) - qty)
        setattr(equipment, target, getattr(equipment, target) + qty)

    movement = EquipmentMovement(
        equipment_id=equipment.id,
        booking_id=booking_id,
        kind=kind,
        qty=qty,
        note=note,
        actor_user_id=actor_user_id,
    )
    session.add(movement)
    return movement


async def resolve_customer(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID | None,
    customer_name: str | None,
    customer_phone: str | None,
) -> tuple[uuid.UUID | None, str, str | None]:
    """Return (customer_id, name, phone) for a booking.

    Walk-ins are often anonymous — someone turns up and pays cash — so a booking may
    carry a name and phone with no customer row behind it.
    """
    if customer_id is not None:
        customer = await session.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.", details={"id": str(customer_id)})
        return customer.id, customer.name, customer.phone
    return None, (customer_name or "").strip(), customer_phone


# ── Availability ────────────────────────────────────────────────────────────


def _day_bounds(day: datetime, hours: dict[str, str], tz) -> tuple[datetime, datetime]:
    def parse(value: str, fallback: time) -> time:
        try:
            h, _, m = value.partition(":")
            return time(int(h), int(m or 0))
        except (ValueError, TypeError):
            return fallback

    local_day = day.astimezone(tz).date()
    opens = parse(str(hours.get("open", "06:00")), time(6, 0))
    closes = parse(str(hours.get("close", "22:00")), time(22, 0))

    start = datetime.combine(local_day, opens, tzinfo=tz)
    end = datetime.combine(local_day, closes, tzinfo=tz)
    if end <= start:  # closing after midnight
        end += timedelta(days=1)
    return start, end


async def court_availability(
    session: AsyncSession,
    *,
    on_date: datetime,
    duration_min: int,
    sport_id: uuid.UUID | None = None,
    court_id: uuid.UUID | None = None,
    slot_minutes: int = 60,
) -> list[dict]:
    """Which slots are free on a given day.

    Bookings are fetched once for the whole day and matched in memory rather than
    issuing a query per slot: a 16-hour day at 60-minute granularity across 8 courts
    is 128 slots, and 128 round trips is a slow endpoint for no benefit.
    """
    settings = await load_settings(session)
    tz = tenant_zone(settings.timezone)

    court_stmt = select(Court, Sport.name).join(Sport, Court.sport_id == Sport.id)
    if sport_id is not None:
        court_stmt = court_stmt.where(Court.sport_id == sport_id)
    if court_id is not None:
        court_stmt = court_stmt.where(Court.id == court_id)
    court_rows = (await session.execute(court_stmt.order_by(Court.name))).all()

    if not court_rows:
        return []

    day_start, day_end = _day_bounds(on_date, {"open": "00:00", "close": "00:00"}, tz)
    day_start = datetime.combine(on_date.astimezone(tz).date(), time(0, 0), tzinfo=tz)
    day_end = day_start + timedelta(days=1)

    bookings = (
        (
            await session.execute(
                select(Booking).where(
                    Booking.status != BookingStatus.CANCELLED,
                    Booking.starts_at < day_end,
                    Booking.ends_at > day_start,
                )
            )
        )
        .scalars()
        .all()
    )
    by_court: dict[uuid.UUID, list[Booking]] = {}
    for booking in bookings:
        by_court.setdefault(booking.court_id, []).append(booking)

    from app.modules.booking.pricing import is_peak_slot, is_weekend

    results: list[dict] = []
    for court, _sport_name in court_rows:
        opens, closes = _day_bounds(on_date, court.operating_hours, tz)
        taken = by_court.get(court.id, [])

        slots = []
        cursor = opens
        step = timedelta(minutes=slot_minutes)
        length = timedelta(minutes=duration_min)

        while cursor + length <= closes:
            slot_end = cursor + length
            # Half-open comparison, matching the exclusion constraint's '[)' bounds,
            # so a slot starting exactly when another booking ends reads as free.
            blocker = next(
                (b for b in taken if b.starts_at < slot_end and b.ends_at > cursor), None
            )
            peak = is_peak_slot(cursor, settings.booking_rules, tz)
            weekend = is_weekend(cursor, tz)
            slots.append(
                {
                    "starts_at": cursor,
                    "ends_at": slot_end,
                    "available": blocker is None and court.is_bookable,
                    "rate": money(court.peak_rate if (peak or weekend) else court.hourly_rate),
                    "is_peak": peak or weekend,
                    "blocked_by_booking_id": blocker.id if blocker else None,
                }
            )
            cursor += step

        results.append(
            {
                "court_id": court.id,
                "court_name": court.name,
                "court_code": court.code,
                "sport_id": court.sport_id,
                "is_bookable": court.is_bookable,
                "maintenance_note": court.maintenance_note,
                "slots": slots,
            }
        )

    return results


async def court_status_at(
    session: AsyncSession, at: datetime
) -> dict[uuid.UUID, tuple[str, uuid.UUID | None]]:
    """Derive each court's live status — the field the frontend stores on Court.

    `maintenance` comes from the stored `is_bookable` flag; `occupied` is computed
    from whatever booking spans `at`. Storing `occupied` would mean something had to
    remember to clear it when the session ended.
    """
    courts = (await session.execute(select(Court))).scalars().all()
    active = (
        (
            await session.execute(
                select(Booking).where(
                    Booking.status.notin_([BookingStatus.CANCELLED, BookingStatus.COMPLETED]),
                    Booking.starts_at <= at,
                    Booking.ends_at > at,
                )
            )
        )
        .scalars()
        .all()
    )
    occupied = {b.court_id: b.id for b in active}

    status: dict[uuid.UUID, tuple[str, uuid.UUID | None]] = {}
    for court in courts:
        if not court.is_bookable:
            status[court.id] = ("maintenance", None)
        elif court.id in occupied:
            status[court.id] = ("occupied", occupied[court.id])
        else:
            status[court.id] = ("available", None)
    return status


async def max_extension_minutes(
    session: AsyncSession, booking: Booking, *, limit_minutes: int = 480
) -> int:
    """How far a live booking can run on before it meets the next one.

    The Extend flow needs to offer a realistic maximum rather than let staff pick
    +2h and be rejected — the frontend explicitly asks to "suggest the maximum
    available extension".
    """
    next_booking = await session.execute(
        select(Booking.starts_at)
        .where(
            Booking.court_id == booking.court_id,
            Booking.id != booking.id,
            Booking.status != BookingStatus.CANCELLED,
            Booking.starts_at >= booking.ends_at,
        )
        .order_by(Booking.starts_at)
        .limit(1)
    )
    boundary = next_booking.scalar_one_or_none()
    if boundary is None:
        return limit_minutes
    gap = int((boundary - booking.ends_at).total_seconds() // 60)
    return max(0, min(gap, limit_minutes))


async def customer_rollups(
    session: AsyncSession, customer_id: uuid.UUID
) -> tuple[int, Decimal, Decimal]:
    """(total_bookings, total_spent, outstanding_dues), computed not stored."""
    from sqlalchemy import func

    row = (
        await session.execute(
            select(
                func.count(Booking.id),
                func.coalesce(func.sum(Booking.amount_paid), 0),
                func.coalesce(func.sum(Booking.total - Booking.amount_paid), 0),
            ).where(
                Booking.customer_id == customer_id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )
    ).one()
    return int(row[0]), money(row[1]), money(max(Decimal("0"), row[2]))
