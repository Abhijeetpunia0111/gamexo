"""What the emails say.

Kept apart from `mail.py` so wording and transport change independently, and so a
template can be rendered in a test without an SMTP server anywhere near it.

Hand-built HTML rather than a template engine. These are transactional emails —
three of them, mostly tables of numbers — and mail clients are hostile enough
(Outlook ignores most CSS, Gmail strips <style> blocks) that everything has to be
inline-styled anyway. A Jinja dependency would buy nothing here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

from app.models.tenant import TenantSettings
from app.modules.booking.models import Booking

CURRENCY = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€"}


def money(amount: Decimal | float | int, currency: str = "INR") -> str:
    symbol = CURRENCY.get(currency.upper(), f"{currency.upper()} ")
    return f"{symbol}{Decimal(str(amount)):,.2f}"


def local(moment: datetime, timezone_name: str) -> datetime:
    """Times are stored as instants; a customer reads them in the venue's zone.

    Sending "your court is at 14:30" when they booked 20:00 IST is the single most
    confusing thing a booking email can do.
    """
    try:
        return moment.astimezone(ZoneInfo(timezone_name))
    except Exception:  # noqa: BLE001 — a bad tz must not stop the mail going out
        return moment


def _shell(settings: TenantSettings, heading: str, intro: str, body: str, footer: str) -> str:
    """The one HTML frame every message shares, in the tenant's own colours."""
    name = escape(settings.business_name)
    contact = " · ".join(
        escape(part) for part in (settings.phone, settings.email) if part
    )
    return f"""\
<div style="margin:0;padding:24px 12px;background:{settings.brand_background};font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid rgba(0,0,0,0.06);">
    <div style="background:{settings.brand_primary};padding:20px 24px;">
      <p style="margin:0;color:#ffffff;font-size:17px;font-weight:700;">{name}</p>
    </div>
    <div style="padding:24px;">
      <h1 style="margin:0 0 6px;font-size:20px;color:#111111;">{escape(heading)}</h1>
      <p style="margin:0 0 20px;font-size:14px;color:#555555;line-height:1.5;">{escape(intro)}</p>
      {body}
    </div>
    <div style="padding:16px 24px;background:#fafafa;border-top:1px solid rgba(0,0,0,0.06);">
      <p style="margin:0;font-size:12px;color:#888888;line-height:1.5;">{escape(footer)}</p>
      {f'<p style="margin:6px 0 0;font-size:12px;color:#888888;">{contact}</p>' if contact else ''}
    </div>
  </div>
</div>"""


