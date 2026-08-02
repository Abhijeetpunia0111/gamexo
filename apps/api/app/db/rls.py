"""Row-Level Security: the GUC the policies read, and the DDL that creates them."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# The Postgres runtime parameter every tenant policy reads. Namespaced with a dot
# so Postgres accepts it as a custom GUC.
TENANT_GUC = "app.current_tenant"

# The policy predicate, shared by USING and WITH CHECK.
#
#   current_setting(name, true)  -> NULL instead of raising when never set. A
#                                   connection with no tenant therefore sees zero
#                                   rows rather than erroring or, worse, everything.
#   nullif(..., '')              -> we clear the GUC by setting it to '', and
#                                   ''::uuid would raise. This maps it back to NULL.
#   tenant_id = NULL             -> never true, so unscoped access returns nothing.
TENANT_PREDICATE = f"tenant_id = nullif(current_setting('{TENANT_GUC}', true), '')::uuid"

POLICY_NAME = "tenant_isolation"


async def set_current_tenant(session: AsyncSession, tenant_id: uuid.UUID | None) -> None:
    """Bind this transaction to a tenant.

    Uses `set_config(..., is_local => true)` rather than `SET LOCAL`. They have
    identical transaction-local semantics, but `SET LOCAL app.current_tenant = :tid`
    cannot take a bind parameter — the value would have to be interpolated into the
    SQL string, and that value originates in a request header. `set_config` is an
    ordinary function call that accepts a real bind parameter.

    Being transaction-local is what makes connection pooling safe here: the setting
    is discarded at COMMIT or ROLLBACK, so the next request to borrow this connection
    cannot inherit the previous tenant. That guarantee holds only while every request
    runs inside an explicit transaction — which `db.session.tenant_session` enforces.
    """
    await session.execute(
        text(f"SELECT set_config('{TENANT_GUC}', :tenant_id, true)"),
        {"tenant_id": str(tenant_id) if tenant_id is not None else ""},
    )


async def get_current_tenant(session: AsyncSession) -> uuid.UUID | None:
    """Read back the tenant bound to this transaction. Used by the isolation tests."""
    result = await session.execute(
        text(f"SELECT nullif(current_setting('{TENANT_GUC}', true), '')")
    )
    value = result.scalar_one_or_none()
    return uuid.UUID(value) if value else None


# ── DDL emitted by migrations ───────────────────────────────────────────────


def enable_rls_sql(table: str) -> list[str]:
    """Statements that put one table under tenant isolation.

    FORCE is not optional. `ENABLE ROW LEVEL SECURITY` alone leaves the table's
    OWNER exempt from its own policies, and the owner is the migration role that
    created the table. Without FORCE, anything connecting as that role — including
    a seed script or a psql session someone reaches for during an incident — reads
    every tenant's data with no indication that a policy exists.
    """
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        # USING filters what is visible to SELECT/UPDATE/DELETE.
        # WITH CHECK constrains what INSERT/UPDATE may write. Omitting WITH CHECK is
        # the classic half-done RLS: reads are isolated, but a tenant can still
        # INSERT a row stamped with someone else's tenant_id, or UPDATE one of its
        # own rows to hand it to another tenant.
        f"CREATE POLICY {POLICY_NAME} ON {table} "
        f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})",
    ]


def disable_rls_sql(table: str) -> list[str]:
    return [
        f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}",
        f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY",
    ]
