"""Turning an inbound request into a tenant."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PermissionDeniedError, TenantResolutionError
from app.models.tenant import Tenant, TenantStatus
from app.tenancy.context import TenantContext

TENANT_HEADER = "X-Tenant-ID"
IMPERSONATE_HEADER = "X-Impersonate-Tenant"


def extract_slug_from_host(host: str | None, base_domain: str) -> str | None:
    """`myacademy.gamexo.app` -> `myacademy`. The production path.

    Also handles `myacademy.localhost:8000`, so subdomain routing can be exercised
    locally rather than only ever testing the header path — the header path is the
    one that does not exist in production.

    Returns None for the apex domain, `www`, bare `localhost` and bare IPs.
    """
    if not host:
        return None

    hostname = host.split(":")[0].strip().lower().rstrip(".")
    if not hostname:
        return None

    for base in (base_domain.strip().lower(), "localhost"):
        if not base:
            continue
        if hostname in (base, f"www.{base}"):
            return None
        suffix = f".{base}"
        if hostname.endswith(suffix):
            # Take the left-most label so deeper nesting resolves to the tenant,
            # not to an intermediate label.
            label = hostname[: -len(suffix)].split(".")[0]
            return label or None

    return None


async def _load_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    result = await session.execute(select(Tenant).where(Tenant.slug == slug.lower()))
    return result.scalar_one_or_none()


async def _load_tenant_by_id(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def load_tenant_by_reference(session: AsyncSession, reference: str) -> Tenant | None:
    """Look a tenant up by slug or UUID — whichever the caller supplied."""
    try:
        return await _load_tenant_by_id(session, uuid.UUID(reference))
    except ValueError:
        return await _load_tenant_by_slug(session, reference)


def _assert_usable(tenant: Tenant) -> None:
    if tenant.status is TenantStatus.SUSPENDED:
        raise PermissionDeniedError(
            f"Academy '{tenant.slug}' is suspended.", details={"tenant_slug": tenant.slug}
        )


async def resolve_tenant(
    session: AsyncSession,
    *,
    host: str | None,
    tenant_header: str | None,
    impersonate_header: str | None = None,
    is_platform_admin: bool = False,
) -> TenantContext:
    """Resolve the tenant for a request, in priority order.

    1. Platform-admin impersonation (`X-Impersonate-Tenant`) — support access, only
       ever honoured for an authenticated platform operator, and audit-logged by the
       caller.
    2. `X-Tenant-ID` — development and API testing. Gated on ALLOW_TENANT_HEADER,
       which core/config.py refuses to let be true in production. Without that gate
       this header is a complete isolation bypass for anyone who can reach the API.
    3. Host subdomain — the production path.

    The JWT's tenant claim is deliberately NOT a resolution source. If it were, a
    token minted for tenant A would resolve to tenant A no matter which academy's
    hostname it was presented to, and cross-tenant replay would look like ordinary
    traffic. The claim is instead *verified against* the independently resolved
    tenant in auth/deps.py.
    """
    if impersonate_header:
        if not is_platform_admin:
            raise PermissionDeniedError(
                f"{IMPERSONATE_HEADER} is reserved for platform operators."
            )
        tenant = await load_tenant_by_reference(session, impersonate_header.strip())
        if tenant is None:
            raise TenantResolutionError(f"Unknown tenant: {impersonate_header!r}")
        return TenantContext(
            id=tenant.id, slug=tenant.slug, name=tenant.name, source="impersonation"
        )

    if tenant_header and settings.allow_tenant_header:
        tenant = await load_tenant_by_reference(session, tenant_header.strip())
        if tenant is None:
            raise TenantResolutionError(f"Unknown tenant: {tenant_header!r}")
        _assert_usable(tenant)
        return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name, source="header")

    slug = extract_slug_from_host(host, settings.tenant_base_domain)
    if slug:
        tenant = await _load_tenant_by_slug(session, slug)
        if tenant is None:
            raise TenantResolutionError(f"Unknown academy: {slug!r}")
        _assert_usable(tenant)
        return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name, source="host")

    hint = (
        f" Send {TENANT_HEADER} with a tenant slug, or use a subdomain "
        f"(e.g. acme.{settings.tenant_base_domain})."
        if settings.allow_tenant_header
        else ""
    )
    raise TenantResolutionError(f"Could not determine the academy from host {host!r}.{hint}")
