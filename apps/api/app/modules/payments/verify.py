"""Asking the provider whether a credential actually works.

Format checks (catalog.format_problems) catch typos. Only the provider can tell us
the key is real, enabled, and belongs to an account that can take payments — and the
alternative to asking is finding out from a customer at the counter on a Saturday.

── Rules every check here obeys ────────────────────────────────────────────────
1. **A failure to verify is never a failure to save.** The network may be down, the
   provider may be having an outage, we may be behind an egress firewall. None of
   those mean the credential is wrong, so this returns a result object and the
   caller stores it. Nothing here raises into a 500.

2. **The secret is never echoed.** Not into the returned message, not into a log.
   Provider error bodies are summarised, not passed through, because some providers
   quote the offending value back.

3. **Read-only calls only.** Every request below either lists or fetches. Verifying
   a credential must not create an order, a customer, or a charge.

── What "not supported" means ──────────────────────────────────────────────────
PhonePe and PayU have no authenticated read endpoint that answers "are these
credentials valid" — both sign each request with the salt and are only exercised by
initiating a transaction, which rule 3 forbids. So they report honestly that the
format looks right and nothing more. A green tick they had not earned would be
worse than no tick.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.modules.payments.catalog import PaymentProvider, ProviderMode

logger = logging.getLogger("gamexo.payments")

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    message: str
    #: True when we genuinely called the provider. False means format-only, and the
    #: UI says so rather than implying the credential has been proven.
    checked_live: bool


async def verify(
    provider: PaymentProvider,
    mode: ProviderMode,
    public: dict[str, str],
    secrets: dict[str, str],
) -> VerificationResult:
    checker = _CHECKS.get(provider)
    if checker is None:
        return VerificationResult(
            ok=True,
            message=(
                "Saved. This gateway has no read-only endpoint to test credentials "
                "against, so it will be confirmed by your first live payment."
            ),
            checked_live=False,
        )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            return await checker(client, mode, public, secrets)
    except httpx.TimeoutException:
        return VerificationResult(
            ok=False,
            message="The provider did not respond in time. The credentials are saved — try again.",
            checked_live=False,
        )
    except httpx.HTTPError as exc:
        # Type only. The string form of an httpx error can include the request URL,
        # and Stripe-style credentials in a URL would land in the response body.
        logger.warning("payment credential check failed: %s", type(exc).__name__)
        return VerificationResult(
            ok=False,
            message="Could not reach the provider. The credentials are saved — try again.",
            checked_live=False,
        )


async def _razorpay(
    client: httpx.AsyncClient,
    mode: ProviderMode,
    public: dict[str, str],
    secrets: dict[str, str],
) -> VerificationResult:
    """One page of one payment, which is the cheapest authenticated read they have.

    `count=1` because the response is discarded — this asks whether HTTP Basic with
    this pair is accepted, nothing more. Razorpay picks test vs live from the key
    itself, so there is no per-mode host.
    """
    del mode
    res = await client.get(
        "https://api.razorpay.com/v1/payments",
        params={"count": 1},
        auth=(public.get("key_id", ""), secrets.get("key_secret", "")),
    )
    if res.status_code == 200:
        return VerificationResult(True, "Razorpay accepted these credentials.", True)
    if res.status_code in (401, 403):
        return VerificationResult(
            False,
            "Razorpay rejected these credentials. Check the Key ID and Key Secret are "
            "from the same key pair and that the key is still active.",
            True,
        )
    return VerificationResult(
        False, f"Razorpay returned HTTP {res.status_code}.", True
    )


async def _cashfree(
    client: httpx.AsyncClient,
    mode: ProviderMode,
    public: dict[str, str],
    secrets: dict[str, str],
) -> VerificationResult:
    """Fetch an order that does not exist.

    Cashfree has no ping endpoint, and every other call creates something. The
    distinction that matters is available before the lookup happens: bad credentials
    fail authentication (401/403), good ones get far enough to report that the order
    is missing (404). So a 404 here is the success case — spelled out because it
    looks exactly like a bug otherwise.
    """
    base = "https://sandbox.cashfree.com/pg" if mode is ProviderMode.TEST else "https://api.cashfree.com/pg"
    res = await client.get(
        f"{base}/orders/gamexo_credential_check",
        headers={
            "x-client-id": public.get("app_id", ""),
            "x-client-secret": secrets.get("secret_key", ""),
            "x-api-version": "2023-08-01",
        },
    )
    if res.status_code in (401, 403):
        return VerificationResult(
            False,
            f"Cashfree rejected these credentials for the {mode.value} environment. "
            "Check the App ID and Secret Key, and that the mode above matches the keys.",
            True,
        )
    if res.status_code in (200, 400, 404):
        return VerificationResult(
            True, f"Cashfree accepted these credentials ({mode.value}).", True
        )
    return VerificationResult(False, f"Cashfree returned HTTP {res.status_code}.", True)


async def _stripe(
    client: httpx.AsyncClient,
    mode: ProviderMode,
    public: dict[str, str],
    secrets: dict[str, str],
) -> VerificationResult:
    """`/v1/balance` — authenticated, read-only, and available on every account."""
    del mode, public
    res = await client.get(
        "https://api.stripe.com/v1/balance",
        headers={"Authorization": f"Bearer {secrets.get('secret_key', '')}"},
    )
    if res.status_code == 200:
        return VerificationResult(True, "Stripe accepted these credentials.", True)
    if res.status_code in (401, 403):
        return VerificationResult(
            False, "Stripe rejected this secret key. Check it has not been revoked.", True
        )
    return VerificationResult(False, f"Stripe returned HTTP {res.status_code}.", True)


_CHECKS = {
    PaymentProvider.RAZORPAY: _razorpay,
    PaymentProvider.CASHFREE: _cashfree,
    PaymentProvider.STRIPE: _stripe,
}
