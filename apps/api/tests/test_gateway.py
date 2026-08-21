"""The externalisation gateway: partner isolation, idempotency, double-booking.

The property that matters most here is negative — what a partner CANNOT see. Most
of these tests assert a 404 or a 403, because the failure mode is silent: a gateway
that leaks another platform's bookings works perfectly from the partner's side.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient

from tests.conftest import TenantFixture
from tests.test_booking import at, book, setup_academy

IST = ZoneInfo("Asia/Kolkata")


async def make_partner(
    client: AsyncClient, ctx: dict, tenant: TenantFixture, name: str, slug: str
) -> dict:
    """Mint an integration and return `{headers, id, api_key, slug}`.

    The partner headers carry the tenant and the API key but NO Authorization:
    a partner is not a staff member, and the gateway must authenticate it on the
    key alone.
    """
    response = await client.post(
        "/api/v1/partners", json={"name": name, "slug": slug}, headers=ctx["headers"]
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "id": body["id"],
        "slug": slug,
        "api_key": body["api_key"],
        "headers": {"X-API-Key": body["api_key"], **tenant.headers},
    }


async def partner_book(client: AsyncClient, partner: dict, *, court: str, starts_at: str, **extra):
    return await client.post(
        "/api/v1/gateway/bookings",
        json={
            "court_id": court,
            "starts_at": starts_at,
            "duration_min": 60,
            "customer_name": "External Customer",
            "customer_phone": "9876500000",
            **extra,
        },
        headers=partner["headers"],
    )


# ── Key management ──────────────────────────────────────────────────────────


async def test_the_api_key_is_returned_once_and_never_again(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Only a hash is stored, so a lost key needs a rotation, not a lookup."""
    ctx = await setup_academy(client, tenant_a)
    partner = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    assert partner["api_key"]

    listed = await client.get("/api/v1/partners", headers=ctx["headers"])
    assert listed.status_code == 200, listed.text
    row = next(p for p in listed.json() if p["slug"] == "playo")
    assert "api_key" not in row
    # The prefix is public — it is how a key is looked up and how staff identify one.
    assert row["key_prefix"]


