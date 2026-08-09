"""Queueing outbound notifications.

Requests never send email. They enqueue a `job` row in the same transaction as the
thing that caused it, and the worker sends. That ordering matters:

  * A booking must not fail because Gmail is slow, down, or rate-limiting. Taking
    payment at a counter while a customer waits is not the moment to discover an
    SMTP timeout.
  * Enqueueing in the same transaction means an email is queued if and only if the
    booking was actually committed — no confirmations for bookings that rolled back,
    and none lost for bookings that succeeded.
  * The job table already retries with backoff and shows failures in `/jobs`, so a
    transient send failure resolves itself.

The trade-off, stated plainly: mail goes out on the worker's schedule, not
instantly. Run the worker every minute if a confirmation arriving within seconds
matters — see `app/jobs/worker.py`.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Job, NotificationChannelConfig

#: Job kinds, one per template. Prefixed so `/jobs` reads clearly next to the
#: sweep jobs, and so a future SMS channel can sit alongside as `sms.*`.
EMAIL_BOOKING_CONFIRMATION = "email.booking_confirmation"
EMAIL_PAYMENT_RECEIPT = "email.payment_receipt"
EMAIL_INVOICE = "email.invoice"


async def email_enabled(session: AsyncSession, event_key: str) -> bool:
    """Is email switched on for this event, for this academy?

    Defaults to True when no row exists. The config table is populated lazily by
    the settings screen, and an academy that has never opened it should still get
    booking confirmations — silence is the worse failure.
    """
    row = (
        await session.execute(
            select(NotificationChannelConfig).where(
                NotificationChannelConfig.event_key == event_key
            )
        )
    ).scalar_one_or_none()
    return True if row is None else row.email_enabled


async def enqueue_email(
    session: AsyncSession,
    *,
    kind: str,
    event_key: str,
    recipient: str | None,
    payload: dict[str, Any],
) -> Job | None:
    """Queue one email. Returns None when there is nothing to send.

    The payload carries ids, not rendered text: the worker re-reads the booking at
    send time, so an email that goes out a minute later reflects the booking as it
    now stands rather than as it was when the row was written.
    """
    if not recipient or "@" not in recipient:
        # No address is not an error — walk-ins are frequently anonymous, and most
        # counter bookings have a phone and no email.
        return None

    if not await email_enabled(session, event_key):
        return None

    job = Job(
        kind=kind,
        payload={"event_key": event_key, "recipient": recipient, **payload},
    )
    session.add(job)
    return job


def as_id(value: Any) -> uuid.UUID | None:
    """Job payloads are JSON, so ids come back as strings."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
