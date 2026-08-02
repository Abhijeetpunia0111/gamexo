"""Shared column types."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import TypeVar

from sqlalchemy import Enum, Numeric

E = TypeVar("E", bound=PyEnum)


def enum_type(enum_class: type[E], *, name: str, length: int = 32) -> Enum:
    """A VARCHAR + CHECK constraint holding the enum's *values*.

    Two deliberate choices:

    `native_enum=False` — a Postgres native ENUM type is painful to evolve. Adding a
    status means ALTER TYPE, removing one means recreating the type and rewriting
    every dependent column. These status sets come from the frontend and will move
    (`ContractStatus` alone has eight members and a sales pipeline behind it). A
    VARCHAR with a named CHECK is a one-line constraint swap in a migration.

    `values_callable` — without it SQLAlchemy persists the enum member's *name*, so
    `Role.ADMIN` would be stored as "ADMIN" while the frontend, the JWT claim and
    every fixture say "admin". Storing values keeps the database, the API and the
    existing TypeScript literal unions identical.
    """
    return Enum(
        enum_class,
        native_enum=False,
        length=length,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
        validate_strings=True,
    )


def money() -> Numeric:
    """NUMERIC(12,2) for every amount.

    The frontend uses JS `number` throughout, which is a float. Floats are wrong for
    money — the frontend gets away with it because it only displays; the backend
    sums, applies GST, splits payments and reconciles against invoices, where the
    drift becomes a discrepancy someone has to explain.

    12 digits before rounding to 2 covers ₹99,99,99,999.99, comfortably beyond the
    largest figure in the mock data (a ₹2,40,000 corporate membership).
    """
    return Numeric(12, 2)
