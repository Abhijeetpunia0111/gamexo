"""Seed tenant #1 — my own academy — so the app runs end to end immediately.

Idempotent: re-running updates nothing and creates nothing twice, so it is safe to
wire into container startup.

Deliberately runs as the *application* role, through the same tenant-scoped session
the API uses. Seeding as the migrator role would bypass nothing (FORCE RLS is set)
but would exercise a path production never takes. If the seed can write it, so can
the API — and if RLS is misconfigured, this fails immediately and loudly.

    uv run python -m app.seed.seed
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

from sqlalchemy import func, select

from app.auth.service import initials, provision_tenant
from app.core.config import settings
from app.core.security import Role, hash_password
from app.db.session import dispose_engine, tenant_session, untenanted_session
from app.models.tenant import Tenant, TenantSettings
from app.models.user import PlatformAdmin, User, UserStatus

# Straight from src/pages/Staff.tsx — the real staff list the frontend renders.
STAFF = [
    ("Rahul Joshi", "rahul@xcourtsports.com", Role.ADMIN, "9811122334",
     "Morning (6AM–2PM)", UserStatus.ACTIVE, date(2022, 3, 1)),
    ("Sunita Rao", "sunita@xcourtsports.com", Role.RECEPTION, "9833344556",
     "Evening (2PM–10PM)", UserStatus.ACTIVE, date(2023, 1, 15)),
    ("Mohan Das", "mohan@xcourtsports.com", Role.RECEPTION, "9877665544",
     "Morning (6AM–2PM)", UserStatus.ACTIVE, date(2023, 6, 10)),
    ("Priya Verma", "priya.v@xcourtsports.com", Role.MANAGER, "9900011223",
     "Full Day (9AM–6PM)", UserStatus.ON_LEAVE, date(2022, 8, 20)),
    ("Karthik S", "karthik@xcourtsports.com", Role.RECEPTION, "9855544332",
     "Night (10PM–6AM)", UserStatus.ACTIVE, date(2024, 1, 1)),
]

# From src/pages/Settings.tsx → General → Business Information.
BUSINESS_PROFILE = {
    "business_name": "XCourt Sports",
    "phone": "+91 98765 43210",
    "email": "info@xcourtsports.com",
    "gst_number": "27AABCX1234Z1ZV",
    "address": "123 Sports Complex, Mumbai",
    "city": "Mumbai, MH 400001",
}


async def _seed_platform_admin() -> None:
    async with untenanted_session() as session:
        email = settings.seed_platform_admin_email.lower()
        existing = await session.execute(
            select(PlatformAdmin).where(func.lower(PlatformAdmin.email) == email)
        )
        if existing.scalar_one_or_none() is not None:
            print(f"  platform admin {email} already exists")
            return

        session.add(
            PlatformAdmin(
                email=email,
                password_hash=hash_password(settings.seed_platform_admin_password),
                full_name="gamexo Operations",
            )
        )
        print(f"  created platform admin {email}")


async def _seed_tenant() -> uuid.UUID:
    async with untenanted_session() as session:
        existing = await session.execute(
            select(Tenant).where(Tenant.slug == settings.seed_tenant_slug)
        )
        tenant = existing.scalar_one_or_none()
        if tenant is not None:
            print(f"  tenant '{tenant.slug}' already exists")
            return tenant.id

        tenant, admin = await provision_tenant(
            session,
            slug=settings.seed_tenant_slug,
            name=settings.seed_tenant_name,
            admin_email=settings.seed_admin_email,
            admin_password=settings.seed_admin_password,
            admin_full_name="XCourt Administrator",
            business_name=BUSINESS_PROFILE["business_name"],
        )
        print(f"  created tenant #1 '{tenant.slug}' with admin {admin.email}")
        return tenant.id


async def _seed_tenant_data(tenant_id: uuid.UUID) -> None:
    """Fill in the academy's profile and staff, through a tenant-bound session."""
    async with tenant_session(tenant_id) as session:
        # RLS means this query cannot see another academy's settings even though it
        # has no WHERE clause on tenant_id.
        result = await session.execute(select(TenantSettings))
        tenant_settings = result.scalar_one()
        for field, value in BUSINESS_PROFILE.items():
            setattr(tenant_settings, field, value)
        tenant_settings.notification_sender_name = "XCourt Sports"
        tenant_settings.notification_sender_email = BUSINESS_PROFILE["email"]

        existing_emails = {
            email.lower()
            for email in (await session.execute(select(User.email))).scalars()
        }

        created = 0
        for name, email, role, phone, shift, status, joined in STAFF:
            if email.lower() in existing_emails:
                continue
            # tenant_id is intentionally not passed: the before_flush hook in
            # db/session.py stamps it from the bound context. That is the ergonomic
            # the plan asked for — no endpoint threading tenant_id by hand — and
            # seeding is the first place it gets exercised.
            session.add(
                User(
                    email=email,
                    password_hash=hash_password(settings.seed_admin_password),
                    full_name=name,
                    role=role,
                    phone=phone,
                    shift=shift,
                    status=status,
                    joined_on=joined,
                    avatar_initials=initials(name),
                )
            )
            created += 1

        print(f"  updated academy profile, created {created} staff user(s)")
        return tenant_settings.invoice_prefix


async def _seed_domain(tenant_id: uuid.UUID, prefix: str) -> None:
    """Sports, courts, equipment, customers, plans, coaches, students, ad spots."""
    from app.seed.demo_data import seed_domain_data

    async with tenant_session(tenant_id) as session:
        created = await seed_domain_data(session, prefix)
    summary = ", ".join(f"{count} {name}" for name, count in created.items() if count)
    print(f"  {summary or 'domain data already present'}")


async def main() -> None:
    print("Seeding gamexo…")
    await _seed_platform_admin()
    tenant_id = await _seed_tenant()
    prefix = await _seed_tenant_data(tenant_id)
    await _seed_domain(tenant_id, prefix or "XC")
    await dispose_engine()

    print(
        "\nDone.\n"
        f"  Academy      : {settings.seed_tenant_name} ({settings.seed_tenant_slug})\n"
        f"  Staff login  : {settings.seed_admin_email} / {settings.seed_admin_password}\n"
        f"  Platform     : {settings.seed_platform_admin_email} / "
        f"{settings.seed_platform_admin_password}\n"
        f"  Try          : curl -H 'X-Tenant-ID: {settings.seed_tenant_slug}' "
        "http://localhost:8000/api/v1/health/tenant"
    )


if __name__ == "__main__":
    asyncio.run(main())
