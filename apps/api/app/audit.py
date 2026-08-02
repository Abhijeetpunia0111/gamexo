"""Writing to the audit trail."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ActorKind, AuditLog
from app.tenancy.context import TenantContext


def client_ip(request: Request | None) -> str | None:
    """The caller's address, honouring one layer of reverse proxy.

    Only the first X-Forwarded-For entry from a trusted proxy is meaningful; the
    header is client-settable, so this is a debugging aid rather than evidence.
    """
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def write_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: str,
    actor_kind: ActorKind,
    actor_id: uuid.UUID | None = None,
    actor_label: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    changes: dict[str, Any] | None = None,
    request: Request | None = None,
    tenant_context: TenantContext | None = None,
) -> AuditLog:
    """Append one audit row.

    Written on the caller's session so it commits in the same transaction as the
    change it describes. An audit log that can commit while the action rolls back
    (or vice versa) is worse than none: it makes the record actively misleading.
    """
    entry = AuditLog(
        tenant_id=tenant_id,
        action=action,
        actor_kind=actor_kind,
        actor_id=actor_id,
        actor_label=actor_label,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent") if request else None,
        tenant_source=tenant_context.source if tenant_context else None,
    )
    session.add(entry)
    return entry
