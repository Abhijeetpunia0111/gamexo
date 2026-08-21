"""Payment gateway configuration: encryption, routing exclusivity, who may read it.

Most of these assert a negative — that a secret is *not* in a response, that the
kiosk *cannot* reach a credential, that two gateways *cannot* both claim a surface.
Those are the failures that stay invisible: a screen that leaks a Razorpay key
looks identical to one that does not, right up until the key is used.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.core.crypto import decrypt
from app.core.security import Role
from app.db.session import tenant_session
from tests.conftest import TenantFixture, auth_headers, login, make_user

RZP = {"key_id": "rzp_test_ABC1234567", "key_secret": "razorpay-secret-value-8f2a"}
CFR = {"app_id": "TEST_APP_ID_00001", "secret_key": "cashfree-secret-value-aaaa"}


async def admin_headers(client: AsyncClient, tenant: TenantFixture) -> dict[str, str]:
    token = await login(client, tenant, tenant.admin_email, "correct-horse-battery")
    return auth_headers(token, tenant)


async def kiosk_headers(client: AsyncClient, tenant: TenantFixture) -> dict[str, str]:
    await make_user(tenant, email=f"kiosk@{tenant.slug}.example.com", role=Role.KIOSK)
    token = await login(client, tenant, f"kiosk@{tenant.slug}.example.com", "correct-horse-battery")
    return auth_headers(token, tenant)


async def connect(
    client: AsyncClient,
    headers: dict[str, str],
    provider: str,
    values: dict[str, str],
    mode: str = "test",
):
    """Save credentials without calling the provider.

    `verify: False` everywhere in this file. A test that reaches api.razorpay.com is
    not testing our code — it fails on a plane, and it makes the suite's result
    depend on a third party's uptime.
    """
    return await client.put(
        f"/api/v1/payments/providers/{provider}",
        json={"mode": mode, "values": values, "verify": False},
        headers=headers,
    )


# ── The catalog drives the form ─────────────────────────────────────────────


async def test_catalog_describes_every_field(client: AsyncClient, tenant_a: TenantFixture) -> None:
    headers = await admin_headers(client, tenant_a)
    response = await client.get("/api/v1/payments/providers", headers=headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["secrets_available"] is True
    providers = {p["id"]: p for p in body["providers"]}
    assert {"razorpay", "cashfree", "phonepe", "payu", "stripe"} <= set(providers)

    # The screen renders its inputs from this, so a field with no label is a blank
    # box the admin has to guess at.
    for provider in body["providers"]:
        assert provider["fields"], provider["id"]
        for field in provider["fields"]:
            assert field["label"] and field["help"]
        assert provider["credentials_url"].startswith("https://")
        assert provider["config"] is None


# ── Secrets ─────────────────────────────────────────────────────────────────


async def test_secret_is_encrypted_and_never_returned(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    headers = await admin_headers(client, tenant_a)
    response = await connect(client, headers, "razorpay", RZP)
    assert response.status_code == 200, response.text

    # Not in this response...
    assert RZP["key_secret"] not in response.text
    config = response.json()["config"]
    assert config["public_config"] == {"key_id": RZP["key_id"]}
    assert config["secret_hints"] == {"key_secret": "8f2a"}

    # ...nor in any later read...
    listing = await client.get("/api/v1/payments/providers", headers=headers)
    assert RZP["key_secret"] not in listing.text

    # ...and not in the column either. The last one is the point: the other two
    # would still pass if the value were sitting in the database in plain text.
    async with tenant_session(tenant_a.id) as session:
        stored = (
            await session.execute(text("select secrets_ciphertext from payment_provider_config"))
        ).scalar_one()
    assert RZP["key_secret"] not in stored
    assert json.loads(decrypt(stored))["key_secret"] == RZP["key_secret"]


async def test_blank_secret_keeps_the_stored_one(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The whole reason the form can be edited at all.

    The browser is never given the real secret, so an admin changing only the key id
    submits a blank Key Secret. Treating that as "clear it" would wipe a working
    credential on the most ordinary edit there is.
    """
    headers = await admin_headers(client, tenant_a)
    await connect(client, headers, "razorpay", RZP)

    response = await connect(client, headers, "razorpay", {"key_id": "rzp_test_ZZZ9999999"})
    assert response.status_code == 200, response.text
    config = response.json()["config"]
    assert config["public_config"]["key_id"] == "rzp_test_ZZZ9999999"
    assert config["secret_hints"] == {"key_secret": "8f2a"}

    async with tenant_session(tenant_a.id) as session:
        stored = (
            await session.execute(text("select secrets_ciphertext from payment_provider_config"))
        ).scalar_one()
    assert json.loads(decrypt(stored))["key_secret"] == RZP["key_secret"]


