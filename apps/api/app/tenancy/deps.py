"""FastAPI dependencies for tenant resolution and tenant-scoped database access."""

from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Audience, TokenError, decode_token
from app.db.session import tenant_session, untenanted_session
from app.tenancy.context import TenantContext
from app.tenancy.resolver import IMPERSONATE_HEADER, TENANT_HEADER, resolve_tenant

# auto_error=False so anonymous requests reach the endpoint and get our error
# envelope, rather than Starlette's bare {"detail": "Not authenticated"}.
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")

BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _looks_like_platform_token(credentials: HTTPAuthorizationCredentials | None) -> bool:
    """Is this a *valid* platform-operator access token?

    Full signature/expiry/audience verification, not a peek at the claims — this
    decides whether X-Impersonate-Tenant is honoured, so an unverified read would
    make impersonation available to anyone who can craft a JSON blob.

    The identity is re-established properly in auth/deps.py; this only answers
    "which tenant is this request for", which has to be settled before a session
    can be opened to look the operator up.
    """
    if credentials is None:
        return False
    try:
        decode_token(credentials.credentials, audience=Audience.PLATFORM)
    except TokenError:
        return False
    return True


async def get_tenant_context(
    request: Request, credentials: BearerToken = None
) -> TenantContext:
    """Resolve the tenant for this request.

    Runs on an untenanted session because the `tenant` table is what is being read —
    it carries no tenant_id and no RLS policy, by necessity.
    """
    async with untenanted_session() as session:
        context = await resolve_tenant(
            session,
            host=request.headers.get("host"),
            tenant_header=request.headers.get(TENANT_HEADER),
            impersonate_header=request.headers.get(IMPERSONATE_HEADER),
            is_platform_admin=_looks_like_platform_token(credentials),
        )
    # Stash for the audit log and for logging middleware.
    request.state.tenant = context
    return context


TenantCtx = Annotated[TenantContext, Depends(get_tenant_context)]


async def get_db(tenant: TenantCtx) -> AsyncIterator[AsyncSession]:
    """A tenant-bound session for the life of one request.

    The whole request runs in one transaction. That is what gives the
    `app.current_tenant` setting a defined lifetime — see db/rls.py — and it means a
    handler that raises halfway through a multi-table write leaves nothing behind.
    """
    async with tenant_session(tenant.id) as session:
        yield session


async def get_untenanted_db() -> AsyncIterator[AsyncSession]:
    """A session with no tenant bound, for platform-level endpoints only.

    Not a backdoor: every tenant-scoped table returns zero rows through this session,
    because RLS evaluates `tenant_id = NULL`. It reaches only `tenant` and
    `platform_admin`, the two tables with no tenant_id.
    """
    async with untenanted_session() as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_db)]
UntenantedDb = Annotated[AsyncSession, Depends(get_untenanted_db)]