def _rows(pairs: list[tuple[str, str]], *, emphasise_last: bool = False) -> str:
    out = []
    for i, (label, value) in enumerate(pairs):
        last = emphasise_last and i == len(pairs) - 1
        weight = "700" if last else "400"
        border = "border-top:1px solid rgba(0,0,0,0.08);" if last else ""
        out.append(
            f'<tr><td style="padding:7px 0;{border}font-size:14px;color:#555555;">{escape(label)}</td>'
            f'<td style="padding:7px 0;{border}font-size:14px;color:#111111;font-weight:{weight};'
            f'text-align:right;">{escape(value)}</td></tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;">{"".join(out)}</table>'


# ── Booking confirmation ────────────────────────────────────────────────────


def booking_confirmation(
    booking: Booking,
    settings: TenantSettings,
    *,
    court_name: str,
    sport_name: str,
) -> tuple[str, str, str]:
    """Returns (subject, text, html)."""
    starts = local(booking.starts_at, settings.timezone)
    ends = local(booking.ends_at, settings.timezone)
    cur = settings.currency

    when = f"{starts:%a %d %b %Y}, {starts:%I:%M %p} – {ends:%I:%M %p}".replace(" 0", " ")
    subject = f"Booking confirmed · {court_name} · {starts:%d %b, %I:%M %p}".replace(" 0", " ")

    lines: list[tuple[str, str]] = [
        ("Sport", sport_name),
        ("Court", court_name),
        ("When", when),
        ("Duration", f"{booking.duration_min} min"),
    ]

    charges: list[tuple[str, str]] = [("Court", money(booking.court_charge, cur))]
    for item in booking.equipment or []:
        qty = item.get("qty", 1)
        charges.append((f"{item.get('name', 'Add-on')} × {qty}", ""))
    if booking.equipment_charge:
        charges.append(("Add-ons", money(booking.equipment_charge, cur)))
    if booking.discount:
        charges.append(("Discount", f"-{money(booking.discount, cur)}"))
    charges.append(("Taxes", money(booking.taxes, cur)))
    charges.append(("Total", money(booking.total, cur)))

    balance = booking.total - booking.amount_paid
    outstanding = (
        f"{money(balance, cur)} is payable at the venue."
        if balance > 0
        else "Paid in full — nothing to settle on arrival."
    )

    text = "\n".join(
        [
            f"{settings.business_name} — booking confirmed",
            "",
            f"{sport_name} · {court_name}",
            when,
            "",
            *(f"{label}: {value}" for label, value in charges if value),
            "",
            outstanding,
            f"Reference: {booking.id}",
        ]
    )

    html = _shell(
        settings,
        "Your court is booked",
        f"Hi {booking.customer_name or 'there'}, here are the details.",
        _rows(lines)
        + '<div style="height:18px"></div>'
        + _rows([c for c in charges if c[1]], emphasise_last=True)
        + f'<p style="margin:18px 0 0;font-size:14px;color:#111111;">{escape(outstanding)}</p>',
        f"Reference {booking.id}. Please arrive a few minutes early.",
    )
    return subject, text, html


# ── Payment receipt ─────────────────────────────────────────────────────────


def payment_receipt(
    settings: TenantSettings,
    *,
    customer_name: str,
    amount: Decimal,
    method: str,
    reference: str,
    balance_remaining: Decimal | None = None,
) -> tuple[str, str, str]:
    cur = settings.currency
    subject = f"Payment received · {money(amount, cur)}"

    rows = [
        ("Amount", money(amount, cur)),
        ("Method", method.upper()),
        ("Reference", reference),
    ]
    if balance_remaining is not None and balance_remaining > 0:
        rows.append(("Still outstanding", money(balance_remaining, cur)))

    closing = (
        f"{money(balance_remaining, cur)} remains on this booking."
        if balance_remaining is not None and balance_remaining > 0
        else "This settles the balance in full. Thank you."
    )

    text = "\n".join(
        [
            f"{settings.business_name} — payment received",
            "",
            *(f"{label}: {value}" for label, value in rows),
            "",
            closing,
        ]
    )
    html = _shell(
        settings,
        "Payment received",
        f"Thanks {customer_name or 'there'} — we've recorded your payment.",
        _rows(rows, emphasise_last=False)
        + f'<p style="margin:18px 0 0;font-size:14px;color:#111111;">{escape(closing)}</p>',
        "This is a receipt for your records.",
    )
    return subject, text, html


# ── Invoice ─────────────────────────────────────────────────────────────────


def invoice_raised(
    settings: TenantSettings,
    *,
    invoice_no: str,
    customer_name: str,
    items: list[dict],
    subtotal: Decimal,
    gst: Decimal,
    discount: Decimal,
    total: Decimal,
    balance_due: Decimal,
) -> tuple[str, str, str]:
    cur = settings.currency
    subject = f"Invoice {invoice_no} · {money(total, cur)}"

    line_rows = [
        (f"{item.get('description', 'Item')} × {item.get('qty', 1)}", money(item.get("amount", 0), cur))
        for item in items
    ]
    totals = [("Subtotal", money(subtotal, cur))]
    if discount:
        totals.append(("Discount", f"-{money(discount, cur)}"))
    totals.append(("GST", money(gst, cur)))
    totals.append(("Total", money(total, cur)))

    closing = (
        f"{money(balance_due, cur)} is outstanding."
        if balance_due > 0
        else "Paid in full — thank you."
    )

    text = "\n".join(
        [
            f"{settings.business_name} — invoice {invoice_no}",
            "",
            *(f"{label}: {value}" for label, value in line_rows),
            "",
            *(f"{label}: {value}" for label, value in totals),
            "",
            closing,
        ]
    )
    html = _shell(
        settings,
        f"Invoice {invoice_no}",
        f"Hi {customer_name or 'there'}, here is your invoice.",
        _rows(line_rows)
        + '<div style="height:18px"></div>'
        + _rows(totals, emphasise_last=True)
        + f'<p style="margin:18px 0 0;font-size:14px;color:#111111;">{escape(closing)}</p>',
        f"Invoice {invoice_no}"
        + (f" · GST {settings.gst_number}" if settings.gst_number else ""),
    )
    return subject, text, html
