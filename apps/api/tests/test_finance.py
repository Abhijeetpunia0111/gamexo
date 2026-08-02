"""Finance: per-tenant numbering, invoicing, payment application, memberships."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import PASSWORD, TenantFixture, auth_headers, login
from tests.test_booking import at, book, setup_academy


async def make_customer(client: AsyncClient, ctx: dict, name="Arjun Mehta", phone="9876543210"):
    response = await client.post(
        "/api/v1/customers", json={"name": name, "phone": phone}, headers=ctx["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def make_plan(client: AsyncClient, ctx: dict, name="Tennis Elite"):
    response = await client.post(
        "/api/v1/membership-plans",
        json={
            "name": name,
            "category": "Tennis",
            "price_1m": "3500",
            "price_3m": "9500",
            "price_6m": "17000",
            "price_12m": "30000",
            "joining_fee": "1000",
            "benefits": ["Unlimited Court Hours", "Priority Booking"],
        },
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ── Per-tenant invoice numbering ────────────────────────────────────────────


async def test_invoice_numbers_start_at_one_for_every_academy(
    client: AsyncClient, tenant_a: TenantFixture, tenant_b: TenantFixture
) -> None:
    """The requirement: numbering must not leak volume across tenants.

    A global sequence would mean the second academy to sign up sees its very first
    invoice numbered XC-2024-0873 and learns exactly how much business the first one
    is doing. Both academies must independently start at 0001.
    """
    ctx_a = await setup_academy(client, tenant_a)
    ctx_b = await setup_academy(client, tenant_b)
    year = date.today().year

    for _ in range(3):
        response = await client.post(
            "/api/v1/invoices",
            json={
                "customer_name": "Alpha Customer",
                "items": [{"description": "Court", "qty": 1, "rate": "800", "amount": "800"}],
            },
            headers=ctx_a["headers"],
        )
        assert response.status_code == 201, response.text

    first_for_b = await client.post(
        "/api/v1/invoices",
        json={
            "customer_name": "Beta Customer",
            "items": [{"description": "Court", "qty": 1, "rate": "500", "amount": "500"}],
        },
        headers=ctx_b["headers"],
    )

    assert first_for_b.json()["invoice_no"] == f"XC-{year}-0001"

    numbers = [
        row["invoice_no"]
        for row in (await client.get("/api/v1/invoices", headers=ctx_a["headers"])).json()["items"]
    ]
    assert sorted(numbers) == [f"XC-{year}-000{n}" for n in (1, 2, 3)]


async def test_concurrent_invoices_never_share_a_number(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The row lock under concurrency.

    Ten invoices raised at once must produce ten distinct numbers. Without
    `SELECT ... FOR UPDATE` on the counter row, several transactions read the same
    `last_value` and issue duplicates — which the unique index then rejects, turning
    a silent corruption into a visible failure either way.
    """
    ctx = await setup_academy(client, tenant_a)

    async def raise_invoice(n: int):
        return await client.post(
            "/api/v1/invoices",
            json={
                "customer_name": f"Customer {n}",
                "items": [{"description": "Court", "qty": 1, "rate": "100", "amount": "100"}],
            },
            headers=ctx["headers"],
        )

    responses = await asyncio.gather(*(raise_invoice(n) for n in range(10)))
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses if r.status_code != 201]

    numbers = [r.json()["invoice_no"] for r in responses]
    assert len(set(numbers)) == 10, f"duplicate invoice numbers issued: {numbers}"


async def test_numbering_is_gapless(client: AsyncClient, tenant_a: TenantFixture) -> None:
    """No holes in the series — a statutory requirement for GST invoices.

    This is why the counter is a locked row rather than a Postgres sequence:
    `nextval` does not roll back, so a failed transaction would burn its number.
    """
    ctx = await setup_academy(client, tenant_a)
    year = date.today().year

    for _ in range(5):
        await client.post(
            "/api/v1/invoices",
            json={
                "customer_name": "Serial",
                "items": [{"description": "X", "qty": 1, "rate": "10", "amount": "10"}],
            },
            headers=ctx["headers"],
        )

    # A rejected request must not consume a number.
    rejected = await client.post(
        "/api/v1/invoices", json={"customer_name": "", "items": []}, headers=ctx["headers"]
    )
    assert rejected.status_code == 422

    following = await client.post(
        "/api/v1/invoices",
        json={
            "customer_name": "After failure",
            "items": [{"description": "X", "qty": 1, "rate": "10", "amount": "10"}],
        },
        headers=ctx["headers"],
    )
    assert following.json()["invoice_no"] == f"XC-{year}-0006"


