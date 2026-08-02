"""Booking price calculation.

Mirrors the arithmetic the frontend already performs in `src/pages/WalkInBooking.tsx`,
so a quote shown during the wizard matches the booking that gets created. The rules
themselves come from the tenant's own settings rather than being hardcoded — that is
what makes the pricing white-label.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.booking.models import Court

TWO_PLACES = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    """Round to paise, half-up.

    Half-up rather than Python's default banker's rounding: an invoice line of
    ₹0.125 becoming ₹0.12 half the time and ₹0.13 the other half is impossible to
    reconcile against a printed receipt, and is not what an accountant expects.
    """
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def percent(value: Decimal | float | int, places: int = 1) -> float:
    """Round a percentage half-up.

    Python's built-in `round()` is banker's rounding, so `round(6.25, 1)` is 6.2 and
    `round(6.35, 1)` is 6.4 — the direction flips depending on the preceding digit.
    On a utilisation or attendance figure that reads as a bug. Same rule as `money()`
    above, for the same reason: predictable beats statistically neutral when a person
    is going to compare the number against one they worked out themselves.
    """
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class EquipmentLine:
    name: str
    qty: int
    rate: Decimal

    @property
    def amount(self) -> Decimal:
        return money(self.rate * self.qty)

    def as_json(self) -> dict[str, Any]:
        return {"name": self.name, "qty": self.qty, "rate": float(self.rate)}


@dataclass(frozen=True, slots=True)
class Quote:
    court_charge: Decimal
    equipment_charge: Decimal
    discount: Decimal
    taxes: Decimal
    total: Decimal
    is_peak: bool
    is_weekend: bool
    rate_applied: Decimal


def tenant_zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        # A bad timezone in settings must not take bookings down; IST is the
        # documented default and the only one in use today.
        return ZoneInfo("Asia/Kolkata")


def _parse_hhmm(value: str, fallback: time) -> time:
    try:
        hour, _, minute = value.partition(":")
        return time(int(hour), int(minute or 0))
    except (ValueError, TypeError):
        return fallback


def is_peak_slot(starts_at: datetime, booking_rules: dict[str, Any], tz: ZoneInfo) -> bool:
    """Is this slot inside the academy's peak window?

    Evaluated in the tenant's own timezone. Comparing in UTC would shift an Indian
    academy's 17:00 peak boundary by 5h30m and price the entire evening wrong.
    """
    local = starts_at.astimezone(tz)
    start = _parse_hhmm(str(booking_rules.get("peak_start", "17:00")), time(17, 0))
    end = _parse_hhmm(str(booking_rules.get("peak_end", "22:00")), time(22, 0))

    if start <= end:
        return start <= local.time() < end
    # Window wrapping past midnight, e.g. 20:00–02:00.
    return local.time() >= start or local.time() < end


def is_weekend(starts_at: datetime, tz: ZoneInfo) -> bool:
    return starts_at.astimezone(tz).weekday() >= 5  # Saturday, Sunday


def quote_booking(
    *,
    court: Court,
    starts_at: datetime,
    duration_min: int,
    equipment_lines: Iterable[EquipmentLine] = (),
    discount: Decimal = Decimal("0"),
    booking_rules: dict[str, Any],
    tax_config: dict[str, Any],
    timezone_name: str,
) -> Quote:
    """Price a booking.

    Follows the frontend exactly: the peak rate applies at peak hours *or* at
    weekends, court charge is pro-rated by the minute, and GST is charged on the
    discounted subtotal — not on the gross, which would tax money the customer never
    paid and is the more expensive mistake to discover during a GST audit.
    """
    tz = tenant_zone(timezone_name)
    peak = is_peak_slot(starts_at, booking_rules, tz)
    weekend = is_weekend(starts_at, tz)

    rate = court.peak_rate if (peak or weekend) else court.hourly_rate
    court_charge = money(Decimal(rate) * Decimal(duration_min) / Decimal(60))

    equipment_charge = money(sum((line.amount for line in equipment_lines), Decimal("0")))

    discount = money(max(Decimal("0"), discount))
    subtotal = court_charge + equipment_charge
    # Never let a discount exceed the bill and produce a negative invoice.
    discount = min(discount, subtotal)

    gst_rate = Decimal(str(tax_config.get("gst_rate", 18)))
    taxes = money((subtotal - discount) * gst_rate / Decimal(100))
    total = money(subtotal - discount + taxes)

    return Quote(
        court_charge=court_charge,
        equipment_charge=equipment_charge,
        discount=discount,
        taxes=taxes,
        total=total,
        is_peak=peak,
        is_weekend=weekend,
        rate_applied=money(rate),
    )
