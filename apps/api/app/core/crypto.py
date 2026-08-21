"""Encryption at rest for secrets an academy hands us.

This exists for one class of value: a credential belonging to *someone else's*
account that we must be able to replay verbatim. A Razorpay key secret is the
example — we have to send it to Razorpay on every charge, so unlike a password it
cannot be hashed. Hashing is one-way; this has to come back.

That makes the threat model different from `core/security.py`. There, a stolen
database yields bcrypt hashes and no logins. Here, a stolen database would yield
live payment credentials for every academy on the platform — the ability to move
their money — unless the ciphertext is useless without a key that is not in the
database. So the key lives in the environment, and a dump alone is inert.

── Why Fernet ──────────────────────────────────────────────────────────────────
AES-128-CBC with an HMAC-SHA256 over the ciphertext, from `cryptography`'s recipes
layer. Authenticated, so a tampered token fails loudly instead of decrypting to
garbage that we would then send to a payment provider. It also picks the IV itself,
which removes the single most common way hand-rolled AES goes wrong.

Note that it is *not* deterministic: encrypting the same secret twice gives
different tokens. That rules out querying by ciphertext, which is fine — nothing
looks a credential up by its value.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings


class SecretsNotConfigured(RuntimeError):
    """No encryption key in the environment.

    Raised at use, never at import: an academy that has not connected a payment
    gateway is unaffected, and the API must still boot and serve bookings on a
    deployment where this was never set up.
    """


class SecretDecryptionError(RuntimeError):
    """Stored ciphertext will not open with any configured key.

    Almost always means the key was rotated without keeping the old one in
    SECRETS_ENCRYPTION_KEY. Surfaced as its own type so the router can say
    "re-enter the credential" rather than returning a 500 that reads like a bug.
    """


def generate_key() -> str:
    """A fresh key, for `SECRETS_ENCRYPTION_KEY`.

        python -c "from app.core.crypto import generate_key; print(generate_key())"
    """
    return Fernet.generate_key().decode()


@lru_cache(maxsize=1)
def _box() -> MultiFernet:
    """The configured keys, newest first.

    A list rather than one key so the encryption key can be rotated without a
    downtime window: put the new key first, keep the old one second, and every
    existing ciphertext still opens while new writes use the new key. Once
    everything has been rewritten the old key can be dropped.
    """
    raw = settings.secrets_encryption_key
    if raw is None:
        raise SecretsNotConfigured(
            "SECRETS_ENCRYPTION_KEY is not set, so payment credentials cannot be "
            "stored. Generate one with: python -c \"from app.core.crypto import "
            'generate_key; print(generate_key())"'
        )

    keys = [part.strip() for part in raw.get_secret_value().split(",") if part.strip()]
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except (ValueError, TypeError) as exc:
        raise SecretsNotConfigured(
            "SECRETS_ENCRYPTION_KEY is not a valid Fernet key (32 url-safe "
            "base64-encoded bytes). Comma-separate multiple keys to rotate."
        ) from exc


def is_configured() -> bool:
    """Whether secrets can be stored at all.

    The Integrations screen asks this so it can explain that credentials are
    unavailable on this deployment, instead of letting an admin type a live
    payment secret into a form whose save is going to fail.
    """
    try:
        _box()
    except SecretsNotConfigured:
        return False
    return True


def encrypt(plaintext: str) -> str:
    return _box().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _box().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise SecretDecryptionError(
            "Stored credential could not be decrypted with any configured key."
        ) from exc


def last4(secret: str) -> str:
    """The tail of a secret, for display.

    Four characters is what every provider's own dashboard shows, and it is what
    makes "is the key on this screen the one I generated?" answerable without ever
    sending the secret back to the browser.

    Guarded against short input: a 3-character secret is certainly a paste error,
    and echoing the whole of it would be the one case where this leaks everything.
    """
    return secret[-4:] if len(secret) >= 8 else "••••"
