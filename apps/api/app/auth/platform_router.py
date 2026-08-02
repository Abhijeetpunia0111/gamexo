"""Platform-operator endpoints: my own control plane, above any single academy."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.audit import write_audit
from app.auth.deps import CurrentPlatformAdmin
from app.auth.schemas import (
    CreateTenantRequest,
    CreateTenantResponse,
    LoginRequest,
    PlatformAdminOut,
    RefreshRequest,
    TenantOut,
    TokenPair,
    UserOut,
)
from app.auth.service import (
    access_token_ttl_seconds,
    authenticate_platform_admin,
    issue_platform_tokens,
    provision_tenant,
)
from app.core.errors import AuthenticationError
from app.core.security import Audience, TokenError, decode_token
from app.models.audit import ActorKind
from app.models.tenant import Tenant
from app.models.user import PlatformAdmin
from app.tenancy.deps import UntenantedDb

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in as a platform operator",
    description=(
        "No academy is involved, so this endpoint does not resolve a tenant. The "
        "resulting token has a distinct audience and cannot be used as academy staff "
        "credentials; to act inside an academy, send it with `X-Impersonate-Tenant`."
    ),
)
async def platform_login(payload: LoginRequest, db: UntenantedDb) -> TokenPair:
    admin = await authenticate_platform_admin(
        db, email=payload.email, password=payload.password
    )
    access, refresh = issue_platform_tokens(admin)
    return TokenPair(
        access_token=access, refresh_token=refresh, expires_in=access_token_ttl_seconds()
    )


@router.post("/refresh", response_model=TokenPair, summary="Refresh a platform token")
async def platform_refresh(payload: RefreshRequest, db: UntenantedDb) -> TokenPair:
    try:
        claims = decode_token(
            payload.refresh_token, audience=Audience.PLATFORM, expected_type="refresh"
        )
    except TokenError as exc:
        raise AuthenticationError(f"Invalid or expired refresh token: {exc}") from exc

    result = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.id == uuid.UUID(claims["sub"]))
    )
    admin = result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise AuthenticationError("This platform account is no longer active.")

    access, refresh = issue_platform_tokens(admin)
    return TokenPair(
        access_token=access, refresh_token=refresh, expires_in=access_token_ttl_seconds()
    )


@router.get("/me", response_model=PlatformAdminOut, summary="The current platform operator")
async def platform_me(admin: CurrentPlatformAdmin) -> PlatformAdminOut:
    return PlatformAdminOut.model_validate(admin)


@router.post(
    "/tenants",
    response_model=CreateTenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard an academy",
    description=(
        "Creates the tenant, its default settings and its first admin user in one "
        "transaction. This is the only way an academy comes into existence — there "
        "is deliberately no public self-service registration."
    ),
)
async def create_tenant(
    payload: CreateTenantRequest,
    admin: CurrentPlatformAdmin,
    db: UntenantedDb,
    request: Request,
) -> CreateTenantResponse:
    tenant, tenant_admin = await provision_tenant(
        db,
        slug=payload.slug,
        name=payload.name,
        admin_email=payload.admin.email,
        admin_password=payload.admin.password,
        admin_full_name=payload.admin.full_name,
        business_name=payload.business_name,
        currency=payload.currency,
        timezone=payload.timezone,
    )

    # provision_tenant leaves the transaction bound to the new tenant, so this
    # tenant-scoped audit row is insertable and lands in the same commit.
    await write_audit(
        db,
        tenant_id=tenant.id,
        action="tenant.provisioned",
        actor_kind=ActorKind.PLATFORM_ADMIN,
        actor_id=admin.id,
        actor_label=admin.email,
        entity_type="tenant",
        entity_id=tenant.id,
        changes={"after": {"slug": tenant.slug, "name": tenant.name}},
        request=request,
    )

    return CreateTenantResponse(
        tenant=TenantOut.model_validate(tenant),
        admin=UserOut.model_validate(tenant_admin),
    )


@router.get(
    "/tenants",
    response_model=list[TenantOut],
    summary="List every academy on the platform",
)
async def list_tenants(admin: CurrentPlatformAdmin, db: UntenantedDb) -> list[TenantOut]:
    del admin
    result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    return [TenantOut.model_validate(row) for row in result.scalars()]
