"""Declarative base and the tenant-scoped mixin every business entity inherits."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Explicit naming convention so Alembic autogenerate emits deterministic constraint
# names it can later DROP. Without this, Postgres invents names like
# "booking_court_id_fkey1" and a downgrade cannot reliably find them.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TenantScoped(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Shared base for every tenant-owned table.

    Carries `id`, `tenant_id`, `created_at`, `updated_at`. Two mechanisms key off
    this class specifically, so a business model that forgets to inherit it is
    silently unprotected — `tests/test_tenant_isolation.py::test_every_business_table_is_tenant_scoped`
    fails the build if one does:

    1. `db/session.py` injects `tenant_id` on INSERT and appends a tenant predicate
       to every ORM SELECT, keyed on `isinstance(obj, TenantScoped)`.
    2. The Alembic migrations enable RLS on every table mapped under it.

    `tenant` and `platform_admin` inherit `Base` directly — they are the two tables
    that are not owned by a tenant.
    """

    __abstract__ = True

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        # RESTRICT, not CASCADE: deleting a tenant must be a deliberate, audited
        # offboarding procedure, never a side effect of one stray DELETE.
        ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


def tenant_index(table_name: str, *columns: str, unique: bool = False) -> Index:
    """Build a composite index that leads with `tenant_id`.

    Every query in a pooled multi-tenant schema filters on tenant_id, so it belongs
    in the leading position of every composite index — an index on (court_id, starts_at)
    cannot serve `WHERE tenant_id = ? AND court_id = ?` nearly as well as
    (tenant_id, court_id, starts_at) can.
    """
    prefix = "uq" if unique else "ix"
    name = f"{prefix}_{table_name}_tenant_{'_'.join(columns)}"
    return Index(name, "tenant_id", *columns, unique=unique)


def tenant_scoped_tables() -> list[str]:
    """Table names that must carry an RLS policy. Used by migrations and tests."""
    return sorted(
        table.name
        for table in Base.metadata.tables.values()
        if "tenant_id" in table.columns
    )
