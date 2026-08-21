"""Reading and writing gateway credentials.

The one rule this module exists to hold: a secret goes in encrypted and comes back
out only for a server-side call to the provider. Nothing here returns a secret in
anything shaped like a response body.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.crypto import decrypt, encrypt, last4
from app.modules.payments.catalog import ProviderMode, ProviderSpec
from app.modules.payments.models import PaymentProviderConfig


def read_secrets(config: PaymentProviderConfig) -> dict[str, str]:
    """Decrypt the secret bundle. Server-side callers only.

    Empty for a row that has never been given credentials, which is the state a
    config sits in only transiently — the router refuses to create one without.
    """
    if not config.secrets_ciphertext:
        return {}
    loaded = json.loads(decrypt(config.secrets_ciphertext))
    return {str(k): str(v) for k, v in loaded.items()}


def merge_submitted(
    spec: ProviderSpec,
    config: PaymentProviderConfig | None,
    submitted: dict[str, str],
) -> dict[str, str]:
    """Combine what the form sent with what is already stored.

    ── The asymmetry, which is deliberate ──────────────────────────────────────
    A blank **secret** field means "leave it alone". It has to: the browser was
    never given the real value, so an edit that only changes the mode would
    otherwise submit an empty Key Secret and wipe a working credential. The form
    shows `••••8f2a` in its place precisely because there is nothing real to put
    there.

    A blank **public** field means what it says and clears the value. Those are
    round-tripped to the browser intact, so a blank one is a real edit.

    The consequence worth knowing: there is no way to blank a secret through this
    path. Disconnecting the gateway is how you remove one, and that deletes the
    whole row rather than leaving a half-configured gateway behind.
    """
    existing_secrets = read_secrets(config) if config else {}
    existing_public = dict(config.public_config) if config else {}

    merged: dict[str, str] = {}
    for f in spec.fields:
        incoming = (submitted.get(f.name) or "").strip()
        if incoming:
            merged[f.name] = incoming
        elif f.secret:
            merged[f.name] = existing_secrets.get(f.name, "")
        elif f.name in submitted:
            merged[f.name] = ""  # explicitly cleared
        else:
            merged[f.name] = str(existing_public.get(f.name, "") or "")

    return merged


def apply_credentials(
    config: PaymentProviderConfig,
    spec: ProviderSpec,
    mode: ProviderMode,
    values: dict[str, str],
    *,
    actor_email: str | None,
) -> None:
    """Write a full credential set onto the row, encrypting the secret half.

    Whole-bundle, not field-by-field: the ciphertext is one Fernet token over one
    JSON object, so a partial write would have to decrypt, patch and re-encrypt
    anyway. `merge_submitted` is what turns a partial form into a full set.

    Any previous verification result is dropped. It described the old credential,
    and leaving a green tick attached to a key that was just replaced is worse than
    showing nothing.
    """
    secrets: dict[str, str] = {}
    public: dict[str, Any] = {}
    hints: dict[str, Any] = {}

    for f in spec.fields:
        value = (values.get(f.name) or "").strip()
        if f.secret:
            if value:
                secrets[f.name] = value
                hints[f.name] = last4(value)
        elif value:
            public[f.name] = value

    config.mode = mode
    config.public_config = public
    config.secret_hints = hints
    config.secrets_ciphertext = encrypt(json.dumps(secrets)) if secrets else ""
    config.updated_by_email = actor_email
    config.last_verified_at = None
    config.last_verification_error = None
