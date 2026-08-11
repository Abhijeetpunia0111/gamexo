"""Test fixtures.

Requires the Compose Postgres to be running:

    docker compose up -d postgres
    cd apps/api && uv run pytest

Tests run against a separate `gamexo_test` database created by
docker/initdb/01-roles.sh with the *same* two-role privilege model as dev and
production. That matters more than it looks: if tests connected as an owner or
superuser, every RLS assertion below would pass vacuously.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import AsyncIterator

import pytest

API_DIR = Path(__file__).resolve().parent.parent

TEST_APP_URL = "postgresql+asyncpg://gamexo_app:gamexo_app_pw@localhost:5433/gamexo_test"
TEST_MIGRATION_URL = (
    "postgresql+asyncpg://gamexo_migrator:gamexo_migrator_pw@localhost:5433/gamexo_test"
)

# Set BEFORE importing anything from `app`: core.config builds a settings singleton
# at import time. Environment variables outrank the .env file in pydantic-settings,
# so this redirects the whole suite at the test database.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = TEST_APP_URL
os.environ["MIGRATION_DATABASE_URL"] = TEST_MIGRATION_URL
os.environ["DB_APP_USER"] = "gamexo_app"
os.environ["ALLOW_TENANT_HEADER"] = "true"
os.environ["TENANT_BASE_DOMAIN"] = "gamexo.app"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-the-validator"
os.environ["ACCESS_TOKEN_TTL_MINUTES"] = "30"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.auth.deps import clear_identity_cache  # noqa: E402
from app.auth.service import provision_tenant  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.security import Role, hash_password  # noqa: E402
from app.tenancy.resolver import invalidate_tenant_cache  # noqa: E402
from app.db.session import dispose_engine, tenant_session, untenanted_session  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import PlatformAdmin, User, UserStatus  # noqa: E402

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    """Apply the real migrations to the test database.

    A subprocess rather than alembic's Python API: env.py calls asyncio.run(), which
    cannot be re-entered from inside pytest-asyncio's running loop. Running the real
    migration also means the RLS policies and grants under test are the ones the
    migration actually produces, not a re-creation of them.
    """
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env={**os.environ, "MIGRATION_DATABASE_URL": TEST_MIGRATION_URL},
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing in the suite may send a real email.

    The mail transport is chosen by whichever credential is present, and the
    developer's own .env has a live Resend key — so without this a test that merely
    unsets SMTP_HOST reaches the real API and posts real mail. Both credentials are
    cleared by default; the tests that exercise a transport opt back in with their
    own fixture.
    """
    monkeypatch.setattr(settings, "resend_api_key", None)
    monkeypatch.setattr(settings, "smtp_host", None)


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    """Empty every table between tests.

    Connects as the migrator because TRUNCATE is a table-level privilege that RLS
    does not filter, and the app role deliberately holds no DELETE on audit_log.

    The in-process caches are cleared alongside it. Tenant resolution and identity
    lookups are memoised per process to keep them off the request path, and every
    test re-provisions the *same slug* with a *new* UUID — so a surviving entry
    would resolve to a tenant this TRUNCATE just deleted, and every query behind it
    would come back empty via RLS.
    """
    invalidate_tenant_cache()
    clear_identity_cache()
    engine = create_async_engine(TEST_MIGRATION_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE tenant RESTART IDENTITY CASCADE"))
        await conn.execute(text("TRUNCATE TABLE platform_admin RESTART IDENTITY CASCADE"))
    await engine.dispose()
    yield


@pytest.fixture(scope="session", autouse=True)
async def _dispose() -> AsyncIterator[None]:
    yield
    await dispose_engine()


class TenantFixture:
    """A provisioned academy plus its staff, for tests to act as."""

    def __init__(self, tenant: Tenant, admin: User) -> None:
        self.id: uuid.UUID = tenant.id
        self.slug: str = tenant.slug
        self.name: str = tenant.name
        self.admin_email: str = admin.email
        self.admin_id: uuid.UUID = admin.id

    @property
    def host(self) -> str:
        """The hostname that resolves to this academy in production."""
        return f"{self.slug}.gamexo.app"

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Tenant-ID": self.slug}


async def _make_tenant(slug: str, name: str) -> TenantFixture:
    async with untenanted_session() as session:
        tenant, admin = await provision_tenant(
            session,
            slug=slug,
            name=name,
            admin_email=f"admin@{slug}.example.com",
            admin_password=PASSWORD,
            admin_full_name=f"{name} Admin",
        )
        return TenantFixture(tenant, admin)


@pytest.fixture
async def tenant_a() -> TenantFixture:
    return await _make_tenant("alpha-academy", "Alpha Academy")


@pytest.fixture
async def tenant_b() -> TenantFixture:
    return await _make_tenant("beta-sports", "Beta Sports Club")


@pytest.fixture
async def platform_admin() -> PlatformAdmin:
    async with untenanted_session() as session:
        admin = PlatformAdmin(
            email="ops@gamexo.example.com",
            password_hash=hash_password(PASSWORD),
            full_name="Platform Operator",
        )
        session.add(admin)
        await session.flush()
        session.expunge(admin)
        return admin


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def make_user(
    tenant: TenantFixture,
    *,
    email: str,
    role: Role,
    status: UserStatus = UserStatus.ACTIVE,
    password: str = PASSWORD,
) -> User:
    """Add a staff member to an academy, through the tenant-scoped session."""
    async with tenant_session(tenant.id) as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=email.split("@")[0].title(),
            role=role,
            status=status,
        )
        session.add(user)
        await session.flush()
        session.expunge(user)
        return user


async def login(client: AsyncClient, tenant: TenantFixture, email: str, password: str) -> str:
    """Log in and return the access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers=tenant.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str, tenant: TenantFixture) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **tenant.headers}
