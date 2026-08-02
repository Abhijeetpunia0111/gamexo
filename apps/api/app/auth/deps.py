"""Authentication and RBAC dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Callable, Literal

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import (
    ROLE_HIERARCHY,
    Audience,
    Role,
    TokenError,
    decode_token,
)
from app.models.user import PlatformAdmin, User
from app.tenancy.context import TenantContext
from app.tenancy.deps import BearerToken, Db, TenantCtx, UntenantedDb


@dataclass(frozen=True, slots=True)
class Principal:
    """Whoever is making this request — a staff member or a platform operator."""

    id: uuid.UUID
    kind: Literal["user", "platform_admin"]
    email: str
    tenant_id: uuid.UUID | None
    role: Role | None
    user: User | None = None

    @property
    def is_platform_admin(self) -> bool:
        return self.kind == "platform_admin"

    @property
    def actor_label(self) -> str:
        return self.email


async def _load_platform_admin(session: AsyncSession, admin_id: uuid.UUID) -> PlatformAdmin:
    """Fetch a platform operator.

    Works on a tenant-bound session because `platform_admin` carries no tenant_id
    and therefore no RLS policy — it is one of exactly two such tables.
    """
    result = await session.execute(select(PlatformAdmin).where(PlatformAdmin.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise AuthenticationError("This platform account is no longer active.")
    return admin


async def get_current_principal(
    tenant: TenantCtx, db: Db, credentials: BearerToken = None
) -> Principal:
    """Authenticate the caller against the already-resolved tenant."""
    if credentials is None:
        raise AuthenticationError("Not authenticated.")

    token = credentials.credentials

    # Platform operators first: their token has a different audience, so this is a
    # cheap, unambiguous discrimination rather than a guess.
    try:
        payload = decode_token(token, audience=Audience.PLATFORM)
    except TokenError:
        pass
    else:
        admin = await _load_platform_admin(db, uuid.UUID(payload["sub"]))
        return Principal(
            id=admin.id,
            kind="platform_admin",
            email=admin.email,
            tenant_id=tenant.id,
            role=None,
        )

    try:
        payload = decode_token(token, audience=Audience.TENANT)
    except TokenError as exc:
        raise AuthenticationError(f"Invalid or expired token: {exc}") from exc

    claimed_tenant = payload.get("tid")

    # The check the whole design rests on. The tenant was resolved from the host
    # (or the dev header) *independently* of this token. If a token minted for
    # academy A arrives on academy B's hostname, both values exist and disagree,
    # and the request is refused. Trusting `tid` as the selector instead would make
    # exactly that replay indistinguishable from normal traffic.
    if claimed_tenant != str(tenant.id):
        raise PermissionDeniedError(
            "This token was issued for a different academy.",
            details={"resolved_tenant": tenant.slug},
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        # RLS also guarantees a user from another tenant is invisible here, so this
        # covers deletion and cross-tenant lookup alike.
        raise AuthenticationError("This account no longer exists.")
    if not user.is_active:
        raise AuthenticationError(f"This account is {user.status.value}.")

    return Principal(
        id=user.id,
        kind="user",
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        user=user,
    )


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_roles(*allowed: Role) -> Callable[[Principal], Principal]:
    """Guard an endpoint behind one or more tenant roles.

    Roles are hierarchical: requiring RECEPTION admits MANAGER and ADMIN too. Flat
    role sets mean every new admin-facing endpoint has to remember to list all three,
    and the one that forgets locks the owner out of their own academy.

    Platform operators pass every guard. That is the point of the role — they are
    acting on a tenant's behalf for support — and every such request is audited.
    """
    required = min(ROLE_HIERARCHY[role] for role in allowed)

    def dependency(principal: CurrentPrincipal) -> Principal:
        if principal.is_platform_admin:
            return principal
        if principal.role is None or ROLE_HIERARCHY[principal.role] < required:
            raise PermissionDeniedError(
                "Your role does not permit this action.",
                details={
                    "required": sorted(role.value for role in allowed),
                    "actual": principal.role.value if principal.role else None,
                },
            )
        return principal

    return dependency


RequireAdmin = Annotated[Principal, Depends(require_roles(Role.ADMIN))]
RequireManager = Annotated[Principal, Depends(require_roles(Role.MANAGER))]
RequireStaff = Annotated[Principal, Depends(require_roles(Role.RECEPTION))]


async def get_current_platform_admin(
    db: UntenantedDb, credentials: BearerToken = None
) -> PlatformAdmin:
    """Authenticate a platform operator on an endpoint with no tenant at all.

    Used by /platform/* (listing and creating tenants), which by definition cannot
    resolve a tenant from the host.
    """
    if credentials is None:
        raise AuthenticationError("Not authenticated.")
    try:
        payload = decode_token(credentials.credentials, audience=Audience.PLATFORM)
    except TokenError as exc:
        raise AuthenticationError(f"Invalid or expired platform token: {exc}") from exc

    return await _load_platform_admin(db, uuid.UUID(payload["sub"]))


CurrentPlatformAdmin = Annotated[PlatformAdmin, Depends(get_current_platform_admin)]


def tenant_context_of(principal: Principal, tenant: TenantContext) -> TenantContext:
    """Convenience for audit writes."""
    del principal
    return tenant
