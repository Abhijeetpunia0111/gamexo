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

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.admin.models import Channel, DeliveryState, NotificationDelivery

logger = logging.getLogger("gamexo.mail")


class MailNotConfigured(RuntimeError):
    """No SMTP host is set. Raised rather than silently swallowed so a queued job
    retries once configuration arrives instead of being marked done."""


@dataclass(frozen=True, slots=True)
class Message:
    to: str
    subject: str
    text: str
    html: str | None = None


def is_configured() -> bool:
    return bool(settings.smtp_host)


def _sender(from_email: str | None, from_name: str | None) -> tuple[str, str]:
    """The address mail goes out as.

    A tenant's own sender wins, falling back to the deployment default. Both may be
    overridden by the provider anyway — see the note in config.py about Gmail.
    """
    email = from_email or settings.smtp_from_email or settings.smtp_username or ""
    return email, from_name or settings.smtp_from_name


def build_message(msg: Message, *, from_email: str | None, from_name: str | None) -> EmailMessage:
    email_addr, name = _sender(from_email, from_name)

    out = EmailMessage()
    out["From"] = formataddr((name, email_addr))
    out["To"] = msg.to
    out["Subject"] = msg.subject
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

    Cost stays 0: SMTP email has no per-message charge the way WhatsApp and SMS do.
    The column exists so the same table can meter those later.
    """
    recipient = settings.smtp_redirect_all_to or msg.to

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
        delivery.error = "SMTP is not configured (SMTP_HOST is unset)."
        await session.flush()
        raise MailNotConfigured(delivery.error)

    payload = build_message(
        Message(to=recipient, subject=msg.subject, text=msg.text, html=msg.html),
        from_email=from_email,
        from_name=from_name,
    )

    try:
        _, response = await aiosmtplib.send(
            payload,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=(
                settings.smtp_password.get_secret_value() if settings.smtp_password else None
            ),
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_starttls or None,
            timeout=settings.smtp_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 — every failure mode is worth recording
        delivery.state = DeliveryState.FAILED
        delivery.error = f"{type(exc).__name__}: {exc}"[:2000]
        await session.flush()
        logger.warning("email failed to %s (%s): %s", recipient, event_key, exc)
        raise

    delivery.state = DeliveryState.SENT
    delivery.sent_at = datetime.now(UTC)
    # SMTP has no message id of its own; most servers put a queue id in the final
    # 250 response, which is the only handle support has when chasing a message.
    delivery.provider_message_id = (response or "")[:128] or None
    await session.flush()
    logger.info("email sent to %s (%s)", recipient, event_key)
    return delivery
