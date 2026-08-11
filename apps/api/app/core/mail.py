"""Sending email, and recording that it was sent.

Two responsibilities, deliberately together: a message that goes out without a
`notification_delivery` row is invisible to the usage screen and to the bill, and
one that is recorded without going out is worse. `send_email` does both or neither.

Transport only — what the messages *say* lives in `app/core/mail_templates.py`,
and *when* they are sent in `app/jobs/worker.py`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

import aiosmtplib
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.admin.models import Channel, DeliveryState, NotificationDelivery

logger = logging.getLogger("gamexo.mail")


class MailNotConfigured(RuntimeError):
    """Neither transport is set up. Raised rather than silently swallowed so a queued
    job retries once configuration arrives instead of being marked done."""


class MailSendFailed(RuntimeError):
    """The provider accepted the request and refused the message — a bad sender
    domain, an unverified account, a rejected recipient. Distinct from a network
    error because the same payload will keep failing until something is fixed."""


@dataclass(frozen=True, slots=True)
class Message:
    to: str
    subject: str
    text: str
    html: str | None = None


def is_configured() -> bool:
    return settings.mail_provider != "none"


def _sender(from_email: str | None, from_name: str | None) -> tuple[str, str, str | None]:
    """Who the message comes from, and where replies should go.

    Returns (from_email, from_name, reply_to).

    With MAIL_FORCE_FROM the academy's address moves to Reply-To and the deployment's
    verified address becomes the sender. That is not a downgrade: providers reject
    unverified sender domains outright, so this is the difference between an academy
    being able to send and not. The recipient still sees the academy's name, and
    hitting reply still reaches the academy.
    """
    fallback = settings.mail_from_email or settings.smtp_username or ""
    name = from_name or settings.mail_from_name

    if settings.mail_force_from and fallback:
        reply_to = from_email if from_email and from_email != fallback else None
        return fallback, name, reply_to

    return (from_email or fallback), name, None


def build_message(msg: Message, *, from_email: str | None, from_name: str | None) -> EmailMessage:
    email_addr, name, reply_to = _sender(from_email, from_name)

    out = EmailMessage()
    out["From"] = formataddr((name, email_addr))
    out["To"] = msg.to
    out["Subject"] = msg.subject
    if reply_to:
        out["Reply-To"] = reply_to
    # Plain text first, HTML as the alternative: a client that cannot render HTML
    # shows the text part rather than an empty message or a wall of markup.
    out.set_content(msg.text)
    if msg.html:
        out.add_alternative(msg.html, subtype="html")
    return out


async def send_email(
    session: AsyncSession,
    msg: Message,
    *,
    event_key: str,
    from_email: str | None = None,
    from_name: str | None = None,
) -> NotificationDelivery:
    """Send one message and record the attempt.

    The delivery row is written whatever happens — sent, or failed with the reason —
    because "we tried and the address bounced" and "we never tried" are different
    problems and only one of them is the customer's.

    Cost stays 0: email has no per-message charge the way WhatsApp and SMS do. The
    column exists so the same table can meter those later.
    """
    recipient = settings.mail_redirect_all_to or msg.to

    delivery = NotificationDelivery(
        event_key=event_key,
        channel=Channel.EMAIL,
        recipient=recipient,
        state=DeliveryState.QUEUED,
    )
    session.add(delivery)
    # Sessions here run with autoflush off, so every state change below is flushed
    # by hand. Without it a failure path raises with the row still sitting in the
    # identity map, and the evidence of the attempt never reaches the table.
    await session.flush()

    if not is_configured():
        delivery.state = DeliveryState.FAILED
        delivery.error = "Email is not configured — set RESEND_API_KEY or SMTP_HOST."
        await session.flush()
        raise MailNotConfigured(delivery.error)

    outbound = Message(to=recipient, subject=msg.subject, text=msg.text, html=msg.html)

    try:
        if settings.mail_provider == "resend":
            reference = await _send_via_resend(outbound, from_email, from_name)
        else:
            reference = await _send_via_smtp(outbound, from_email, from_name)
    except Exception as exc:  # noqa: BLE001 — every failure mode is worth recording
        delivery.state = DeliveryState.FAILED
        delivery.error = f"{type(exc).__name__}: {exc}"[:2000]
        await session.flush()
        logger.warning("email failed to %s (%s): %s", recipient, event_key, exc)
        raise

    delivery.state = DeliveryState.SENT
    delivery.sent_at = datetime.now(UTC)
    delivery.provider_message_id = reference[:128] or None
    await session.flush()
    logger.info("email sent to %s (%s) via %s", recipient, event_key, settings.mail_provider)
    return delivery


async def _send_via_resend(msg: Message, from_email: str | None, from_name: str | None) -> str:
    """Resend's HTTP API. Returns their message id.

    That id is the point of preferring this over SMTP: it is searchable in Resend's
    dashboard, so "did the customer get it?" has an answer beyond our own log line.
    """
    email_addr, name, reply_to = _sender(from_email, from_name)
    body: dict[str, Any] = {
        "from": formataddr((name, email_addr)),
        "to": [msg.to],
        "subject": msg.subject,
        "text": msg.text,
    }
    if msg.html:
        body["html"] = msg.html
    if reply_to:
        body["reply_to"] = reply_to

    async with httpx.AsyncClient(timeout=settings.mail_timeout_seconds) as client:
        response = await client.post(
            settings.resend_api_url,
            json=body,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

    if response.status_code >= 400:
        # Resend answers with structured JSON — surface its message rather than a
        # bare status code, because it names the actual problem ("The gamexo.app
        # domain is not verified", "You can only send to your own email address").
        try:
            detail = response.json()
            reason = detail.get("message") or detail.get("name") or response.text
        except ValueError:
            reason = response.text
        raise MailSendFailed(f"Resend refused the message ({response.status_code}): {reason}")

    return str(response.json().get("id", ""))


async def _send_via_smtp(msg: Message, from_email: str | None, from_name: str | None) -> str:
    """The fallback transport. Returns whatever queue id the server volunteered.

    SMTP has no message id of its own; most servers put one in the final 250
    response, which is the only handle support has when chasing a message.
    """
    payload = build_message(msg, from_email=from_email, from_name=from_name)
    _, response = await aiosmtplib.send(
        payload,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=(settings.smtp_password.get_secret_value() if settings.smtp_password else None),
        use_tls=settings.smtp_use_tls,
        start_tls=settings.smtp_starttls or None,
        timeout=settings.mail_timeout_seconds,
    )
    return response or ""