async def test_a_revoked_key_stops_working(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await setup_academy(client, tenant_a)
    partner = await make_partner(client, ctx, tenant_a, "Playo", "playo")

    revoke = await client.patch(
        f"/api/v1/partners/{partner['id']}", json={"is_active": False}, headers=ctx["headers"]
    )
    assert revoke.status_code == 200, revoke.text

    response = await client.get(
        "/api/v1/gateway/availability",
        params={"date": at(9, 10)},
        headers=partner["headers"],
    )
    assert response.status_code == 401


async def test_a_forged_secret_is_rejected(client: AsyncClient, tenant_a: TenantFixture) -> None:
    """A valid prefix with the wrong secret must fail — the prefix is not the secret."""
    ctx = await setup_academy(client, tenant_a)
    partner = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    prefix = partner["api_key"].split(".")[0]

    response = await client.get(
        "/api/v1/gateway/availability",
        params={"date": at(9, 10)},
        headers={**partner["headers"], "X-API-Key": f"{prefix}.wrong-secret"},
    )
    assert response.status_code == 401


# ── Availability ────────────────────────────────────────────────────────────


async def test_availability_reflects_bookings_from_every_source(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The gateway's whole purpose: a walk-in must close the slot for Playo too.

    If this fails, the integration double-books courts.
    """
    ctx = await setup_academy(client, tenant_a)
    partner = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    slot = at(10, 19)

    before = await client.get(
        "/api/v1/gateway/availability",
        params={"date": at(10, 0), "court_id": ctx["court_1"]},
        headers=partner["headers"],
    )
    assert before.status_code == 200, before.text
    assert any(
        s["available"] for s in before.json()[0]["slots"] if s["starts_at"].startswith(slot[:13])
    )

    # Booked at the counter, by staff — nothing to do with any platform.
    walkin = await book(client, ctx, court=ctx["court_1"], starts_at=slot, minutes=60)
    assert walkin.status_code == 201, walkin.text

    after = await client.get(
        "/api/v1/gateway/availability",
        params={"date": at(10, 0), "court_id": ctx["court_1"]},
        headers=partner["headers"],
    )
    taken = [s for s in after.json()[0]["slots"] if s["starts_at"].startswith(slot[:13])]
    assert taken and not any(s["available"] for s in taken)


async def test_availability_does_not_leak_internal_booking_ids(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """`blocked_by_booking_id` is right for our dashboard and wrong for a partner.

    Handing it out would let a platform enumerate our bookings by polling a day at
    a time — including walk-ins that are none of its business.
    """
    ctx = await setup_academy(client, tenant_a)
    partner = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    booked = await book(client, ctx, court=ctx["court_1"], starts_at=at(11, 19), minutes=60)
    assert booked.status_code == 201

    response = await client.get(
        "/api/v1/gateway/availability",
        params={"date": at(11, 0), "court_id": ctx["court_1"]},
        headers=partner["headers"],
    )
    assert response.status_code == 200, response.text
    for slot in response.json()[0]["slots"]:
        assert "blocked_by_booking_id" not in slot


# ── Double booking ──────────────────────────────────────────────────────────


async def test_two_platforms_cannot_take_the_same_slot(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    hudle = await make_partner(client, ctx, tenant_a, "Hudle", "hudle")
    slot = at(12, 19)

    first = await partner_book(client, playo, court=ctx["court_1"], starts_at=slot)
    assert first.status_code == 201, first.text

    second = await partner_book(client, hudle, court=ctx["court_1"], starts_at=slot)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_a_conflict_does_not_reveal_the_blocking_booking(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """`ensure_slot_free` names the conflicting booking; the gateway must strip it.

    Otherwise one platform learns another's booking ids by probing slots.
    """
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    hudle = await make_partner(client, ctx, tenant_a, "Hudle", "hudle")
    slot = at(13, 19)

    assert (await partner_book(client, playo, court=ctx["court_1"], starts_at=slot)).status_code == 201
    clash = await partner_book(client, hudle, court=ctx["court_1"], starts_at=slot)

    assert clash.status_code == 409
    assert "conflicting_booking_id" not in clash.json()["error"]["details"]


async def test_a_walk_in_blocks_a_platform_from_the_same_slot(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    slot = at(14, 19)

    assert (await book(client, ctx, court=ctx["court_1"], starts_at=slot, minutes=60)).status_code == 201
    blocked = await partner_book(client, playo, court=ctx["court_1"], starts_at=slot)
    assert blocked.status_code == 409


# ── Isolation ───────────────────────────────────────────────────────────────


async def test_a_partner_cannot_read_another_platforms_booking(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """404, not 403: a 403 confirms the id exists and turns this into an oracle."""
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    hudle = await make_partner(client, ctx, tenant_a, "Hudle", "hudle")

    made = await partner_book(client, playo, court=ctx["court_1"], starts_at=at(15, 19))
    assert made.status_code == 201, made.text
    booking_id = made.json()["id"]

    seen = await client.get(f"/api/v1/gateway/bookings/{booking_id}", headers=hudle["headers"])
    assert seen.status_code == 404


async def test_a_partner_cannot_cancel_another_platforms_booking(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    hudle = await make_partner(client, ctx, tenant_a, "Hudle", "hudle")

    made = await partner_book(client, playo, court=ctx["court_1"], starts_at=at(16, 19))
    assert made.status_code == 201
    booking_id = made.json()["id"]

    killed = await client.post(
        f"/api/v1/gateway/bookings/{booking_id}/cancel", json={}, headers=hudle["headers"]
    )
    assert killed.status_code == 404

    # And it really is still live, not merely hidden.
    still = await client.get(f"/api/v1/gateway/bookings/{booking_id}", headers=playo["headers"])
    assert still.json()["status"] != "cancelled"


async def test_a_partner_cannot_see_a_counter_booking(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")

    walkin = await book(client, ctx, court=ctx["court_1"], starts_at=at(17, 19), minutes=60)
    assert walkin.status_code == 201

    seen = await client.get(
        f"/api/v1/gateway/bookings/{walkin.json()['id']}", headers=playo["headers"]
    )
    assert seen.status_code == 404


async def test_the_booking_list_is_scoped_to_the_calling_partner(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    hudle = await make_partner(client, ctx, tenant_a, "Hudle", "hudle")

    assert (await partner_book(client, playo, court=ctx["court_1"], starts_at=at(18, 19))).status_code == 201
    assert (await partner_book(client, hudle, court=ctx["court_2"], starts_at=at(18, 19))).status_code == 201
    assert (await book(client, ctx, court=ctx["court_1"], starts_at=at(18, 8), minutes=60)).status_code == 201

    for partner in (playo, hudle):
        listed = await client.get("/api/v1/gateway/bookings", headers=partner["headers"])
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        assert rows, "partner should see its own booking"
        assert {row["source_platform"] for row in rows} == {partner["slug"]}


# ── Idempotency and provenance ──────────────────────────────────────────────


async def test_repeating_a_create_with_the_same_ref_returns_the_same_booking(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """A timeout on the partner's side must be safe to retry, not sell the court twice."""
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    slot = at(19, 19)

    first = await partner_book(client, playo, court=ctx["court_1"], starts_at=slot, external_ref="REF-1")
    assert first.status_code == 201, first.text

    retry = await partner_book(client, playo, court=ctx["court_1"], starts_at=slot, external_ref="REF-1")
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]

    listed = await client.get("/api/v1/gateway/bookings", headers=playo["headers"])
    assert len(listed.json()) == 1


async def test_the_platform_is_recorded_and_visible_to_staff(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """"Where did this booking come from?" answered without a join."""
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")

    made = await partner_book(
        client, playo, court=ctx["court_1"], starts_at=at(20, 19), external_ref="PLAYO-77"
    )
    assert made.status_code == 201, made.text
    assert made.json()["source_platform"] == "playo"

    internal = await client.get(f"/api/v1/bookings/{made.json()['id']}", headers=ctx["headers"])
    assert internal.status_code == 200, internal.text
    assert internal.json()["source_platform"] == "playo"
    assert internal.json()["external_ref"] == "PLAYO-77"


async def test_source_platform_is_taken_from_the_key_not_the_request(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """A platform must not be able to file a booking under a competitor's name."""
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    await make_partner(client, ctx, tenant_a, "Hudle", "hudle")

    made = await partner_book(
        client,
        playo,
        court=ctx["court_1"],
        starts_at=at(21, 19),
        # Ignored: not a field on PartnerBookingCreate at all.
        source_platform="hudle",
    )
    assert made.status_code == 201, made.text
    assert made.json()["source_platform"] == "playo"


async def test_a_partner_booking_is_not_auto_checked_in(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Nobody is at the counter. Arriving stays a separate event the desk confirms."""
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")

    starts = (datetime.now(UTC) + timedelta(minutes=2)).replace(microsecond=0).isoformat()
    made = await partner_book(client, playo, court=ctx["court_1"], starts_at=starts)
    assert made.status_code == 201, made.text
    assert made.json()["status"] == "upcoming"


# ── Cancellation ────────────────────────────────────────────────────────────


async def test_cancelling_frees_the_slot_for_everyone(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    hudle = await make_partner(client, ctx, tenant_a, "Hudle", "hudle")
    slot = at(22, 19)

    made = await partner_book(client, playo, court=ctx["court_1"], starts_at=slot)
    assert made.status_code == 201

    blocked = await partner_book(client, hudle, court=ctx["court_1"], starts_at=slot)
    assert blocked.status_code == 409

    released = await client.post(
        f"/api/v1/gateway/bookings/{made.json()['id']}/cancel",
        json={"reason": "customer cancelled"},
        headers=playo["headers"],
    )
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "cancelled"

    # The exclusion constraint's `WHERE status <> 'cancelled'` is what makes this work.
    retry = await partner_book(client, hudle, court=ctx["court_1"], starts_at=slot)
    assert retry.status_code == 201, retry.text


async def test_cancelling_twice_is_not_an_error(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    made = await partner_book(client, playo, court=ctx["court_1"], starts_at=at(23, 19))
    assert made.status_code == 201

    for _ in range(2):
        again = await client.post(
            f"/api/v1/gateway/bookings/{made.json()['id']}/cancel",
            json={},
            headers=playo["headers"],
        )
        assert again.status_code == 200, again.text
        assert again.json()["status"] == "cancelled"


async def test_an_integration_with_bookings_cannot_be_deleted(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """A booking must keep answering "where did this come from?" — revoke, don't delete."""
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    assert (await partner_book(client, playo, court=ctx["court_1"], starts_at=at(24, 19))).status_code == 201

    refused = await client.delete(f"/api/v1/partners/{playo['id']}", headers=ctx["headers"])
    assert refused.status_code == 409


async def test_checkin_lookup_matches_a_partners_external_ref(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The counter's check-in screen has to accept Playo's own booking reference,
    not just an id we minted — that reference is what the customer actually holds."""
    ctx = await setup_academy(client, tenant_a)
    playo = await make_partner(client, ctx, tenant_a, "Playo", "playo")
    starts = (datetime.now(UTC) + timedelta(minutes=5)).replace(microsecond=0).isoformat()
    made = await partner_book(
        client, playo, court=ctx["court_1"], starts_at=starts, external_ref="PLYO-998877"
    )
    assert made.status_code == 201, made.text

    found = await client.get(
        "/api/v1/bookings/checkin-lookup",
        params={"code": "plyo-998877"},
        headers=ctx["headers"],
    )
    assert found.status_code == 200, found.text
    assert found.json()["id"] == made.json()["id"]
