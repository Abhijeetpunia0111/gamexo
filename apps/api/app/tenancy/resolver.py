"""Turning an inbound request into a tenant."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PermissionDeniedError, TenantResolutionError
from app.models.tenant import Tenant, TenantStatus
from app.tenancy.context import TenantContext

TENANT_HEADER = "X-Tenant-ID"
IMPERSONATE_HEADER = "X-Impersonate-Tenant"


# ── Tenant snapshot cache ───────────────────────────────────────────────────
#
# Resolving the tenant used to cost a whole extra database session per request —
# its own connection, BEGIN, set_config, SELECT and COMMIT — to read one row that
# changes approximately never. Next to the database that is ~1 ms and invisible.
# Across the Pacific it was measured at ~1,285 ms of the ~3 s a request took.
#
# So the row is cached in-process and the session is skipped entirely on a hit.
# Consequences worth knowing:
#
#   * A suspension takes up to TTL seconds to lock a tenant out, because status is
#     part of the snapshot and re-checked on every hit rather than re-read.
#   * Misses are NOT cached. A bogus Host header therefore still reaches the
#     database, but a tenant created a second ago is never masked by a stale "no
#     such tenant" — which is the failure that would be maddening to debug.
#   * Per-process, so N workers hold N copies. That is fine for a table this small
#     and this static; it is the reason the TTL exists at all.

_CACHE_TTL_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class _TenantSnapshot:
    id: uuid.UUID
    slug: str
    name: str
    status: TenantStatus


# reference (slug or uuid string, normalised) -> (expires_at, snapshot)
_snapshots: dict[str, tuple[float, _TenantSnapshot]] = {}


def _normalise(reference: str) -> str:
    return reference.strip().lower()


def _cache_get(reference: str) -> _TenantSnapshot | None:
    entry = _snapshots.get(_normalise(reference))
    if entry is None:
        return None
    expires_at, snapshot = entry
    if expires_at < time.monotonic():
        _snapshots.pop(_normalise(reference), None)
        return None
    return snapshot


def _cache_put(snapshot: _TenantSnapshot) -> None:
    """Store under both slug and id, so either reference form hits."""
    expires_at = time.monotonic() + _CACHE_TTL_SECONDS
    for key in (snapshot.slug, str(snapshot.id)):
        _snapshots[_normalise(key)] = (expires_at, snapshot)


def invalidate_tenant_cache(*references: str) -> None:
    """Drop cached tenants. No arguments clears everything.

    Call after anything that changes a tenant's slug, name or status. Today only
    provisioning does, and provisioning cannot be masked by a stale entry because
    misses are not cached — but a suspend endpoint would need this, and finding
    that out from a support ticket is the expensive way.
    """
    if not references:
        _snapshots.clear()
        return
    for reference in references:
        _snapshots.pop(_normalise(reference), None)


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


def _assert_usable(snapshot: _TenantSnapshot) -> None:
    if snapshot.status is TenantStatus.SUSPENDED:
        raise PermissionDeniedError(
            f"Academy '{snapshot.slug}' is suspended.", details={"tenant_slug": snapshot.slug}
        )


@dataclass(frozen=True, slots=True)
class _Plan:
    """Which tenant this request names, and how. Decided without touching the database."""

    reference: str
    source: str
    #: Impersonation reaches suspended tenants on purpose — that is what support
    #: access is for. Every other path must not.
    enforce_status: bool
    not_found_message: str


def _plan_resolution(
    *,
    host: str | None,
    tenant_header: str | None,
    impersonate_header: str | None,
    is_platform_admin: bool,
) -> _Plan:
    """Apply the resolution priority. Pure — no I/O, so cache and database paths
    cannot drift apart on which header wins.

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
        reference = impersonate_header.strip()
        return _Plan(reference, "impersonation", False, f"Unknown tenant: {reference!r}")

    if tenant_header and settings.allow_tenant_header:
        reference = tenant_header.strip()
        return _Plan(reference, "header", True, f"Unknown tenant: {reference!r}")

    slug = extract_slug_from_host(host, settings.tenant_base_domain)
    if slug:
        return _Plan(slug, "host", True, f"Unknown academy: {slug!r}")

    hint = (
        f" Send {TENANT_HEADER} with a tenant slug, or use a subdomain "
        f"(e.g. acme.{settings.tenant_base_domain})."
        if settings.allow_tenant_header
        else ""
    )
    raise TenantResolutionError(f"Could not determine the academy from host {host!r}.{hint}")


def _context_from(plan: _Plan, snapshot: _TenantSnapshot) -> TenantContext:
    if plan.enforce_status:
        _assert_usable(snapshot)
    return TenantContext(
        id=snapshot.id, slug=snapshot.slug, name=snapshot.name, source=plan.source
    )


def resolve_tenant_cached(
    *,
    host: str | None,
    tenant_header: str | None,
    impersonate_header: str | None = None,
    is_platform_admin: bool = False,
) -> TenantContext | None:
    """Resolve without touching the database, or return None if it cannot.

    None means "open a session and call resolve_tenant". Errors that need no
    database — a missing host, impersonation by a non-operator — still raise here,
    because making the caller open a connection to discover them is pure latency.
    """
    plan = _plan_resolution(
        host=host,
        tenant_header=tenant_header,
        impersonate_header=impersonate_header,
        is_platform_admin=is_platform_admin,
    )
    snapshot = _cache_get(plan.reference)
    return None if snapshot is None else _context_from(plan, snapshot)


async def resolve_tenant(
    session: AsyncSession,
    *,
    host: str | None,
    tenant_header: str | None,
    impersonate_header: str | None = None,
    is_platform_admin: bool = False,
) -> TenantContext:
    """Resolve the tenant for a request, reading the database on a cache miss."""
    plan = _plan_resolution(
        host=host,
        tenant_header=tenant_header,
        impersonate_header=impersonate_header,
        is_platform_admin=is_platform_admin,
    )

    snapshot = _cache_get(plan.reference)
    if snapshot is None:
        tenant = await load_tenant_by_reference(session, plan.reference)
        if tenant is None:
            raise TenantResolutionError(plan.not_found_message)
        snapshot = _TenantSnapshot(
            id=tenant.id, slug=tenant.slug, name=tenant.name, status=tenant.status
        )
        _cache_put(snapshot)

    return _context_from(plan, snapshot)
