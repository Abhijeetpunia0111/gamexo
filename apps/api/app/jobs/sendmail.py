"""Prove the mail credentials work, before a real booking depends on them.

    python -m app.jobs.sendmail you@example.com
    python -m app.jobs.sendmail you@example.com --tenant xcourt --template booking

Deliberately separate from the worker: when mail is not arriving, the first
question is whether the credentials and the network work at all, and answering it
should not require queueing a job and waiting for a sweep.

Nothing is committed — the delivery row this writes is rolled back, so a test send
does not appear in the usage figures as real traffic.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.mail import Message, is_configured, send_email
from app.core.mail_templates import payment_receipt
from app.db.session import dispose_engine, tenant_session, untenanted_session
from app.models.tenant import Tenant, TenantSettings


async def _resolve_tenant(slug: str | None) -> tuple[str, str]:
    async with untenanted_session() as session:
        stmt = select(Tenant)
        if slug:
            stmt = stmt.where(Tenant.slug == slug)
        tenant = (await session.execute(stmt.limit(1))).scalars().first()
        if tenant is None:
            raise SystemExit(f"No tenant found{f' with slug {slug!r}' if slug else ''}.")
        return str(tenant.id), tenant.slug


async def run(to: str, slug: str | None, template: str) -> int:
    if not is_configured():
        print("Email is not configured — set RESEND_API_KEY (or SMTP_HOST) in apps/api/.env.")
        return 2

    tenant_id, tenant_slug = await _resolve_tenant(slug)
    print(f"tenant   : {tenant_slug}")
    print(f"provider : {settings.mail_provider}")
    if settings.mail_provider == "resend":
        print(f"endpoint : {settings.resend_api_url}")
    else:
        print(f"host     : {settings.smtp_host}:{settings.smtp_port}")
        print(f"username : {settings.smtp_username}")
        print(f"starttls : {settings.smtp_starttls}   tls: {settings.smtp_use_tls}")
    print(f"from     : {settings.mail_from_name} <{settings.mail_from_email}>")
    if settings.mail_redirect_all_to:
        print(f"redirect : all mail -> {settings.mail_redirect_all_to}")
    print(f"to       : {to}")

    import uuid as _uuid

    async with tenant_session(_uuid.UUID(tenant_id)) as session:
        tenant_settings = (await session.execute(select(TenantSettings))).scalar_one()

        if template == "payment":
            subject, text, html = payment_receipt(
                tenant_settings,
                customer_name="Test Customer",
                amount=Decimal("944.00"),
                method="cash",
                reference="TEST-0001",
                balance_remaining=Decimal("0"),
            )
        else:
            when = datetime.now(UTC) + timedelta(hours=2)
            subject = f"{tenant_settings.business_name} — mail test"
            text = (
                "This is a test message from gamexo.\n\n"
                f"Sent at {when:%d %b %Y %H:%M} UTC.\n"
                "If you are reading this, the mail credentials work."
            )
            html = f"<p>This is a test message from <b>{tenant_settings.business_name}</b>.</p>"

        try:
            await send_email(
                session,
                Message(to=to, subject=subject, text=text, html=html),
                event_key="mail_test",
                from_email=tenant_settings.notification_sender_email,
                from_name=tenant_settings.notification_sender_name
                or tenant_settings.business_name,
            )
        except Exception as exc:  # noqa: BLE001 — this command exists to report it
            print(f"\nFAILED: {type(exc).__name__}: {exc}")
            _hint(exc)
            return 1

        print("\nSent. Check the inbox (and the spam folder).")
        # Roll back so the test delivery is not counted as real usage.
        await session.rollback()
    return 0


def _hint(exc: Exception) -> None:
    text = str(exc).lower()
    if "not verified" in text or "domain is not verified" in text:
        print(
            "\nResend will not send from a domain you have not verified with them.\n"
            "Either verify the domain (Resend → Domains, then add the DNS records),\n"
            "or set MAIL_FROM_EMAIL=onboarding@resend.dev — which only delivers to\n"
            "the address that owns the Resend account."
        )
    elif "you can only send testing emails" in text or "own email address" in text:
        print(
            "\nResend is in its unverified state: until a domain is verified it will\n"
            "only deliver to the address that owns the account. Verify a domain, or\n"
            "test against your own address."
        )
    elif "401" in text or "unauthorized" in text or "invalid api key" in text:
        print("\nResend rejected the API key. Check RESEND_API_KEY — it starts with `re_`.")
    elif "username and password not accepted" in text or "5.7.8" in text:
        print(
            "\nGmail rejected the credentials. It needs a 16-character app password,\n"
            "not the account password — and app passwords only exist once 2-Step\n"
            "Verification is enabled on the account."
        )
    elif "timed out" in text or isinstance(exc, TimeoutError):
        print(
            "\nTimed out. On SMTP, port 587 wants SMTP_STARTTLS=true and\n"
            "SMTP_USE_TLS=false; port 465 wants the opposite. Outbound SMTP is also\n"
            "blocked on many networks and hosting providers — which is a good reason\n"
            "to use Resend's HTTP API instead."
        )
    elif "certificate" in text:
        print("\nTLS negotiation failed — check the port matches the TLS mode above.")


async def _run_and_dispose(to: str, slug: str | None, template: str) -> int:
    """Send, then dispose the engine on the *same* loop that opened it.

    Two `asyncio.run` calls would be two loops: the pooled connections belong to
    the first, and closing them from the second raises "Event loop is closed" over
    a send that actually succeeded.
    """
    try:
        return await run(to, slug, template)
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one test email through the configured mail provider")
    parser.add_argument("to", help="Recipient address")
    parser.add_argument("--tenant", help="Tenant slug; defaults to the first one")
    parser.add_argument(
        "--template",
        choices=("plain", "payment"),
        default="plain",
        help="plain = a bare test message; payment = a real receipt template",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_run_and_dispose(args.to, args.tenant, args.template)))


if __name__ == "__main__":
    main()
