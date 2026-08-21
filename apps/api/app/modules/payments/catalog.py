"""What each payment gateway needs, described as data.

Every gateway wants a different set of credentials under different names — Razorpay
calls them Key ID and Key Secret, Cashfree calls them App ID and Secret Key, PhonePe
wants a Merchant ID plus a Salt Key *and* a Salt Index. The obvious implementation
is a form per provider and a column per field, and it means the next gateway an
academy asks for is a migration, a schema change and a frontend release.

So the shape of a provider lives here instead, and both sides read it: the API
validates against these definitions, and the Integrations screen renders its form
from `GET /payments/providers`. Adding PayTM is one entry in `CATALOG` — no
migration, no new column, no frontend change.

That is also why the model stores credentials as JSON rather than named columns.
See `models.PaymentProviderConfig`.

── On the values in here ───────────────────────────────────────────────────────
Placeholders and prefixes are the documented formats as of writing. They are used
only to catch paste errors early and are never a hard gate on saving a credential
that authenticates — a provider is free to change its key format, and the check
below must not be the reason an academy cannot take payments that afternoon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PaymentProvider(StrEnum):
    RAZORPAY = "razorpay"
    CASHFREE = "cashfree"
    PHONEPE = "phonepe"
    PAYU = "payu"
    STRIPE = "stripe"


class ProviderMode(StrEnum):
    """Which of the provider's two worlds a credential belongs to.

    Kept explicit rather than inferred from the key, because only some providers
    encode it in the credential — Cashfree and PhonePe pick test vs live by which
    hostname you call, so nothing about the key itself would tell us.
    """

    TEST = "test"
    LIVE = "live"


@dataclass(frozen=True)
class ProviderField:
    """One input on the Integrations form."""

    name: str
    label: str
    placeholder: str = ""
    help: str = ""

    #: Encrypted at rest and never returned to the browser. A non-secret field is
    #: stored in the clear and echoed back, because the admin needs to see which
    #: account is connected.
    secret: bool = False

    required: bool = True

    #: Prefix the value carries for a given mode, where the provider encodes the
    #: environment in the credential. Only set where it is genuinely reliable —
    #: it is what catches the single most common setup mistake, pasting a test key
    #: into a live configuration and discovering it at the counter.
    mode_prefixes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSpec:
    id: PaymentProvider
    label: str
    tagline: str
    #: Where in the provider's own dashboard these credentials are generated. The
    #: question an admin actually has on this screen is "where do I get this?".
    credentials_url: str
    docs_url: str
    fields: tuple[ProviderField, ...]

    #: Whether `POST /payments/providers/{id}/verify` can make a real authenticated
    #: call. False means the credentials can only be checked for shape, which the
    #: UI says out loud rather than implying a green tick it did not earn.
    supports_live_check: bool = False

    @property
    def secret_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.secret)

    @property
    def public_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if not f.secret)


CATALOG: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id=PaymentProvider.RAZORPAY,
        label="Razorpay",
        tagline="Cards, UPI, netbanking and wallets. The default for most Indian academies.",
        credentials_url="https://dashboard.razorpay.com/app/website-app-settings/api-keys",
        docs_url="https://razorpay.com/docs/payments/dashboard/settings/api-keys/",
        supports_live_check=True,
        fields=(
            ProviderField(
                name="key_id",
                label="Key ID",
                placeholder="rzp_live_XXXXXXXXXXXXXX",
                help="Public half of the pair. Safe to show; it reaches the browser anyway.",
                mode_prefixes={"test": "rzp_test_", "live": "rzp_live_"},
            ),
            ProviderField(
                name="key_secret",
                label="Key Secret",
                placeholder="••••••••••••••••••••••••",
                help="Shown once by Razorpay when the key is generated. Regenerate there if lost.",
                secret=True,
            ),
            ProviderField(
                name="webhook_secret",
                label="Webhook Secret",
                placeholder="Optional",
                help="Set this if you have configured a webhook, so callbacks can be verified.",
                secret=True,
                required=False,
            ),
        ),
    ),
    ProviderSpec(
        id=PaymentProvider.CASHFREE,
        label="Cashfree Payments",
        tagline="Payment gateway with same-day settlements and payouts.",
        credentials_url="https://merchant.cashfree.com/merchants/pg/developers/api-keys",
        docs_url="https://docs.cashfree.com/docs/api-keys",
        supports_live_check=True,
        fields=(
            ProviderField(
                name="app_id",
                label="App ID",
                placeholder="TEST1234567890abcdef",
                help="Sent as the x-client-id header.",
            ),
            ProviderField(
                name="secret_key",
                label="Secret Key",
                placeholder="cfsk_ma_test_••••••••",
                help=(
                    "Sent as x-client-secret. Cashfree also signs its webhooks with this, "
                    "so there is no separate webhook secret."
                ),
                secret=True,
            ),
        ),
    ),
    ProviderSpec(
        id=PaymentProvider.PHONEPE,
        label="PhonePe Payment Gateway",
        tagline="UPI-first checkout with the widest UPI reach in India.",
        credentials_url="https://business.phonepe.com/developer-settings",
        docs_url="https://developer.phonepe.com/v1/reference/pay-api/",
        fields=(
            ProviderField(
                name="merchant_id",
                label="Merchant ID",
                placeholder="M22XXXXXXXXXX",
                help="From PhonePe Business → Developer Settings.",
            ),
            ProviderField(
                name="salt_key",
                label="Salt Key",
                placeholder="••••••••-••••-••••-••••-••••••••••••",
                help="Used to sign every request. Treat it like a password.",
                secret=True,
            ),
            ProviderField(
                name="salt_index",
                label="Salt Index",
                placeholder="1",
                help="Usually 1. Increments when PhonePe rotates your salt key.",
            ),
        ),
    ),
    ProviderSpec(
        id=PaymentProvider.PAYU,
        label="PayU",
        tagline="Long-standing Indian gateway with strong EMI and card coverage.",
        credentials_url="https://onboarding.payu.in/app/account/dashboard",
        docs_url="https://docs.payu.in/docs/generate-merchant-key-salt",
        fields=(
            ProviderField(
                name="merchant_key",
                label="Merchant Key",
                placeholder="gtKFFx",
                help="Identifies your PayU account on every request.",
            ),
            ProviderField(
                name="merchant_salt",
                label="Merchant Salt",
                placeholder="••••••••••••••••",
                help="Signs the request hash. Never send it to the browser.",
                secret=True,
            ),
        ),
    ),
    ProviderSpec(
        id=PaymentProvider.STRIPE,
        label="Stripe",
        tagline="For academies taking international card payments.",
        credentials_url="https://dashboard.stripe.com/apikeys",
        docs_url="https://docs.stripe.com/keys",
        supports_live_check=True,
        fields=(
            ProviderField(
                name="publishable_key",
                label="Publishable Key",
                placeholder="pk_live_XXXXXXXXXXXX",
                help="Public by design — this one is meant to be in the page.",
                mode_prefixes={"test": "pk_test_", "live": "pk_live_"},
            ),
            ProviderField(
                name="secret_key",
                label="Secret Key",
                placeholder="sk_live_••••••••••••",
                help="Full access to your Stripe account. Restricted keys work too.",
                secret=True,
                mode_prefixes={"test": "sk_test_", "live": "sk_live_"},
            ),
            ProviderField(
                name="webhook_secret",
                label="Webhook Signing Secret",
                placeholder="whsec_… (optional)",
                help="From the webhook endpoint's page in the Stripe dashboard.",
                secret=True,
                required=False,
            ),
        ),
    ),
)

BY_ID: dict[PaymentProvider, ProviderSpec] = {spec.id: spec for spec in CATALOG}


def spec_for(provider: PaymentProvider) -> ProviderSpec:
    return BY_ID[provider]


def format_problems(
    spec: ProviderSpec, mode: ProviderMode, values: dict[str, str]
) -> list[str]:
    """Everything obviously wrong with these credentials, in plain language.

    Deliberately about *shape*, not authenticity — only the provider can say
    whether a key works, and `verify.py` asks it. What this catches is the class of
    mistake that otherwise surfaces as a failed payment during a Saturday rush:
    a missing field, a test key saved as live, or the key id pasted into the secret
    box (which reads as "wrong password" from the provider and sends the admin
    hunting in the wrong place).

    Returns a list rather than raising on the first, so the form can mark every bad
    field at once instead of one per round trip.
    """
    problems: list[str] = []

    for f in spec.fields:
        value = (values.get(f.name) or "").strip()

        if not value:
            if f.required:
                problems.append(f"{f.label} is required.")
            continue

        expected = f.mode_prefixes.get(mode.value)
        if expected and not value.startswith(expected):
            other = next(
                (m for m, p in f.mode_prefixes.items() if p and value.startswith(p)),
                None,
            )
            if other:
                problems.append(
                    f"{f.label} is a {other} credential, but this gateway is set to "
                    f"{mode.value}. Switch the mode, or paste the {mode.value} key."
                )
            else:
                problems.append(f"{f.label} should start with {expected!r}.")

    # A secret that equals a public field is the paste-into-the-wrong-box error.
    public_values = {
        (values.get(f.name) or "").strip() for f in spec.fields if not f.secret
    }
    public_values.discard("")
    for f in spec.fields:
        value = (values.get(f.name) or "").strip()
        if f.secret and value and value in public_values:
            problems.append(f"{f.label} is the same as a public field — check the paste.")

    return problems
