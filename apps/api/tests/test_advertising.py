"""Advertising: inventory status, contract overlap, the sales pipeline."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import PASSWORD, TenantFixture, auth_headers, login


async def setup_inventory(client: AsyncClient, tenant: TenantFixture) -> dict:
    token = await login(client, tenant, tenant.admin_email, PASSWORD)
    h = auth_headers(token, tenant)

    spot = await client.post(
        "/api/v1/advertising/spots",
        json={
            "code": "Z1-B01",
            "name": "Main Entrance Banner",
            "zone": "Zone A – Entrance",
            "location": "Main Gate, left side pillar",
            "dimensions": "8ft × 4ft",
            "type": "outdoor",
            "display_type": "Vinyl Banner",
            "visibility_rating": "9.5",
            "price_monthly": "15000",
            "price_quarterly": "42000",
            "price_yearly": "150000",
        },
        headers=h,
    )
    assert spot.status_code == 201, spot.text

    second = await client.post(
        "/api/v1/advertising/spots",
        json={
            "code": "Z2-T01",
            "name": "Tennis Court Hoarding",
            "zone": "Zone B – Courts",
            "type": "outdoor",
            "price_monthly": "25000",
            "price_quarterly": "70000",
            "price_yearly": "250000",
        },
        headers=h,
    )
    return {"headers": h, "spot_1": spot.json()["id"], "spot_2": second.json()["id"]}


async def make_contract(client: AsyncClient, ctx: dict, **overrides):
    payload = {
        "spot_id": ctx["spot_1"],
        "company": "Decathlon India",
        "brand": "Decathlon",
        "contact_name": "Rahul Gupta",
        "phone": "9800011223",
        "email": "rahul@decathlon.example.com",
        "gst": "27AABCX1234Z1ZV",
        "start_date": "2027-04-01",
        "duration_months": 6,
        "status": "confirmed",
    }
    payload.update(overrides)
    return await client.post("/api/v1/advertising/contracts", json=payload, headers=ctx["headers"])


# ── Overlap ─────────────────────────────────────────────────────────────────


async def test_overlapping_confirmed_contracts_are_rejected(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """An ad spot is as double-bookable as a court."""
    ctx = await setup_inventory(client, tenant_a)

    first = await make_contract(client, ctx)
    assert first.status_code == 201, first.text

    clash = await make_contract(client, ctx, company="Puma India", start_date="2027-07-01")
    assert clash.status_code == 409
    assert clash.json()["error"]["details"]["conflicting_contract_id"] == first.json()["id"]


async def test_competing_quotations_on_one_spot_are_allowed(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The constraint excludes drafts and quotations on purpose.

    Sending proposals for the same hoarding to two advertisers is how the sales
    pipeline works; blocking it would break the business, not protect it.
    """
    ctx = await setup_inventory(client, tenant_a)

    first = await make_contract(client, ctx, company="Decathlon", status="quotation")
    second = await make_contract(client, ctx, company="Puma", status="quotation")
    third = await make_contract(client, ctx, company="Yonex", status="draft")

    assert first.status_code == 201
    assert second.status_code == 201, second.text
    assert third.status_code == 201


