"""Tenant-scoped auth: login, refresh, me."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.audit import write_audit
from app.auth.deps import CurrentPrincipal
from app.auth.schemas import (
    LoginRequest,
    MeOut,
    PlatformAdminOut,
    RefreshRequest,
    TenantOut,
    TokenPair,
    UserOut,
)
from app.auth.service import (
    access_token_ttl_seconds,
    authenticate_user,
    issue_user_tokens,
)
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import Audience, TokenError, decode_token
from app.models.audit import ActorKind
from app.models.tenant import Tenant
from app.models.user import PlatformAdmin, User
from app.tenancy.deps import Db, TenantCtx

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in as academy staff",
    description=(
        "Authenticates against the academy resolved from the request host "
        "(or `X-Tenant-ID` in development). The same email may exist at more than "
        "one academy; which one you reach is determined by the host, not the password."
    ),
)
async def login(payload: LoginRequest, tenant: TenantCtx, db: Db, request: Request) -> TokenPair:
    user = await authenticate_user(db, email=payload.email, password=payload.password)
    access, refresh = issue_user_tokens(user)

    await write_audit(
        db,
        tenant_id=tenant.id,
        action="auth.login",
        actor_kind=ActorKind.USER,
        actor_id=user.id,
        actor_label=user.email,
        entity_type="app_user",
        entity_id=user.id,
        request=request,
        tenant_context=tenant,
    )

    return TokenPair(
        access_token=access, refresh_token=refresh, expires_in=access_token_ttl_seconds()
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Exchange a refresh token for a new pair",
)
async def refresh_tokens(payload: RefreshRequest, tenant: TenantCtx, db: Db) -> TokenPair:
    try:
        claims = decode_token(
            payload.refresh_token, audience=Audience.TENANT, expected_type="refresh"
        )
    except TokenError as exc:
        raise AuthenticationError(f"Invalid or expired refresh token: {exc}") from exc

    # Same rule as the access path: a refresh token is bound to the academy it was
    # issued for, and presenting it against another one is refused.
    if claims.get("tid") != str(tenant.id):
        raise PermissionDeniedError("This token was issued for a different academy.")

    result = await db.execute(select(User).where(User.id == uuid.UUID(claims["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("This account is no longer active.")

    # NOTE: refresh tokens are stateless for now, so a refresh token stays valid
    # until it expires even after a password change. When that matters, add a
    # `token_version` integer to app_user, put it in the claims, and compare here —
    # bumping it invalidates every outstanding token for that user without needing
    # a denylist or Redis.
    access, refresh = issue_user_tokens(user)
    return TokenPair(
        access_token=access, refresh_token=refresh, expires_in=access_token_ttl_seconds()
    )


@router.get(
    "/me",
    response_model=MeOut,
    status_code=status.HTTP_200_OK,
    summary="The current principal and the academy they are acting in",
    description=(
        "Returns the academy alongside the principal, because the frontend needs "
        "the tenant's branding to render the shell. A platform operator "
        "impersonating an academy gets `platform_admin` populated and `user` null."
    ),
)
async def me(principal: CurrentPrincipal, tenant: TenantCtx, db: Db) -> MeOut:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant.id))
    tenant_row = result.scalar_one()

    if principal.is_platform_admin:
        admin_result = await db.execute(
            select(PlatformAdmin).where(PlatformAdmin.id == principal.id)
        )
        return MeOut(
            user=None,
            platform_admin=PlatformAdminOut.model_validate(admin_result.scalar_one()),
            tenant=TenantOut.model_validate(tenant_row),
        )

    return MeOut(
        user=UserOut.model_validate(principal.user),
        platform_admin=None,
        tenant=TenantOut.model_validate(tenant_row),
    )
