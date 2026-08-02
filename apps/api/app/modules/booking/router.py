"""Booking domain endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api_utils import Page, Params, get_or_404, paginate
from app.auth.deps import RequireManager, RequireStaff
from app.core.errors import ConflictError, NotFoundError
from app.modules.booking import service
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
from app.modules.booking.pricing import money
from app.modules.booking.schemas import (
    BookingCancel,
    BookingCreate,
    BookingDetail,
    BookingEventOut,
    BookingExtend,
    BookingOut,
    BookingUpdate,
    CourtAvailability,
    CourtCreate,
    CourtOut,
    CourtUpdate,
    CourtWithStatus,
    CustomerCreate,
    CustomerDetail,
    CustomerOut,
    CustomerUpdate,
    EquipmentCreate,
    EquipmentOut,
    EquipmentUpdate,
    MovementCreate,
    MovementOut,
    QuoteOut,
    QuoteRequest,
    SportCreate,
    SportOut,
    SportUpdate,
)
from app.tenancy.deps import Db

router = APIRouter(tags=["booking"])


# ── Sports ──────────────────────────────────────────────────────────────────


@router.get("/sports", response_model=list[SportOut], summary="List sports")
async def list_sports(db: Db, _: RequireStaff, include_inactive: bool = False) -> list[SportOut]:
    stmt = select(Sport).order_by(Sport.display_order, Sport.name)
    if not include_inactive:
        stmt = stmt.where(Sport.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return [SportOut.model_validate(row) for row in rows]


@router.post("/sports", response_model=SportOut, status_code=status.HTTP_201_CREATED, summary="Add a sport")
async def create_sport(payload: SportCreate, db: Db, _: RequireManager) -> SportOut:
    data = payload.model_dump(exclude={"slug"})
    sport = Sport(**data, slug=payload.slug or service.slugify(payload.name))
    db.add(sport)
    await db.flush()
    return SportOut.model_validate(sport)


@router.patch("/sports/{sport_id}", response_model=SportOut, summary="Update a sport")
async def update_sport(
    sport_id: uuid.UUID, payload: SportUpdate, db: Db, _: RequireManager
) -> SportOut:
    sport = await get_or_404(db, Sport, sport_id, label="Sport")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sport, field, value)
    await db.flush()
    return SportOut.model_validate(sport)


# ── Courts ──────────────────────────────────────────────────────────────────


@router.get(
    "/courts",
    response_model=list[CourtWithStatus],
    summary="List courts with their live status",
    description=(
        "`status` is derived at request time from bookings and the maintenance flag, "
        "not stored — a stored status goes stale the moment a session ends."
    ),
)
async def list_courts(
    db: Db,
    _: RequireStaff,
    sport_id: uuid.UUID | None = None,
    at: datetime | None = Query(default=None, description="Defaults to now"),
) -> list[CourtWithStatus]:
    moment = at or datetime.now(UTC)
    statuses = await service.court_status_at(db, moment)

    stmt = select(Court, Sport.name).join(Sport, Court.sport_id == Sport.id)
    if sport_id is not None:
        stmt = stmt.where(Court.sport_id == sport_id)
    rows = (await db.execute(stmt.order_by(Court.name))).all()

    out: list[CourtWithStatus] = []
    for court, sport_name in rows:
        state, booking_id = statuses.get(court.id, ("available", None))
        out.append(
            CourtWithStatus(
                **CourtOut.model_validate(court).model_dump(),
                status=state,
                current_booking_id=booking_id,
                sport_name=sport_name,
            )
        )
    return out


@router.post("/courts", response_model=CourtOut, status_code=status.HTTP_201_CREATED, summary="Add a court")
async def create_court(payload: CourtCreate, db: Db, _: RequireManager) -> CourtOut:
    await get_or_404(db, Sport, payload.sport_id, label="Sport")
    data = payload.model_dump()
    data["operating_hours"] = payload.operating_hours.model_dump()
    court = Court(**data)
    db.add(court)
    await db.flush()
    return CourtOut.model_validate(court)


@router.patch("/courts/{court_id}", response_model=CourtOut, summary="Update a court")
async def update_court(
    court_id: uuid.UUID, payload: CourtUpdate, db: Db, _: RequireManager
) -> CourtOut:
    court = await get_or_404(db, Court, court_id, label="Court")
    updates = payload.model_dump(exclude_unset=True)
    if "operating_hours" in updates and payload.operating_hours is not None:
        updates["operating_hours"] = payload.operating_hours.model_dump()
    for field, value in updates.items():
        setattr(court, field, value)
    await db.flush()
    return CourtOut.model_validate(court)


@router.get(
    "/courts/availability",
    response_model=list[CourtAvailability],
    summary="Free slots for a day",
    description=(
        "Slot boundaries use half-open comparison, matching the booking exclusion "
        "constraint, so a slot starting exactly when another booking ends is free."
    ),
)
async def availability(
    db: Db,
    _: RequireStaff,
    date: Annotated[datetime, Query(description="Any instant on the target day")],
    duration_min: Annotated[int, Query(ge=15, le=1440)] = 60,
    sport_id: uuid.UUID | None = None,
    court_id: uuid.UUID | None = None,
    slot_minutes: Annotated[int, Query(ge=15, le=240)] = 60,
) -> list[CourtAvailability]:
    rows = await service.court_availability(
        db,
        on_date=date,
        duration_min=duration_min,
        sport_id=sport_id,
        court_id=court_id,
        slot_minutes=slot_minutes,
    )
    return [CourtAvailability.model_validate(row) for row in rows]


# ── Equipment ───────────────────────────────────────────────────────────────


@router.get("/equipment", response_model=Page[EquipmentOut], summary="List equipment")
async def list_equipment(
    db: Db,
    _: RequireStaff,
    params: Params,
    category: str | None = None,
    low_stock_only: bool = False,
) -> Page[EquipmentOut]:
    stmt = select(Equipment).order_by(Equipment.category, Equipment.name)
    if category:
        stmt = stmt.where(Equipment.category == category)
    if low_stock_only:
        stmt = stmt.where(Equipment.qty_available <= Equipment.low_stock_threshold)
    return await paginate(db, stmt, params, EquipmentOut)


@router.post(
    "/equipment",
    response_model=EquipmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add equipment",
)
async def create_equipment(payload: EquipmentCreate, db: Db, _: RequireManager) -> EquipmentOut:
    item = Equipment(
        **payload.model_dump(exclude={"qty_stock"}),
        qty_stock=payload.qty_stock,
        qty_available=payload.qty_stock,
    )
    db.add(item)
    await db.flush()
    return EquipmentOut.model_validate(item)


@router.patch("/equipment/{equipment_id}", response_model=EquipmentOut, summary="Update equipment")
async def update_equipment(
    equipment_id: uuid.UUID, payload: EquipmentUpdate, db: Db, _: RequireManager
) -> EquipmentOut:
    item = await get_or_404(db, Equipment, equipment_id, label="Equipment")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.flush()
    return EquipmentOut.model_validate(item)


@router.post(
    "/equipment/{equipment_id}/movements",
    response_model=MovementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Move stock between states",
    description=(
        "Issue, return, send to maintenance, write off or restock. The ledger row "
        "and the counters on the equipment are written in one transaction, and a "
        "CHECK constraint requires them to balance."
    ),
)
async def create_movement(
    equipment_id: uuid.UUID, payload: MovementCreate, db: Db, principal: RequireStaff
) -> MovementOut:
    item = await get_or_404(db, Equipment, equipment_id, label="Equipment")
    movement = await service.apply_movement(
        db,
        item,
        kind=payload.kind,
        qty=payload.qty,
        booking_id=payload.booking_id,
        note=payload.note,
        actor_user_id=principal.id,
    )
    await db.flush()
    return MovementOut.model_validate(movement)


@router.get(
    "/equipment/{equipment_id}/movements",
    response_model=Page[MovementOut],
    summary="Equipment movement history",
)
async def list_movements(
    equipment_id: uuid.UUID, db: Db, _: RequireStaff, params: Params
) -> Page[MovementOut]:
    await get_or_404(db, Equipment, equipment_id, label="Equipment")
    stmt = (
        select(EquipmentMovement)
        .where(EquipmentMovement.equipment_id == equipment_id)
        .order_by(EquipmentMovement.occurred_at.desc())
    )
    return await paginate(db, stmt, params, MovementOut)


# ── Customers ───────────────────────────────────────────────────────────────


@router.get("/customers", response_model=Page[CustomerOut], summary="List customers")
async def list_customers(
    db: Db,
    _: RequireStaff,
    params: Params,
    search: str | None = Query(default=None, description="Matches name, phone or email"),
    member_type: str | None = None,
) -> Page[CustomerOut]:
    stmt = select(Customer).order_by(Customer.name)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            Customer.name.ilike(like) | Customer.phone.ilike(like) | Customer.email.ilike(like)
        )
    if member_type:
        stmt = stmt.where(Customer.member_type == member_type)
    return await paginate(db, stmt, params, CustomerOut)


@router.post(
    "/customers",
    response_model=CustomerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a customer",
)
async def create_customer(payload: CustomerCreate, db: Db, _: RequireStaff) -> CustomerOut:
    customer = Customer(
        **payload.model_dump(exclude={"email"}),
        email=str(payload.email) if payload.email else None,
        avatar_initials=service.initials(payload.name),
    )
    db.add(customer)
    await db.flush()
    return CustomerOut.model_validate(customer)


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerDetail,
    summary="A customer with their booking rollups",
)
async def get_customer(customer_id: uuid.UUID, db: Db, _: RequireStaff) -> CustomerDetail:
    customer = await get_or_404(db, Customer, customer_id, label="Customer")
    total_bookings, total_spent, dues = await service.customer_rollups(db, customer_id)

    favorite = None
    if customer.favorite_sport_id:
        sport = await db.get(Sport, customer.favorite_sport_id)
        favorite = sport.name if sport else None

    return CustomerDetail(
        **CustomerOut.model_validate(customer).model_dump(),
        total_bookings=total_bookings,
        total_spent=total_spent,
        outstanding_dues=dues,
        favorite_sport=favorite,
    )


@router.patch("/customers/{customer_id}", response_model=CustomerOut, summary="Update a customer")
async def update_customer(
    customer_id: uuid.UUID, payload: CustomerUpdate, db: Db, _: RequireStaff
) -> CustomerOut:
    customer = await get_or_404(db, Customer, customer_id, label="Customer")
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        updates["email"] = str(updates["email"])
    for field, value in updates.items():
        setattr(customer, field, value)
    if "name" in updates:
        customer.avatar_initials = service.initials(customer.name)
    await db.flush()
    return CustomerOut.model_validate(customer)


# ── Bookings ────────────────────────────────────────────────────────────────


@router.post(
    "/bookings/quote",
    response_model=QuoteOut,
    summary="Price a booking without creating it",
    description="Backs the walk-in wizard's live summary, so the quote and the booking agree.",
)
async def quote(payload: QuoteRequest, db: Db, _: RequireStaff) -> QuoteOut:
    court = await get_or_404(db, Court, payload.court_id, label="Court")
    result, lines = await service.price_booking(
        db,
        court=court,
        starts_at=payload.starts_at,
        duration_min=payload.duration_min,
        selections=payload.equipment,
        discount=payload.discount,
    )
    return QuoteOut(
        court_charge=result.court_charge,
        equipment_charge=result.equipment_charge,
        discount=result.discount,
        taxes=result.taxes,
        total=result.total,
        is_peak=result.is_peak,
        is_weekend=result.is_weekend,
        rate_applied=result.rate_applied,
        equipment=[{"name": l.name, "qty": l.qty, "rate": l.rate} for l in lines],
    )


@router.get("/bookings", response_model=Page[BookingOut], summary="List bookings")
async def list_bookings(
    db: Db,
    _: RequireStaff,
    params: Params,
    booking_status: Annotated[BookingStatus | None, Query(alias="status")] = None,
    court_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> Page[BookingOut]:
    stmt = select(Booking).order_by(Booking.starts_at.desc())
    if booking_status is not None:
        stmt = stmt.where(Booking.status == booking_status)
    if court_id is not None:
        stmt = stmt.where(Booking.court_id == court_id)
    if customer_id is not None:
        stmt = stmt.where(Booking.customer_id == customer_id)
    if date_from is not None:
        stmt = stmt.where(Booking.starts_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Booking.starts_at < date_to)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(Booking.customer_name.ilike(like) | Booking.customer_phone.ilike(like))
    return await paginate(db, stmt, params, BookingOut)


@router.post(
    "/bookings",
    response_model=BookingDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking",
    description=(
        "Returns **409** if the court is already taken for any part of the slot. "
        "That check is a PostgreSQL exclusion constraint, not a read-then-write in "
        "application code — two staff confirming simultaneously cannot both win."
    ),
)
async def create_booking(payload: BookingCreate, db: Db, principal: RequireStaff) -> BookingDetail:
    court = await get_or_404(db, Court, payload.court_id, label="Court")
    if not court.is_bookable:
        raise ConflictError(
            f"{court.name} is under maintenance.",
            details={"maintenance_note": court.maintenance_note},
        )

    customer_id, name, phone = await service.resolve_customer(
        db,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
    )

    quote_result, lines = await service.price_booking(
        db,
        court=court,
        starts_at=payload.starts_at,
        duration_min=payload.duration_min,
        selections=payload.equipment,
        discount=payload.discount,
    )

    ends_at = payload.starts_at + timedelta(minutes=payload.duration_min)
    booking = Booking(
        customer_id=customer_id,
        customer_name=name,
        customer_phone=phone,
        sport_id=court.sport_id,
        court_id=court.id,
        starts_at=payload.starts_at,
        ends_at=ends_at,
        duration_min=payload.duration_min,
        booking_type=payload.booking_type,
        notes=payload.notes,
        created_by_user_id=principal.id,
    )
    service._apply_quote(booking, quote_result, lines)
    db.add(booking)

    await service.ensure_slot_free(
        db, court_id=court.id, starts_at=payload.starts_at, ends_at=ends_at
    )
    await db.flush()

    await service.record_event(
        db,
        booking,
        kind=BookingEventKind.CREATED,
        label="Booking Created",
        detail=f"{payload.booking_type.value.title()} booking by {principal.email}",
        actor_user_id=principal.id,
    )

    # Issuing equipment moves real stock, so it goes through the ledger.
    for selection in payload.equipment:
        item = await db.get(Equipment, selection.equipment_id)
        if item is not None:
            await service.apply_movement(
                db,
                item,
                kind=MovementKind.ISSUE,
                qty=selection.qty,
                booking_id=booking.id,
                actor_user_id=principal.id,
            )
    if payload.equipment:
        await service.record_event(
            db,
            booking,
            kind=BookingEventKind.EQUIPMENT,
            label="Equipment Issued",
            detail=", ".join(f"{l.qty}× {l.name}" for l in lines),
            actor_user_id=principal.id,
        )

    await db.flush()
    return await _detail(db, booking)


@router.get("/bookings/{booking_id}", response_model=BookingDetail, summary="A single booking")
async def get_booking(booking_id: uuid.UUID, db: Db, _: RequireStaff) -> BookingDetail:
    booking = await get_or_404(db, Booking, booking_id, label="Booking")
    return await _detail(db, booking)


@router.patch(
    "/bookings/{booking_id}",
    response_model=BookingDetail,
    summary="Edit a booking",
    description="Re-prices whenever the court, time, duration, equipment or discount changes.",
)
async def update_booking(
    booking_id: uuid.UUID, payload: BookingUpdate, db: Db, principal: RequireStaff
) -> BookingDetail:
    booking = await get_or_404(db, Booking, booking_id, label="Booking")
    if booking.status is BookingStatus.CANCELLED:
        raise ConflictError("This booking has been cancelled and can no longer be edited.")

    updates = payload.model_dump(exclude_unset=True)
    reprice = {"court_id", "starts_at", "duration_min", "equipment", "discount"} & set(updates)

    if "status" in updates:
        booking.status = updates["status"]
    if "notes" in updates:
        booking.notes = updates["notes"]

    if reprice:
        court = (
            await get_or_404(db, Court, payload.court_id, label="Court")
            if payload.court_id
            else await db.get(Court, booking.court_id)
        )
        starts_at = payload.starts_at or booking.starts_at
        duration = payload.duration_min or booking.duration_min
        selections = payload.equipment if payload.equipment is not None else []
        discount = payload.discount if payload.discount is not None else booking.discount

        quote_result, lines = await service.price_booking(
            db,
            court=court,
            starts_at=starts_at,
            duration_min=duration,
            selections=selections,
            discount=discount,
        )
        booking.court_id = court.id
        booking.sport_id = court.sport_id
        booking.starts_at = starts_at
        booking.ends_at = starts_at + timedelta(minutes=duration)
        booking.duration_min = duration
        service._apply_quote(booking, quote_result, lines)

        await service.ensure_slot_free(
            db,
            court_id=court.id,
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
            exclude_booking_id=booking.id,
        )
        await db.flush()
        await service.record_event(
            db,
            booking,
            kind=BookingEventKind.EDIT,
            label="Booking Edited",
            detail=f"Updated {', '.join(sorted(reprice))}",
            actor_user_id=principal.id,
        )

    await db.flush()
    return await _detail(db, booking)


@router.post(
    "/bookings/{booking_id}/extend",
    response_model=BookingDetail,
    summary="Extend a live booking",
    description=(
        "The common case of a player deciding to keep going. Rejected with **409** "
        "and the maximum possible extension if another booking already follows."
    ),
)
async def extend_booking(
    booking_id: uuid.UUID, payload: BookingExtend, db: Db, principal: RequireStaff
) -> BookingDetail:
    booking = await get_or_404(db, Booking, booking_id, label="Booking")
    if booking.status is BookingStatus.CANCELLED:
        raise ConflictError("This booking has been cancelled.")

    available = await service.max_extension_minutes(db, booking)
    if payload.additional_minutes > available:
        raise ConflictError(
            "The court is booked again before that."
            if available
            else "The court is booked again immediately after this session.",
            details={"max_additional_minutes": available},
        )

    court = await db.get(Court, booking.court_id)
    duration = booking.duration_min + payload.additional_minutes
    quote_result, lines = await service.price_booking(
        db,
        court=court,
        starts_at=booking.starts_at,
        duration_min=duration,
        selections=[],
        discount=booking.discount,
    )
    # Keep the equipment already issued; only the court charge changes.
    existing = list(booking.equipment or [])
    booking.duration_min = duration
    booking.ends_at = booking.starts_at + timedelta(minutes=duration)
    booking.court_charge = quote_result.court_charge
    booking.taxes = quote_result.taxes
    booking.total = money(
        quote_result.court_charge + booking.equipment_charge - booking.discount + quote_result.taxes
    )
    booking.equipment = existing

    await service.ensure_slot_free(
        db,
        court_id=booking.court_id,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
        exclude_booking_id=booking.id,
    )
    await db.flush()
    await service.record_event(
        db,
        booking,
        kind=BookingEventKind.EXTENDED,
        label=f"Extended by {payload.additional_minutes} min",
        detail=f"Now ends at {booking.ends_at.isoformat()}",
        actor_user_id=principal.id,
    )
    await db.flush()
    return await _detail(db, booking)


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=BookingDetail,
    summary="Cancel a booking",
    description=(
        "Cancelling frees the slot immediately: the exclusion constraint excludes "
        "cancelled rows, so the time becomes bookable again in the same transaction."
    ),
)
async def cancel_booking(
    booking_id: uuid.UUID, payload: BookingCancel, db: Db, principal: RequireStaff
) -> BookingDetail:
    booking = await get_or_404(db, Booking, booking_id, label="Booking")
    if booking.status is BookingStatus.CANCELLED:
        return await _detail(db, booking)

    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = datetime.now(UTC)
    booking.cancellation_reason = payload.reason

    # Anything still out comes back to the shelf.
    outstanding = (
        (
            await db.execute(
                select(EquipmentMovement).where(
                    EquipmentMovement.booking_id == booking.id,
                    EquipmentMovement.kind == MovementKind.ISSUE,
                )
            )
        )
        .scalars()
        .all()
    )
    returned = (
        (
            await db.execute(
                select(EquipmentMovement).where(
                    EquipmentMovement.booking_id == booking.id,
                    EquipmentMovement.kind == MovementKind.RETURN,
                )
            )
        )
        .scalars()
        .all()
    )
    still_out: dict[uuid.UUID, int] = {}
    for movement in outstanding:
        still_out[movement.equipment_id] = still_out.get(movement.equipment_id, 0) + movement.qty
    for movement in returned:
        still_out[movement.equipment_id] = still_out.get(movement.equipment_id, 0) - movement.qty

    for equipment_id, qty in still_out.items():
        if qty <= 0:
            continue
        item = await db.get(Equipment, equipment_id)
        if item is not None:
            await service.apply_movement(
                db,
                item,
                kind=MovementKind.RETURN,
                qty=qty,
                booking_id=booking.id,
                note="Auto-returned on cancellation",
                actor_user_id=principal.id,
            )

    await service.record_event(
        db,
        booking,
        kind=BookingEventKind.CANCELLED,
        label="Booking Cancelled",
        detail=payload.reason,
        actor_user_id=principal.id,
    )
    await db.flush()
    return await _detail(db, booking)


@router.get(
    "/bookings/{booking_id}/timeline",
    response_model=list[BookingEventOut],
    summary="A booking's activity timeline",
)
async def booking_timeline(booking_id: uuid.UUID, db: Db, _: RequireStaff) -> list[BookingEventOut]:
    await get_or_404(db, Booking, booking_id, label="Booking")
    rows = (
        (
            await db.execute(
                select(BookingEvent)
                .where(BookingEvent.booking_id == booking_id)
                .order_by(BookingEvent.occurred_at)
            )
        )
        .scalars()
        .all()
    )
    return [BookingEventOut.model_validate(row) for row in rows]


async def _detail(db, booking: Booking) -> BookingDetail:
    sport = await db.get(Sport, booking.sport_id)
    court = await db.get(Court, booking.court_id)
    return BookingDetail(
        **BookingOut.model_validate(booking).model_dump(),
        sport_name=sport.name if sport else None,
        court_name=court.name if court else None,
    )
