"""Shared DDL for tenant isolation, used by every migration after the foundation.

Lives at the project root rather than inside `alembic/` because that directory name
collides with the installed `alembic` package — `from alembic._rls import ...` would
resolve to site-packages and fail.

Frozen on purpose. This module must never import from `app`: a migration describes
the schema at one point in history, and pulling in live application code would make
old migrations change meaning as the app evolves. The predicate below is a byte-for-byte
copy of `app/db/rls.py::TENANT_PREDICATE`; `tests/test_tenant_isolation.py` asserts
that every tenant table actually ends up with a policy, so the two cannot silently
drift apart without the suite going red.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

from alembic import op

POLICY_NAME = "tenant_isolation"

#   current_setting(_, true) -> NULL rather than an error when never set
#   nullif(_, '')            -> we clear by setting '', and ''::uuid would raise
#   tenant_id = NULL         -> never true, so an unbound session sees zero rows
TENANT_PREDICATE = "tenant_id = nullif(current_setting('app.current_tenant', true), '')::uuid"


def app_role() -> str:
    """The role the API connects as. Interpolated into DDL, so it is validated."""
    role = os.environ.get("DB_APP_USER", "gamexo_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", role):
        raise ValueError(f"DB_APP_USER is not a plain SQL identifier: {role!r}")
    return role


def protect(tables: Iterable[str], *, append_only: Iterable[str] = ()) -> None:
    """Grant the app role access to new tables and put them under tenant isolation.

    Grants are emitted explicitly even though docker/initdb sets ALTER DEFAULT
    PRIVILEGES, so migrations also work against a managed Postgres provisioned
    without that bootstrap — where the failure mode is an API that authenticates
    fine and then 500s on every query.
    """
    role = app_role()
    append_only = set(append_only)

    for table in tables:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {role}")
        if table in append_only:
            op.execute(f"REVOKE UPDATE, DELETE ON TABLE {table} FROM {role}")

        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE is not redundant: ENABLE alone leaves the table's owner — this
        # migration role — exempt from its own policies.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # WITH CHECK as well as USING, or a tenant can still INSERT rows stamped
        # with another tenant's id even though reads are isolated.
        op.execute(
            f"CREATE POLICY {POLICY_NAME} ON {table} "
            f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})"
        )


def unprotect(tables: Iterable[str]) -> None:
    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