@pytest.mark.parametrize(
    "mode,values,expected",
    [
        ("live", RZP, "test credential"),
        ("test", {"key_id": "rzp_test_ABC1234567"}, "required"),
        (
            "test",
            {"key_id": "rzp_test_ABC1234567", "key_secret": "rzp_test_ABC1234567"},
            "same as a public field",
        ),
    ],
    ids=["test-key-saved-as-live", "missing-secret", "secret-pasted-in-wrong-box"],
)
async def test_credential_shape_is_checked(
    client: AsyncClient, tenant_a: TenantFixture, mode: str, values: dict, expected: str
) -> None:
    headers = await admin_headers(client, tenant_a)
    response = await connect(client, headers, "razorpay", values, mode=mode)

    assert response.status_code == 400, response.text
    problems = response.json()["error"]["details"]["problems"]
    assert any(expected in p for p in problems), problems


# ── Routing ─────────────────────────────────────────────────────────────────


async def test_only_one_gateway_collects_per_surface(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    headers = await admin_headers(client, tenant_a)
    await connect(client, headers, "razorpay", RZP)
    await connect(client, headers, "cashfree", CFR)

    claimed = await client.patch(
        "/api/v1/payments/providers/razorpay/routing",
        json={"collect_on_web": True, "collect_on_pos": True},
        headers=headers,
    )
    assert claimed.json()["collect_on_web"] and claimed.json()["collect_on_pos"]

    # Cashfree takes the counter. Razorpay must lose it — and must keep the
    # dashboard, which nobody asked to change.
    await client.patch(
        "/api/v1/payments/providers/cashfree/routing",
        json={"collect_on_pos": True},
        headers=headers,
    )

    listing = await client.get("/api/v1/payments/providers", headers=headers)
    by = {p["id"]: p["config"] for p in listing.json()["providers"]}
    assert by["razorpay"]["collect_on_pos"] is False
    assert by["razorpay"]["collect_on_web"] is True
    assert by["cashfree"]["collect_on_pos"] is True
    assert by["cashfree"]["collect_on_web"] is False


async def test_database_refuses_two_gateways_on_one_surface(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The guarantee is the partial unique index, not the handler.

    Written as a raw UPDATE precisely because it bypasses the router. If this ever
    starts passing, the invariant has become a convention.
    """
    headers = await admin_headers(client, tenant_a)
    await connect(client, headers, "razorpay", RZP)
    await connect(client, headers, "cashfree", CFR)
    await client.patch(
        "/api/v1/payments/providers/razorpay/routing",
        json={"collect_on_web": True},
        headers=headers,
    )

    with pytest.raises(Exception) as excinfo:
        async with tenant_session(tenant_a.id) as session:
            await session.execute(text("update payment_provider_config set collect_on_web = true"))
            await session.flush()
    assert "uq_payment_provider_one_web" in str(excinfo.value)


async def test_gateway_without_credentials_cannot_collect(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    headers = await admin_headers(client, tenant_a)
    response = await client.patch(
        "/api/v1/payments/providers/razorpay/routing",
        json={"collect_on_web": True},
        headers=headers,
    )
    assert response.status_code == 404  # not connected at all

    await connect(client, headers, "razorpay", RZP)
    await client.delete("/api/v1/payments/providers/razorpay", headers=headers)
    gone = await client.patch(
        "/api/v1/payments/providers/razorpay/routing",
        json={"collect_on_web": True},
        headers=headers,
    )
    assert gone.status_code == 404


# ── Who may read what ───────────────────────────────────────────────────────


async def test_kiosk_cannot_reach_credentials(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The counter tablet is the most exposed login in the academy.

    It runs on a shared device on a public counter, so anything it can read should
    be assumed readable by anyone standing there.
    """
    admin = await admin_headers(client, tenant_a)
    await connect(client, admin, "razorpay", RZP)
    kiosk = await kiosk_headers(client, tenant_a)

    assert (await client.get("/api/v1/payments/providers", headers=kiosk)).status_code == 403
    assert (await connect(client, kiosk, "stripe", {})).status_code == 403
    assert (
        await client.delete("/api/v1/payments/providers/razorpay", headers=kiosk)
    ).status_code == 403


async def test_kiosk_reads_the_active_gateway_public_half(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The one thing the counter does need: which gateway to charge through."""
    admin = await admin_headers(client, tenant_a)
    await connect(client, admin, "cashfree", CFR)
    await client.patch(
        "/api/v1/payments/providers/cashfree/routing",
        json={"collect_on_pos": True},
        headers=admin,
    )

    kiosk = await kiosk_headers(client, tenant_a)
    response = await client.get("/api/v1/payments/active?surface=pos", headers=kiosk)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "cashfree"
    assert body["public_config"] == {"app_id": CFR["app_id"]}
    assert set(body) == {"provider", "label", "mode", "public_config"}
    assert CFR["secret_key"] not in response.text


async def test_no_gateway_for_a_surface_is_not_an_error(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """An academy on cash and UPI is the normal case, not a broken configuration."""
    kiosk = await kiosk_headers(client, tenant_a)
    response = await client.get("/api/v1/payments/active?surface=web", headers=kiosk)
    assert response.status_code == 200
    assert response.json() is None


# ── Tenancy ─────────────────────────────────────────────────────────────────


async def test_one_academy_cannot_see_anothers_gateway(
    client: AsyncClient, tenant_a: TenantFixture, tenant_b: TenantFixture
) -> None:
    a_headers = await admin_headers(client, tenant_a)
    await connect(client, a_headers, "razorpay", RZP)

    b_headers = await admin_headers(client, tenant_b)
    listing = await client.get("/api/v1/payments/providers", headers=b_headers)

    assert listing.status_code == 200
    assert all(p["config"] is None for p in listing.json()["providers"])
    assert RZP["key_id"] not in listing.text

    # And B connecting the same provider is a separate row, not a collision on A's.
    response = await connect(
        client, b_headers, "razorpay", {"key_id": "rzp_test_BBB2222222", "key_secret": "b-secret-bbbb"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["config"]["public_config"]["key_id"] == "rzp_test_BBB2222222"


async def test_connecting_the_same_gateway_twice_edits_it(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """PUT is idempotent — the screen uses one call for "connect" and "edit"."""
    headers = await admin_headers(client, tenant_a)
    await connect(client, headers, "razorpay", RZP)
    await connect(client, headers, "razorpay", {**RZP, "key_secret": "second-secret-value-9c3b"})

    listing = await client.get("/api/v1/payments/providers", headers=headers)
    configs = [p["config"] for p in listing.json()["providers"] if p["config"]]
    assert len(configs) == 1
    assert configs[0]["secret_hints"]["key_secret"] == "9c3b"


async def test_disconnect_removes_the_credential(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    headers = await admin_headers(client, tenant_a)
    await connect(client, headers, "razorpay", RZP)

    assert (
        await client.delete("/api/v1/payments/providers/razorpay", headers=headers)
    ).status_code == 204

    listing = await client.get("/api/v1/payments/providers", headers=headers)
    assert all(p["config"] is None for p in listing.json()["providers"])

    async with tenant_session(tenant_a.id) as session:
        remaining = (
            await session.execute(text("select count(*) from payment_provider_config"))
        ).scalar_one()
    assert remaining == 0


async def test_without_an_encryption_key_credentials_are_refused_not_stored_plainly(
    client: AsyncClient, tenant_a: TenantFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deployment with no SECRETS_ENCRYPTION_KEY must refuse, loudly.

    The tempting failure — fall back to storing the key in plain text — would be
    invisible from every screen and would put live payment credentials in the clear
    for every academy. So the save is rejected with a 409 that names the missing
    setting, and the Integrations screen disables the form rather than inviting
    someone to paste a live secret into it.

    The cache_clear calls are load-bearing: `crypto._box` is lru_cached, so without
    them this test would read a key that was resolved by an earlier test.
    """
    from app.core import crypto

    monkeypatch.setattr(settings, "secrets_encryption_key", None)
    crypto._box.cache_clear()
    try:
        headers = await admin_headers(client, tenant_a)

        listing = await client.get("/api/v1/payments/providers", headers=headers)
        assert listing.json()["secrets_available"] is False

        response = await connect(client, headers, "razorpay", RZP)
        assert response.status_code == 409, response.text
        assert "SECRETS_ENCRYPTION_KEY" in response.json()["error"]["message"]

        async with tenant_session(tenant_a.id) as session:
            rows = (
                await session.execute(text("select count(*) from payment_provider_config"))
            ).scalar_one()
        assert rows == 0
    finally:
        crypto._box.cache_clear()


async def test_the_actor_is_recorded(client: AsyncClient, tenant_a: TenantFixture) -> None:
    """Who pasted this key is the first question when a payment stops working."""
    headers = await admin_headers(client, tenant_a)
    response = await connect(client, headers, "razorpay", RZP)
    assert response.json()["config"]["updated_by_email"] == tenant_a.admin_email
