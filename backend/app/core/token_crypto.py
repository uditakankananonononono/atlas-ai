"""Encryption for stored third-party tokens (Gmail refresh tokens, CalDAV
credentials). Uses Fernet (AES-128-CBC + HMAC) from the `cryptography`
package. The key comes from ATLAS_TOKEN_KEY; a per-tenant key is derived so
one tenant's rows cannot be decrypted with another tenant's key.
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet


class TokenCryptoError(RuntimeError):
    pass


def _derive_key(master_secret: str, tenant_id: str) -> bytes:
    digest = hashlib.sha256(f"{master_secret}::{tenant_id}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


class TokenCipher:
    """Tenant-scoped symmetric cipher for tokens at rest."""

    def __init__(self, tenant_id: str, master_secret: str | None = None) -> None:
        secret = master_secret or os.getenv("ATLAS_TOKEN_KEY")
        if not secret:
            raise TokenCryptoError(
                "ATLAS_TOKEN_KEY is not configured; refusing to store tokens unencrypted"
            )
        self._fernet = Fernet(_derive_key(secret, tenant_id))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
