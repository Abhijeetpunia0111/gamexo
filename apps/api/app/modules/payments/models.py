"""An academy's own payment gateway accounts.

`tenant_settings` deliberately excludes these — see the note at the bottom of
models/tenant.py. Brand colours and a live Razorpay key secret are not the same
kind of value and must not share a table: one is read by every request and shown on
a settings form, the other is a credential for moving somebody else's money.

── What is stored, and how ─────────────────────────────────────────────────────
Credentials are split by sensitivity, not by provider:

  * `public_config` — JSONB, in the clear. Key IDs, merchant IDs, salt indexes.
    These reach the browser in a checkout anyway; hiding them would buy nothing and
    cost the admin the ability to see which account is connected.

  * `secrets_ciphertext` — one Fernet token over a JSON object of every secret
    field. Encrypted with a key that lives in the environment, so a stolen database
    yields no working credentials. Never leaves the server.

  * `secret_hints` — JSONB, `{"key_secret": "8f2a"}`. The last four characters, so
    "is this the key I generated?" is answerable without the secret ever being sent
    back.

JSON rather than a column per credential because the fields differ per provider and
are defined in catalog.py — Razorpay has three, PayU has two, PhonePe needs a salt
index. A column per field would make the next gateway a migration.

── Why routing is two booleans and not one "active" flag ───────────────────────
The dashboard and the counter are genuinely different surfaces. An academy may well
take online payments through Razorpay while the POS tablet stays on cash and UPI, or
run a new gateway on the counter first before pointing the public site at it. What
must never happen is *two* gateways claiming the same surface, because then nothing
answers "which one charges this booking?" — so that is a unique index, below, rather
than something the router promises to keep true.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScoped
from app.db.types import enum_type
from app.modules.payments.catalog import PaymentProvider, ProviderMode

__all__ = ["PaymentProvider", "PaymentProviderConfig", "ProviderMode"]


class PaymentProviderConfig(TenantScoped):
    """One gateway account, for one academy."""

    __tablename__ = "payment_provider_config"
    __table_args__ = (
        # One configuration per gateway per academy. Connecting Razorpay twice is
        # never what anyone means; it is a double-submit or a stale form.
        Index("uq_payment_provider_tenant_provider", "tenant_id", "provider", unique=True),
        # ── The load-bearing pair ───────────────────────────────────────────
        # At most one gateway may collect for a given surface. Partial unique
        # indexes on a constant expression: with `WHERE collect_on_web`, the index
        # holds one row per tenant among the rows that have the flag set, which is
        # exactly "no two gateways both claim the dashboard".
        #
        # In Postgres rather than in the router because the router is not the only
        # writer this will ever have — a support script, a seed, a future bulk
        # onboarding tool. An invariant that decides where money goes should not
        # depend on every caller remembering to clear the other row first.
        Index(
            "uq_payment_provider_one_web",
            "tenant_id",
            unique=True,
            postgresql_where=text("collect_on_web"),
        ),
        Index(
            "uq_payment_provider_one_pos",
            "tenant_id",
            unique=True,
            postgresql_where=text("collect_on_pos"),
        ),
        # A gateway cannot be routed live payments with no secret to sign them
        # with. Enforced here so it survives a direct UPDATE, not only the API.
        CheckConstraint(
            "NOT (collect_on_web OR collect_on_pos) OR char_length(secrets_ciphertext) > 0",
            name="routed_gateway_has_credentials",
        ),
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        enum_type(PaymentProvider, name="payment_provider"), nullable=False
    )

    #: test vs live. Not derived from the key: Cashfree and PhonePe choose the
    #: environment by hostname, so the credential alone does not say which it is.
    mode: Mapped[ProviderMode] = mapped_column(
        enum_type(ProviderMode, name="payment_provider_mode"),
        default=ProviderMode.TEST,
        nullable=False,
    )

    public_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    secrets_ciphertext: Mapped[str] = mapped_column(Text, default="", nullable=False)
    secret_hints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    #: Which surface this gateway collects for. See the class docstring.
    collect_on_web: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    collect_on_pos: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Result of the last real call to the provider. Kept because "I pasted the key
    #: last month and it worked then" is not the same claim as "it works now", and
    #: a rotated-at-the-provider key fails silently until someone tries to pay.
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verification_error: Mapped[str | None] = mapped_column(Text)

    #: Who last touched the credential. Stored as an email rather than a FK so it
    #: still answers the question after that staff member is deleted — and this is
    #: precisely the change someone will need to trace.
    updated_by_email: Mapped[str | None] = mapped_column(String(320))

    @property
    def is_configured(self) -> bool:
        return bool(self.secrets_ciphertext)

    def __repr__(self) -> str:
        return f"<PaymentProviderConfig {self.provider} {self.mode}>"


def surface_column(surface: str) -> Any:
    """Map "web"/"pos" to the routing column, rejecting anything else.

    A helper rather than `getattr(cfg, f"collect_on_{surface}")` at call sites:
    the surface arrives from a query string, and getattr on unvalidated input is
    how a typo becomes an AttributeError 500 — or worse, how a crafted value
    reaches an attribute that was never meant to be addressable.
    """
    columns = {
        "web": PaymentProviderConfig.collect_on_web,
        "pos": PaymentProviderConfig.collect_on_pos,
    }
    if surface not in columns:
        raise ValueError(f"unknown surface {surface!r}")
    return columns[surface]
