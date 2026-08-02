"""Per-tenant document numbering.

The requirement: `XC-2024-0001` style numbers must reset and increment *per academy*.
A global auto-increment is unacceptable — it would leak the platform's total invoice
count into every tenant's numbers, so an academy that signed up second would see its
very first invoice numbered XC-2024-0873 and learn exactly how much business everyone
else is doing.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import CounterKind, DocumentCounter
from app.tenancy.context import require_current_tenant_id

# Zero-padding per series, matching the frontend's existing strings:
# XC-2024-0001, XC-M-0001, XC-C-001, XC-S-001.
PAD: dict[CounterKind, int] = {
    CounterKind.INVOICE: 4,
    CounterKind.MEMBER: 4,
    CounterKind.COACH: 3,
    CounterKind.STUDENT: 3,
}

INFIX: dict[CounterKind, str] = {
    CounterKind.INVOICE: "",  # the year takes this slot
    CounterKind.MEMBER: "M",
    CounterKind.COACH: "C",
    CounterKind.STUDENT: "S",
}


def period_for(kind: CounterKind, on: date) -> str:
    """Invoices reset annually; the other series run forever."""
    return str(on.year) if kind is CounterKind.INVOICE else ""


async def allocate(session: AsyncSession, kind: CounterKind, *, period: str) -> int:
    """Take the next value in a series, atomically.

    Two steps, both necessary:

    1. `INSERT ... ON CONFLICT DO NOTHING` creates the counter row the first time
       this series is used. Doing it as an upsert rather than "check then insert"
       closes the race where two concurrent first-ever invoices both find no row.

    2. `SELECT ... FOR UPDATE` takes a row lock held until the caller's transaction
       ends. A second transaction wanting the same series blocks here rather than
       reading the same `last_value`, so two invoices can never share a number.

    Because this runs inside the caller's transaction, a rollback takes the
    allocation with it and the series stays gapless — which a Postgres sequence
    could not offer, since `nextval` is deliberately non-transactional.
    """
    tenant_id = require_current_tenant_id()

    await session.execute(
        pg_insert(DocumentCounter)
        .values(tenant_id=tenant_id, kind=kind, period=period, last_value=0)
        .on_conflict_do_nothing(index_elements=["tenant_id", "kind", "period"])
    )

    counter = (
        await session.execute(
            select(DocumentCounter)
            .where(DocumentCounter.kind == kind, DocumentCounter.period == period)
            .with_for_update()
        )
    ).scalar_one()

    counter.last_value += 1
    await session.flush()
    return counter.last_value


async def next_number(
    session: AsyncSession, kind: CounterKind, *, prefix: str = "XC", on: date | None = None
) -> str:
    """The formatted document number, e.g. `XC-2024-0001` or `XC-M-0001`.

    `prefix` comes from the tenant's settings, so a white-label customer's invoices
    carry their own initials rather than mine.
    """
    on = on or date.today()
    period = period_for(kind, on)
    value = await allocate(session, kind, period=period)

    middle = period or INFIX[kind]
    return f"{prefix}-{middle}-{value:0{PAD[kind]}d}"