async def test_member_numbers_use_their_own_series(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Four independent series per academy: invoice, member, coach, student."""
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)
    year = date.today().year

    # An invoice first, so the two series are demonstrably independent.
    await client.post(
        "/api/v1/invoices",
        json={
            "customer_name": "Someone",
            "items": [{"description": "X", "qty": 1, "rate": "10", "amount": "10"}],
        },
        headers=ctx["headers"],
    )

    customer_id = await make_customer(client, ctx)
    response = await client.post(
        "/api/v1/memberships",
        json={"customer_id": customer_id, "plan_id": plan_id, "duration": "12m"},
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    assert response.json()["subscription"]["member_no"] == "XC-M-0001"
    assert response.json()["invoice"]["invoice_no"] == f"XC-{year}-0002"


async def test_the_number_prefix_is_per_tenant(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """White-label: a customer's invoices carry their own initials, not mine."""
    from sqlalchemy import select

    from app.db.session import tenant_session
    from app.models.tenant import TenantSettings

    ctx = await setup_academy(client, tenant_a)
    async with tenant_session(tenant_a.id) as session:
        settings = (await session.execute(select(TenantSettings))).scalar_one()
        settings.invoice_prefix = "ALPHA"

    response = await client.post(
        "/api/v1/invoices",
        json={
            "customer_name": "Branded",
            "items": [{"description": "X", "qty": 1, "rate": "10", "amount": "10"}],
        },
        headers=ctx["headers"],
    )
    assert response.json()["invoice_no"].startswith("ALPHA-")


# ── Invoicing a booking ─────────────────────────────────────────────────────


async def test_invoicing_a_booking_matches_the_quoted_total(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    created = await book(
        client,
        ctx,
        court=ctx["court_1"],
        starts_at=at(1, 10),
        equipment=[{"equipment_id": ctx["equipment_id"], "qty": 2}],
    )
    booking = created.json()

    invoice = await client.post(
        f"/api/v1/bookings/{booking['id']}/invoice", headers=ctx["headers"]
    )
    assert invoice.status_code == 201, invoice.text
    body = invoice.json()

    assert Decimal(body["total"]) == Decimal(booking["total"])
    assert Decimal(body["gst"]) == Decimal(booking["taxes"])
    assert len(body["items"]) == 2  # court + one equipment line


async def test_invoicing_a_booking_twice_returns_the_same_invoice(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Re-invoicing would issue a second number for the same money."""
    ctx = await setup_academy(client, tenant_a)
    created = await book(client, ctx, court=ctx["court_1"], starts_at=at(2, 10))
    booking_id = created.json()["id"]

    first = await client.post(f"/api/v1/bookings/{booking_id}/invoice", headers=ctx["headers"])
    second = await client.post(f"/api/v1/bookings/{booking_id}/invoice", headers=ctx["headers"])

    assert first.json()["id"] == second.json()["id"]
    assert first.json()["invoice_no"] == second.json()["invoice_no"]

    listed = await client.get("/api/v1/invoices", headers=ctx["headers"])
    assert listed.json()["total"] == 1


# ── Payments ────────────────────────────────────────────────────────────────


async def test_partial_then_full_payment_updates_invoice_and_booking(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    created = await book(client, ctx, court=ctx["court_1"], starts_at=at(3, 10))
    booking_id = created.json()["id"]
    total = Decimal(created.json()["total"])  # 944.00

    invoice = await client.post(f"/api/v1/bookings/{booking_id}/invoice", headers=ctx["headers"])
    invoice_id = invoice.json()["id"]

    part = await client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice_id, "amount": "400", "method": "cash"},
        headers=ctx["headers"],
    )
    assert part.status_code == 201, part.text

    mid = await client.get(f"/api/v1/invoices/{invoice_id}", headers=ctx["headers"])
    assert mid.json()["status"] == "pending"
    assert Decimal(mid.json()["balance_due"]) == total - Decimal("400")

    booking = await client.get(f"/api/v1/bookings/{booking_id}", headers=ctx["headers"])
    assert booking.json()["payment_status"] == "partial"

    await client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice_id, "amount": str(total - Decimal("400")), "method": "upi"},
        headers=ctx["headers"],
    )

    settled = await client.get(f"/api/v1/invoices/{invoice_id}", headers=ctx["headers"])
    assert settled.json()["status"] == "paid"
    assert Decimal(settled.json()["balance_due"]) == Decimal("0.00")
    # Two methods on one invoice renders as "split", matching the Payments page.
    assert settled.json()["payment_method"] == "split"

    booking = await client.get(f"/api/v1/bookings/{booking_id}", headers=ctx["headers"])
    assert booking.json()["payment_status"] == "paid"


async def test_overpaying_an_invoice_is_refused(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """At a reception desk an over-payment is almost always a typo.

    Absorbing it silently creates a credit nobody tracks and an invoice that
    reconciles to the wrong figure.
    """
    ctx = await setup_academy(client, tenant_a)
    created = await book(client, ctx, court=ctx["court_1"], starts_at=at(4, 10))
    invoice = await client.post(
        f"/api/v1/bookings/{created.json()['id']}/invoice", headers=ctx["headers"]
    )

    response = await client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice.json()["id"], "amount": "99999", "method": "cash"},
        headers=ctx["headers"],
    )
    assert response.status_code == 409
    assert "balance_due" in response.json()["error"]["details"]


async def test_payments_overview_groups_by_method(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    created = await book(client, ctx, court=ctx["court_1"], starts_at=at(5, 10))
    invoice = await client.post(
        f"/api/v1/bookings/{created.json()['id']}/invoice", headers=ctx["headers"]
    )
    invoice_id = invoice.json()["id"]

    for amount, method in (("100", "cash"), ("200", "upi"), ("50", "cash")):
        await client.post(
            "/api/v1/payments",
            json={"invoice_id": invoice_id, "amount": amount, "method": method},
            headers=ctx["headers"],
        )

    overview = await client.get("/api/v1/payments/overview", headers=ctx["headers"])
    body = overview.json()
    assert Decimal(body["total_collected"]) == Decimal("350.00")
    assert body["transaction_count"] == 3

    by_method = {row["method"]: row for row in body["by_method"]}
    assert Decimal(by_method["cash"]["amount"]) == Decimal("150.00")
    assert by_method["cash"]["count"] == 2
    assert Decimal(by_method["upi"]["amount"]) == Decimal("200.00")


async def test_finance_records_do_not_cross_academies(
    client: AsyncClient, tenant_a: TenantFixture, tenant_b: TenantFixture
) -> None:
    ctx_a = await setup_academy(client, tenant_a)
    ctx_b = await setup_academy(client, tenant_b)

    invoice = await client.post(
        "/api/v1/invoices",
        json={
            "customer_name": "Alpha only",
            "items": [{"description": "X", "qty": 1, "rate": "500", "amount": "500"}],
        },
        headers=ctx_a["headers"],
    )
    invoice_id = invoice.json()["id"]

    assert (
        await client.get(f"/api/v1/invoices/{invoice_id}", headers=ctx_b["headers"])
    ).status_code == 404
    assert (await client.get("/api/v1/invoices", headers=ctx_b["headers"])).json()["total"] == 0

    # And B cannot pay A's invoice.
    attempt = await client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice_id, "amount": "100", "method": "cash"},
        headers=ctx_b["headers"],
    )
    assert attempt.status_code == 404


# ── Memberships ─────────────────────────────────────────────────────────────


async def test_membership_creates_a_subscription_and_its_invoice(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)
    customer_id = await make_customer(client, ctx)

    response = await client.post(
        "/api/v1/memberships",
        json={
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration": "12m",
            "start_date": "2026-01-15",
        },
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["subscription"]["expiry_date"] == "2027-01-15"
    assert body["subscription"]["status"] == "active"
    # 30000 plan + 1000 joining fee, + 18% GST
    assert Decimal(body["invoice"]["subtotal"]) == Decimal("31000.00")
    assert Decimal(body["invoice"]["gst"]) == Decimal("5580.00")
    assert Decimal(body["invoice"]["total"]) == Decimal("36580.00")

    # The customer is now a member.
    customer = await client.get(f"/api/v1/customers/{customer_id}", headers=ctx["headers"])
    assert customer.json()["member_type"] == "member"


async def test_month_arithmetic_clamps_to_short_months(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """31 Jan + 1 month is 28 Feb, not 3 March.

    Adding 30 days instead would drift the renewal date every cycle, and members
    notice when an annual membership expires a few days earlier each year.
    """
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)
    customer_id = await make_customer(client, ctx)

    response = await client.post(
        "/api/v1/memberships",
        json={
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration": "1m",
            "start_date": "2027-01-31",
        },
        headers=ctx["headers"],
    )
    assert response.json()["subscription"]["expiry_date"] == "2027-02-28"


async def test_days_left_and_renewal_due_are_computed(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Never stored: mock record mr-4's `daysLeft: 1` is wrong tomorrow."""
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)
    customer_id = await make_customer(client, ctx)

    start = date.today() - timedelta(days=350)
    response = await client.post(
        "/api/v1/memberships",
        json={
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration": "12m",
            "start_date": start.isoformat(),
        },
        headers=ctx["headers"],
    )
    subscription = response.json()["subscription"]
    assert 0 < subscription["days_left"] <= 20
    assert subscription["renewal_due"] is True


async def test_early_renewal_extends_from_the_current_expiry(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Renewing early must not forfeit days already paid for."""
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)
    customer_id = await make_customer(client, ctx)

    start = date.today()
    created = await client.post(
        "/api/v1/memberships",
        json={
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration": "12m",
            "start_date": start.isoformat(),
        },
        headers=ctx["headers"],
    )
    subscription_id = created.json()["subscription"]["id"]
    original_expiry = date.fromisoformat(created.json()["subscription"]["expiry_date"])

    renewed = await client.post(
        f"/api/v1/memberships/{subscription_id}/renew",
        json={"duration": "12m"},
        headers=ctx["headers"],
    )
    assert renewed.status_code == 200, renewed.text
    new_expiry = date.fromisoformat(renewed.json()["subscription"]["expiry_date"])

    assert new_expiry.year == original_expiry.year + 1
    # A second invoice was raised for the renewal.
    assert renewed.json()["invoice"]["invoice_no"] != created.json()["invoice"]["invoice_no"]


async def test_pause_and_cancel(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)
    customer_id = await make_customer(client, ctx)

    created = await client.post(
        "/api/v1/memberships",
        json={"customer_id": customer_id, "plan_id": plan_id, "duration": "3m"},
        headers=ctx["headers"],
    )
    subscription_id = created.json()["subscription"]["id"]

    paused = await client.post(
        f"/api/v1/memberships/{subscription_id}/pause", headers=ctx["headers"]
    )
    assert paused.json()["status"] == "paused"

    again = await client.post(
        f"/api/v1/memberships/{subscription_id}/pause", headers=ctx["headers"]
    )
    assert again.status_code == 409

    cancelled = await client.post(
        f"/api/v1/memberships/{subscription_id}/cancel", headers=ctx["headers"]
    )
    assert cancelled.json()["status"] == "cancelled"


async def test_plan_active_count_is_derived(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)

    for n in range(3):
        customer_id = await make_customer(client, ctx, name=f"Member {n}", phone=f"90000000{n:02d}")
        await client.post(
            "/api/v1/memberships",
            json={"customer_id": customer_id, "plan_id": plan_id, "duration": "1m"},
            headers=ctx["headers"],
        )

    plans = await client.get("/api/v1/membership-plans", headers=ctx["headers"])
    assert plans.json()[0]["active_count"] == 3

    # Cancelling one drops the count — because it is a query, not a counter.
    memberships = await client.get("/api/v1/memberships", headers=ctx["headers"])
    await client.post(
        f"/api/v1/memberships/{memberships.json()['items'][0]['id']}/cancel",
        headers=ctx["headers"],
    )
    plans = await client.get("/api/v1/membership-plans", headers=ctx["headers"])
    assert plans.json()[0]["active_count"] == 2


async def test_renewal_due_filter(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await setup_academy(client, tenant_a)
    plan_id = await make_plan(client, ctx)

    expiring = await make_customer(client, ctx, name="Expiring Soon", phone="9111111111")
    comfortable = await make_customer(client, ctx, name="Plenty Left", phone="9222222222")

    await client.post(
        "/api/v1/memberships",
        json={
            "customer_id": expiring,
            "plan_id": plan_id,
            "duration": "1m",
            "start_date": (date.today() - timedelta(days=25)).isoformat(),
        },
        headers=ctx["headers"],
    )
    await client.post(
        "/api/v1/memberships",
        json={
            "customer_id": comfortable,
            "plan_id": plan_id,
            "duration": "12m",
            "start_date": date.today().isoformat(),
        },
        headers=ctx["headers"],
    )

    due = await client.get(
        "/api/v1/memberships", params={"renewal_due": True}, headers=ctx["headers"]
    )
    assert due.json()["total"] == 1
    assert due.json()["items"][0]["customer_id"] == expiring
