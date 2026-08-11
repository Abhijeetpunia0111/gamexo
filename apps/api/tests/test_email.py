"""Outbound email: queueing, rendering, sending and metering.

No SMTP server is involved. `aiosmtplib.send` is patched, because what matters here
is that the right message is built for the right recipient and that the attempt is
recorded — none of which needs a socket.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.core.mail import MailNotConfigured, MailSendFailed, Message, send_email
from app.db.session import tenant_session
from app.jobs import worker
from app.modules.admin.models import (
    Channel,
    DeliveryState,
    Job,
    JobState,
    NotificationChannelConfig,
    NotificationDelivery,
)
from tests.conftest import PASSWORD, TenantFixture, auth_headers, login

IST = ZoneInfo("Asia/Kolkata")


def at(day: int, hour: int) -> str:
    return datetime(2026, 10, day, hour, tzinfo=IST).isoformat()


@pytest.fixture
def smtp(monkeypatch):
    """A configured SMTP server that records instead of sending.

    `resend_api_key` is cleared explicitly: the provider is chosen by which
    credential is present, so a key left in the developer's .env would silently
    route these tests down the other transport.
    """
    sent: list = []

    async def fake_send(message, **kwargs):
        sent.append((message, kwargs))
        return {}, "250 2.0.0 OK queued as ABC123"

    monkeypatch.setattr(settings, "resend_api_key", None)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "counter@xcourtsports.com")
    monkeypatch.setattr(settings, "mail_from_email", "counter@xcourtsports.com")
    monkeypatch.setattr(settings, "mail_redirect_all_to", None)
    monkeypatch.setattr("app.core.mail.aiosmtplib.send", fake_send)
    return sent


@pytest.fixture
def resend(monkeypatch):
    """Resend's HTTP API, captured at the transport boundary."""
    calls: list = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "re_abc123"}

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            calls.append({"url": url, "json": json, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(settings, "resend_api_key", SecretStr("re_test_key"))
    monkeypatch.setattr(settings, "mail_from_email", "counter@xcourtsports.com")
    monkeypatch.setattr(settings, "mail_redirect_all_to", None)
    monkeypatch.setattr("app.core.mail.httpx.AsyncClient", FakeClient)
    return calls


async def _setup(client: AsyncClient, tenant: TenantFixture) -> dict:
    token = await login(client, tenant, tenant.admin_email, PASSWORD)
    h = auth_headers(token, tenant)

    sport = await client.post(
        "/api/v1/sports",
        json={"name": "Tennis", "price_base": "800", "price_peak": "1200", "price_weekend": "1000"},
        headers=h,
    )
    court = await client.post(
        "/api/v1/courts",
        json={
            "name": "Court 1",
            "code": "C1",
            "sport_id": sport.json()["id"],
            "hourly_rate": "800",
            "peak_rate": "1200",
            "operating_hours": {"open": "06:00", "close": "22:00"},
        },
        headers=h,
    )
    customer = await client.post(
        "/api/v1/customers",
        json={"name": "Arjun Mehta", "phone": "9876543210", "email": "arjun@xcourtsports.com"},
        headers=h,
    )
    assert customer.status_code == 201, customer.text
    return {"headers": h, "court": court.json()["id"], "customer": customer.json()["id"]}


# ── Queueing ────────────────────────────────────────────────────────────────


async def test_a_booking_queues_a_confirmation(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await _setup(client, tenant_a)

    response = await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(1, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text

    async with tenant_session(tenant_a.id) as session:
        jobs = (await session.execute(select(Job).where(Job.kind == "email.booking_confirmation"))).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].payload["recipient"] == "arjun@xcourtsports.com"
        assert jobs[0].payload["booking_id"] == response.json()["id"]


async def test_a_booking_without_an_email_queues_nothing(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Walk-ins are frequently anonymous. No address is not a failure."""
    ctx = await _setup(client, tenant_a)

    response = await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(2, 10),
            "duration_min": 60,
            "customer_name": "Cash Walk-in",
            "customer_phone": "9000000000",
        },
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text

    async with tenant_session(tenant_a.id) as session:
        jobs = (await session.execute(select(Job).where(Job.kind.like("email.%")))).scalars().all()
        assert jobs == []


async def test_turning_email_off_for_an_event_stops_the_queue(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The per-event channel matrix is honoured at queue time, not at send time —
    a message nobody wants should never become a job in the first place."""
    ctx = await _setup(client, tenant_a)

    off = await client.patch(
        "/api/v1/notification-channels/booking_confirmation",
        json={"email_enabled": False},
        headers=ctx["headers"],
    )
    assert off.status_code == 200, off.text

    await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(3, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )

    async with tenant_session(tenant_a.id) as session:
        jobs = (
            await session.execute(select(Job).where(Job.kind == "email.booking_confirmation"))
        ).scalars().all()
        assert jobs == []


async def test_a_payment_queues_a_receipt(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await _setup(client, tenant_a)
    booking = await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(4, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )
    total = booking.json()["total"]

    paid = await client.post(
        "/api/v1/payments",
        json={"booking_id": booking.json()["id"], "amount": total, "method": "cash"},
        headers=ctx["headers"],
    )
    assert paid.status_code == 201, paid.text

    async with tenant_session(tenant_a.id) as session:
        job = (
            await session.execute(select(Job).where(Job.kind == "email.payment_receipt"))
        ).scalars().one()
        assert job.payload["recipient"] == "arjun@xcourtsports.com"
        assert Decimal(job.payload["amount"]) == Decimal(total)
        assert Decimal(job.payload["balance_remaining"]) == Decimal("0")


# ── Sending ─────────────────────────────────────────────────────────────────


async def test_the_worker_sends_a_queued_confirmation(
    client: AsyncClient, tenant_a: TenantFixture, smtp
) -> None:
    ctx = await _setup(client, tenant_a)
    await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(5, 18),
            "duration_min": 120,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )

    async with tenant_session(tenant_a.id) as session:
        jobs = await worker.claim_batch(session)
        for job in jobs:
            await worker.run_job(session, job)

        assert len(smtp) == 1
        message, _ = smtp[0]
        assert message["To"] == "arjun@xcourtsports.com"
        assert "Court 1" in message["Subject"]

        # Recorded, so the usage screen and the bill can see it.
        delivery = (await session.execute(select(NotificationDelivery))).scalars().one()
        assert delivery.channel is Channel.EMAIL
        assert delivery.state is DeliveryState.SENT
        assert delivery.recipient == "arjun@xcourtsports.com"
        assert delivery.provider_message_id.startswith("250")


async def test_a_send_failure_is_recorded_and_retried(
    client: AsyncClient, tenant_a: TenantFixture, smtp, monkeypatch
) -> None:
    """A bounced send must leave evidence — and come back, not vanish."""
    ctx = await _setup(client, tenant_a)
    await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(6, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )

    async def explode(message, **kwargs):
        raise TimeoutError("connection timed out")

    monkeypatch.setattr("app.core.mail.aiosmtplib.send", explode)

    async with tenant_session(tenant_a.id) as session:
        jobs = await worker.claim_batch(session)
        for job in jobs:
            await worker.run_job(session, job)

        delivery = (await session.execute(select(NotificationDelivery))).scalars().one()
        assert delivery.state is DeliveryState.FAILED
        assert "TimeoutError" in delivery.error

        job = (await session.execute(select(Job).where(Job.kind.like("email.%")))).scalars().one()
        # Back to pending for another attempt, not silently done.
        assert job.state is JobState.PENDING
        assert job.attempts == 1


async def test_a_cancelled_booking_is_not_confirmed(
    client: AsyncClient, tenant_a: TenantFixture, smtp
) -> None:
    """Queued, then cancelled before the sweep. Sending it anyway is worse than
    sending nothing — the customer would arrive for a court they do not have."""
    ctx = await _setup(client, tenant_a)
    booking = await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(7, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/v1/bookings/{booking.json()['id']}/cancel",
        json={"reason": "changed their mind"},
        headers=ctx["headers"],
    )

    async with tenant_session(tenant_a.id) as session:
        jobs = await worker.claim_batch(session)
        for job in jobs:
            await worker.run_job(session, job)

    assert smtp == []


async def test_redirect_diverts_every_message(
    client: AsyncClient, tenant_a: TenantFixture, smtp, monkeypatch
) -> None:
    """The staging guard: real data, one inbox, and the delivery row says so."""
    monkeypatch.setattr(settings, "mail_redirect_all_to", "staging@xcourtsports.com")
    ctx = await _setup(client, tenant_a)
    await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(8, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )

    async with tenant_session(tenant_a.id) as session:
        for job in await worker.claim_batch(session):
            await worker.run_job(session, job)

        message, _ = smtp[0]
        assert message["To"] == "staging@xcourtsports.com"
        delivery = (await session.execute(select(NotificationDelivery))).scalars().one()
        assert delivery.recipient == "staging@xcourtsports.com"


async def test_unconfigured_smtp_raises_rather_than_pretending(
    tenant_a: TenantFixture, monkeypatch
) -> None:
    """With no host, a send must fail loudly so the job retries once mail is set up
    — not report success and drop the message."""
    monkeypatch.setattr(settings, "smtp_host", None)

    async with tenant_session(tenant_a.id) as session:
        with pytest.raises(MailNotConfigured):
            await send_email(
                session,
                Message(to="someone@xcourtsports.com", subject="hi", text="hi"),
                event_key="smtp_test",
            )
        delivery = (await session.execute(select(NotificationDelivery))).scalars().one()
        assert delivery.state is DeliveryState.FAILED


# ── Resend transport ────────────────────────────────────────────────────────


async def test_resend_is_used_when_an_api_key_is_present(
    client: AsyncClient, tenant_a: TenantFixture, resend
) -> None:
    """The provider is chosen by which credential exists, not by a mode flag."""
    assert settings.mail_provider == "resend"
    ctx = await _setup(client, tenant_a)
    await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(20, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )

    async with tenant_session(tenant_a.id) as session:
        for job in await worker.claim_batch(session):
            await worker.run_job(session, job)

        call = resend[0]
        assert call["headers"]["Authorization"] == "Bearer re_test_key"
        assert call["json"]["to"] == ["arjun@xcourtsports.com"]
        # Both parts, so a client that cannot render HTML still shows something.
        assert call["json"]["text"]
        assert call["json"]["html"]

        # Resend's own id, not an SMTP response — this is the point of using it.
        delivery = (await session.execute(select(NotificationDelivery))).scalars().one()
        assert delivery.state is DeliveryState.SENT
        assert delivery.provider_message_id == "re_abc123"


async def test_resend_sends_from_the_tenants_own_identity(
    client: AsyncClient, tenant_a: TenantFixture, resend
) -> None:
    ctx = await _setup(client, tenant_a)
    await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(21, 10),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )

    async with tenant_session(tenant_a.id) as session:
        for job in await worker.claim_batch(session):
            await worker.run_job(session, job)

    # "Business Name <address>", so the recipient sees the academy, not "gamexo".
    assert "<" in resend[0]["json"]["from"]


async def test_forcing_the_sender_keeps_the_academy_reachable(
    client: AsyncClient, tenant_a: TenantFixture, resend, monkeypatch
) -> None:
    """Providers reject unverified sender domains, so the deployment's verified
    address sends and the academy's own moves to Reply-To. The recipient still sees
    the academy, and replying still reaches it."""
    monkeypatch.setattr(settings, "mail_force_from", True)

    async with tenant_session(tenant_a.id) as session:
        await send_email(
            session,
            Message(to="player@xcourtsports.com", subject="hi", text="hi"),
            event_key="mail_test",
            from_email="info@some-unverified-academy.com",
            from_name="Some Academy",
        )

    body = resend[0]["json"]
    assert body["from"] == "Some Academy <counter@xcourtsports.com>"
    assert body["reply_to"] == "info@some-unverified-academy.com"


async def test_without_forcing_the_academys_own_address_sends(
    client: AsyncClient, tenant_a: TenantFixture, resend, monkeypatch
) -> None:
    """Once a domain is verified, the academy sends as itself and needs no Reply-To."""
    monkeypatch.setattr(settings, "mail_force_from", False)

    async with tenant_session(tenant_a.id) as session:
        await send_email(
            session,
            Message(to="player@xcourtsports.com", subject="hi", text="hi"),
            event_key="mail_test",
            from_email="info@verified-academy.com",
            from_name="Verified Academy",
        )

    body = resend[0]["json"]
    assert body["from"] == "Verified Academy <info@verified-academy.com>"
    assert "reply_to" not in body


async def test_a_resend_rejection_surfaces_its_reason(
    client: AsyncClient, tenant_a: TenantFixture, resend, monkeypatch
) -> None:
    """Resend answers 4xx with JSON naming the real problem. Losing that behind a
    status code is how "emails stopped working" becomes an afternoon."""

    class Refused:
        status_code = 403

        @staticmethod
        def json():
            return {"message": "The gamexo.app domain is not verified."}

    class RefusingClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            return Refused()

    monkeypatch.setattr("app.core.mail.httpx.AsyncClient", RefusingClient)

    async with tenant_session(tenant_a.id) as session:
        with pytest.raises(MailSendFailed, match="not verified"):
            await send_email(
                session,
                Message(to="someone@xcourtsports.com", subject="hi", text="hi"),
                event_key="mail_test",
            )
        delivery = (await session.execute(select(NotificationDelivery))).scalars().one()
        assert delivery.state is DeliveryState.FAILED
        assert "not verified" in delivery.error


async def test_redirect_applies_to_resend_too(
    client: AsyncClient, tenant_a: TenantFixture, resend, monkeypatch
) -> None:
    """The staging guard must not be an SMTP-only feature."""
    monkeypatch.setattr(settings, "mail_redirect_all_to", "staging@xcourtsports.com")

    async with tenant_session(tenant_a.id) as session:
        await send_email(
            session,
            Message(to="real.customer@xcourtsports.com", subject="hi", text="hi"),
            event_key="mail_test",
        )

    assert resend[0]["json"]["to"] == ["staging@xcourtsports.com"]


# ── "Email invoice" button ──────────────────────────────────────────────────


async def _booking(client: AsyncClient, ctx: dict, day: int, *, customer: bool = True) -> str:
    body = {"court_id": ctx["court"], "starts_at": at(day, 10), "duration_min": 60}
    if customer:
        body["customer_id"] = ctx["customer"]
    else:
        body |= {"customer_name": "Cash Walk-in", "customer_phone": "9000000000"}
    response = await client.post("/api/v1/bookings", json=body, headers=ctx["headers"])
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_emailing_an_invoice_sends_it_there_and_then(
    client: AsyncClient, tenant_a: TenantFixture, smtp
) -> None:
    """The button is a send, not a queue — staff tell the customer it has gone."""
    ctx = await _setup(client, tenant_a)
    booking_id = await _booking(client, ctx, 11)

    response = await client.post(
        f"/api/v1/bookings/{booking_id}/invoice/email", json={}, headers=ctx["headers"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["sent_to"] == "arjun@xcourtsports.com"
    assert response.json()["invoice_no"]

    message, _ = smtp[0]
    assert message["To"] == "arjun@xcourtsports.com"
    assert response.json()["invoice_no"] in message["Subject"]


async def test_an_explicit_address_overrides_the_one_on_file(
    client: AsyncClient, tenant_a: TenantFixture, smtp
) -> None:
    """Counter staff take an address verbally; the record is often stale or empty."""
    ctx = await _setup(client, tenant_a)
    booking_id = await _booking(client, ctx, 12)

    response = await client.post(
        f"/api/v1/bookings/{booking_id}/invoice/email",
        json={"to": "someone.else@xcourtsports.com"},
        headers=ctx["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["sent_to"] == "someone.else@xcourtsports.com"


async def test_no_address_anywhere_asks_rather_than_failing(
    client: AsyncClient, tenant_a: TenantFixture, smtp
) -> None:
    """409 is what the POS turns into "where should this go?" — not an error state."""
    ctx = await _setup(client, tenant_a)
    booking_id = await _booking(client, ctx, 13, customer=False)

    response = await client.post(
        f"/api/v1/bookings/{booking_id}/invoice/email", json={}, headers=ctx["headers"]
    )
    assert response.status_code == 409, response.text
    assert "No email address on file" in response.json()["error"]["message"]
    assert smtp == []


async def test_pressing_it_twice_does_not_issue_a_second_invoice(
    client: AsyncClient, tenant_a: TenantFixture, smtp
) -> None:
    """Two copies of one invoice is fine. Two invoice numbers for one booking is not."""
    ctx = await _setup(client, tenant_a)
    booking_id = await _booking(client, ctx, 14)

    first = await client.post(
        f"/api/v1/bookings/{booking_id}/invoice/email", json={}, headers=ctx["headers"]
    )
    second = await client.post(
        f"/api/v1/bookings/{booking_id}/invoice/email", json={}, headers=ctx["headers"]
    )
    assert first.json()["invoice_no"] == second.json()["invoice_no"]
    assert len(smtp) == 2


async def test_a_refused_send_reports_502_rather_than_claiming_success(
    client: AsyncClient, tenant_a: TenantFixture, smtp, monkeypatch
) -> None:
    ctx = await _setup(client, tenant_a)
    booking_id = await _booking(client, ctx, 15)

    async def refuse(message, **kwargs):
        raise ConnectionRefusedError("mailbox unavailable")

    monkeypatch.setattr("app.core.mail.aiosmtplib.send", refuse)

    response = await client.post(
        f"/api/v1/bookings/{booking_id}/invoice/email", json={}, headers=ctx["headers"]
    )
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "mail_delivery_failed"


# ── Rendering ───────────────────────────────────────────────────────────────


async def test_the_confirmation_shows_the_venue_local_time(
    client: AsyncClient, tenant_a: TenantFixture, smtp
) -> None:
    """Stored as an instant, read in the academy's zone. A 6 PM IST booking that
    says 12:30 is the most confusing thing a confirmation can do."""
    ctx = await _setup(client, tenant_a)
    await client.post(
        "/api/v1/bookings",
        json={
            "court_id": ctx["court"],
            "starts_at": at(9, 18),
            "duration_min": 60,
            "customer_id": ctx["customer"],
        },
        headers=ctx["headers"],
    )

    async with tenant_session(tenant_a.id) as session:
        for job in await worker.claim_batch(session):
            await worker.run_job(session, job)

    message, _ = smtp[0]
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "6:00 PM" in body
    assert "12:30" not in body
