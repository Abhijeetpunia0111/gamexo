"""The ambient tenant for the current task.

A ContextVar, not a global: FastAPI serves concurrent requests on one event loop,
so a module-level variable would be shared between two in-flight requests for
different tenants. ContextVars are per-task and propagate into anything the request
awaits.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar(
    "gamexo_current_tenant_id", default=None
)


@dataclass(frozen=True, slots=True)
class TenantContext:
    """How the tenant for this request was determined.

    `source` is carried through to the audit log: knowing a write arrived via the
    X-Tenant-ID header rather than the host is exactly what you want when working
    out how something ended up in the wrong academy.
    """

    id: uuid.UUID
    slug: str
    name: str
    source: str  # "host" | "header" | "impersonation"


def get_current_tenant_id() -> uuid.UUID | None:
    return _current_tenant_id.get()


def require_current_tenant_id() -> uuid.UUID:
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise RuntimeError(
            "No tenant bound to this context. Tenant-scoped work must run inside "
            "db.session.tenant_session() or a request carrying a resolved tenant."
        )
    return tenant_id


@contextmanager
def bind_tenant(tenant_id: uuid.UUID | None) -> Iterator[None]:
    token = _current_tenant_id.set(tenant_id)
    try:
        yield
    finally:
        _current_tenant_id.reset(token)