async def test_confirming_a_quotation_is_where_the_conflict_surfaces(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Two quotes are fine; the second one to be confirmed loses."""
    ctx = await setup_inventory(client, tenant_a)

    winner = await make_contract(client, ctx, company="Decathlon", status="quotation")
    loser = await make_contract(client, ctx, company="Puma", status="quotation")

    confirmed = await client.patch(
        f"/api/v1/advertising/contracts/{winner.json()['id']}",
        json={"status": "confirmed"},
        headers=ctx["headers"],
    )
    assert confirmed.status_code == 200, confirmed.text

    refused = await client.patch(
        f"/api/v1/advertising/contracts/{loser.json()['id']}",
        json={"status": "confirmed"},
        headers=ctx["headers"],
    )
    assert refused.status_code == 409


async def test_back_to_back_campaigns_are_allowed(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """A 6-month term ends the day before the next begins, so they do not overlap."""
    ctx = await setup_inventory(client, tenant_a)

    first = await make_contract(client, ctx, start_date="2027-04-01", duration_months=6)
    assert first.json()["end_date"] == "2027-09-30"

    second = await make_contract(
        client, ctx, company="Puma India", start_date="2027-10-01", duration_months=6
    )
    assert second.status_code == 201, second.text


async def test_different_spots_do_not_conflict(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_inventory(client, tenant_a)
    first = await make_contract(client, ctx, spot_id=ctx["spot_1"])
    second = await make_contract(client, ctx, spot_id=ctx["spot_2"], company="Wilson")
    assert first.status_code == 201
    assert second.status_code == 201


async def test_two_academies_can_sell_the_same_period(
    client: AsyncClient, tenant_a: TenantFixture, tenant_b: TenantFixture
) -> None:
    ctx_a = await setup_inventory(client, tenant_a)
    ctx_b = await setup_inventory(client, tenant_b)

    assert (await make_contract(client, ctx_a)).status_code == 201
    assert (await make_contract(client, ctx_b)).status_code == 201

    # And neither can see the other's pipeline.
    assert (await client.get("/api/v1/advertising/contracts", headers=ctx_b["headers"])).json()[
        "total"
    ] == 1


# ── Derived status ──────────────────────────────────────────────────────────


async def test_spot_status_is_derived_from_contract_dates(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """available → reserved → occupied → available, with nothing stored."""
    ctx = await setup_inventory(client, tenant_a)

    before = await client.get("/api/v1/advertising/spots", headers=ctx["headers"])
    assert next(s for s in before.json() if s["id"] == ctx["spot_1"])["status"] == "available"

    await make_contract(client, ctx, start_date="2027-04-01", duration_months=6)

    # Ahead of the start date the spot is reserved…
    reserved = await client.get(
        "/api/v1/advertising/spots", params={"on_date": "2027-01-15"}, headers=ctx["headers"]
    )
    assert next(s for s in reserved.json() if s["id"] == ctx["spot_1"])["status"] == "reserved"

    # …during it, occupied…
    during = await client.get(
        "/api/v1/advertising/spots", params={"on_date": "2027-06-01"}, headers=ctx["headers"]
    )
    row = next(s for s in during.json() if s["id"] == ctx["spot_1"])
    assert row["status"] == "occupied"
    assert row["occupied_until"] == "2027-09-30"

    # …and afterwards, available again — with no job needed to reset it.
    after = await client.get(
        "/api/v1/advertising/spots", params={"on_date": "2027-12-01"}, headers=ctx["headers"]
    )
    assert next(s for s in after.json() if s["id"] == ctx["spot_1"])["status"] == "available"


async def test_a_blocked_spot_cannot_be_sold(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await setup_inventory(client, tenant_a)
    await client.patch(
        f"/api/v1/advertising/spots/{ctx['spot_1']}",
        json={"is_sellable": False, "blocked_status": "maintenance"},
        headers=ctx["headers"],
    )

    spots = await client.get("/api/v1/advertising/spots", headers=ctx["headers"])
    assert next(s for s in spots.json() if s["id"] == ctx["spot_1"])["status"] == "maintenance"

    refused = await make_contract(client, ctx)
    assert refused.status_code == 409


# ── Pricing and payments ────────────────────────────────────────────────────


async def test_term_pricing_uses_the_discounted_rate_card(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """A 12-month deal uses the yearly rate, not twelve monthlies.

    Charging 12 × ₹15,000 = ₹1,80,000 instead of the ₹1,50,000 annual rate would
    quietly overcharge every annual advertiser.
    """
    ctx = await setup_inventory(client, tenant_a)

    yearly = await make_contract(client, ctx, duration_months=12, start_date="2028-01-01")
    assert Decimal(yearly.json()["total"]) == Decimal("150000.00")

    quarterly = await make_contract(
        client, ctx, spot_id=ctx["spot_2"], duration_months=3, start_date="2028-01-01"
    )
    assert Decimal(quarterly.json()["total"]) == Decimal("70000.00")


async def test_fees_and_discounts_apply_to_the_total(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_inventory(client, tenant_a)
    response = await make_contract(
        client,
        ctx,
        duration_months=6,
        installation_fee="5000",
        printing_fee="2000",
        discount="3000",
    )
    # 6 months = 2 quarters at 42000, - 3000 discount + 5000 + 2000
    assert Decimal(response.json()["total"]) == Decimal("88000.00")


async def test_contract_payments_track_the_balance(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_inventory(client, tenant_a)
    contract = await make_contract(client, ctx, duration_months=6)
    contract_id = contract.json()["id"]
    total = Decimal(contract.json()["total"])
    assert contract.json()["payment_status"] == "pending"

    part = await client.post(
        f"/api/v1/advertising/contracts/{contract_id}/payments",
        json={"amount": "40000"},
        headers=ctx["headers"],
    )
    assert part.json()["payment_status"] == "partial"
    assert Decimal(part.json()["balance_due"]) == total - Decimal("40000")

    rest = await client.post(
        f"/api/v1/advertising/contracts/{contract_id}/payments",
        json={"amount": str(total - Decimal("40000"))},
        headers=ctx["headers"],
    )
    assert rest.json()["payment_status"] == "paid"
    assert Decimal(rest.json()["balance_due"]) == Decimal("0.00")

    overpay = await client.post(
        f"/api/v1/advertising/contracts/{contract_id}/payments",
        json={"amount": "1"},
        headers=ctx["headers"],
    )
    assert overpay.status_code == 409


async def test_timeline_accumulates_events(client: AsyncClient, tenant_a: TenantFixture) -> None:
    """The JSONB timeline the frontend's contract drawer renders."""
    ctx = await setup_inventory(client, tenant_a)
    contract = await make_contract(client, ctx, status="quotation")
    contract_id = contract.json()["id"]
    assert [e["type"] for e in contract.json()["timeline"]] == ["created"]

    await client.patch(
        f"/api/v1/advertising/contracts/{contract_id}",
        json={"status": "confirmed"},
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/v1/advertising/contracts/{contract_id}/payments",
        json={"amount": "10000"},
        headers=ctx["headers"],
    )

    final = await client.get(
        f"/api/v1/advertising/contracts/{contract_id}", headers=ctx["headers"]
    )
    kinds = [e["type"] for e in final.json()["timeline"]]
    assert kinds == ["created", "confirmed", "payment"]


async def test_renewal_creates_a_follow_on_term(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The old term stops holding the spot so the new one can take it."""
    ctx = await setup_inventory(client, tenant_a)
    original = await make_contract(client, ctx, start_date="2027-04-01", duration_months=6)
    original_id = original.json()["id"]

    renewed = await client.post(
        f"/api/v1/advertising/contracts/{original_id}/renew",
        json={"duration_months": 12},
        headers=ctx["headers"],
    )
    assert renewed.status_code == 201, renewed.text
    assert renewed.json()["start_date"] == "2027-10-01"
    assert renewed.json()["end_date"] == "2028-09-30"
    assert renewed.json()["status"] == "confirmed"
    assert renewed.json()["company"] == "Decathlon India"

    old = await client.get(f"/api/v1/advertising/contracts/{original_id}", headers=ctx["headers"])
    assert old.json()["status"] == "renewed"


async def test_expiring_soon_filter(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await setup_inventory(client, tenant_a)
    soon = date.today() - timedelta(days=150)
    await make_contract(client, ctx, start_date=soon.isoformat(), duration_months=6)
    await make_contract(
        client,
        ctx,
        spot_id=ctx["spot_2"],
        company="Wilson",
        start_date=date.today().isoformat(),
        duration_months=12,
    )

    expiring = await client.get(
        "/api/v1/advertising/contracts",
        params={"expiring_within_days": 45},
        headers=ctx["headers"],
    )
    assert expiring.json()["total"] == 1
    assert expiring.json()["items"][0]["company"] == "Decathlon India"


async def test_advertising_overview(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await setup_inventory(client, tenant_a)
    contract = await make_contract(
        client, ctx, start_date=date.today().isoformat(), duration_months=6
    )
    await client.post(
        f"/api/v1/advertising/contracts/{contract.json()['id']}/payments",
        json={"amount": "20000"},
        headers=ctx["headers"],
    )

    overview = await client.get("/api/v1/advertising/overview", headers=ctx["headers"])
    body = overview.json()
    assert body["total_spots"] == 2
    assert body["occupied_spots"] == 1
    assert body["available_spots"] == 1
    assert body["active_contracts"] == 1
    assert Decimal(body["collected"]) == Decimal("20000.00")
    assert Decimal(body["outstanding"]) == Decimal(body["contracted_value"]) - Decimal("20000.00")
    assert body["occupancy_pct"] == 50.0
