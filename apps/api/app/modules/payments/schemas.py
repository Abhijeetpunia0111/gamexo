"""The Integrations screen's contract.

The asymmetry to keep in mind reading this file: credentials go **in** through
`values` — one flat map of field name to value, secrets included — and come **out**
as `public_config` plus `secret_hints`. No response model here has a field that
could carry a secret, which is a property worth being able to check by reading the
schemas rather than by auditing every handler.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.catalog import PaymentProvider, ProviderMode

ORM = ConfigDict(from_attributes=True)


class ProviderFieldOut(BaseModel):
    """One input the Integrations form should render."""

    name: str
    label: str
    placeholder: str
    help: str
    secret: bool
    required: bool
    #: `{"test": "rzp_test_", "live": "rzp_live_"}` where the provider encodes the
    #: environment in the key. Lets the form warn before the round trip.
    mode_prefixes: dict[str, str]


class ProviderConfigOut(BaseModel):
    """A connected gateway, with everything secret removed.

    `secret_hints` is the last four characters of each secret — enough to recognise
    a key, useless to anyone who steals the response.
    """

    model_config = ORM

    provider: PaymentProvider
    mode: ProviderMode
    public_config: dict[str, Any]
    secret_hints: dict[str, Any]
    is_configured: bool

    collect_on_web: bool
    collect_on_pos: bool

    last_verified_at: datetime | None
    last_verification_error: str | None
    updated_by_email: str | None
    updated_at: datetime


class ProviderOut(BaseModel):
    """A gateway we support, and this academy's configuration of it if any."""

    id: PaymentProvider
    label: str
    tagline: str
    credentials_url: str
    docs_url: str
    supports_live_check: bool
    fields: list[ProviderFieldOut]
    config: ProviderConfigOut | None


class IntegrationsOut(BaseModel):
    """Everything the payment half of the screen needs, in one request."""

    #: False when SECRETS_ENCRYPTION_KEY is absent from the environment. The screen
    #: explains that instead of offering a form whose save is guaranteed to fail —
    #: and, more to the point, instead of inviting someone to type a live payment
    #: secret into a box that cannot store it safely.
    secrets_available: bool
    providers: list[ProviderOut]


class ProviderConfigUpsert(BaseModel):
    mode: ProviderMode = ProviderMode.TEST

    #: Field name to value, per the provider's `fields`. Unknown names are ignored
    #: rather than rejected, so a browser running last week's bundle after a catalog
    #: change degrades to "that field was dropped" instead of a hard failure.
    #:
    #: A **blank secret means keep the stored one** — the browser never received the
    #: real value and cannot send it back. See service.merge_submitted.
    values: dict[str, str] = Field(default_factory=dict)

    #: Verify against the provider before returning. On by default: an admin pasting
    #: a key wants to know now, not at the counter. Turn it off for a slow or
    #: unreachable network — the credentials are stored either way.
    verify: bool = True


class RoutingUpdate(BaseModel):
    """Which surfaces this gateway collects for.

    Omitted means unchanged, so the dashboard toggle cannot silently reset the POS.
    Setting either to true takes it away from whichever gateway currently holds it —
    only one gateway can collect for a surface.
    """

    collect_on_web: bool | None = None
    collect_on_pos: bool | None = None


class VerificationOut(BaseModel):
    ok: bool
    message: str
    #: False means we could not actually call the provider — either it has no
    #: read-only endpoint to test against, or the call did not complete. Not the
    #: same as a credential being wrong, and the UI must not present it as one.
    checked_live: bool


class ProviderSaveOut(BaseModel):
    config: ProviderConfigOut
    verification: VerificationOut | None


class ActiveGatewayOut(BaseModel):
    """What a checkout needs to start a payment on one surface.

    `public_config` only — the key id a client SDK needs and nothing more. The
    secret never leaves the server; signing an order is a server-side call.
    """

    provider: PaymentProvider
    label: str
    mode: ProviderMode
    public_config: dict[str, Any]
