"""Symmetric encryption helpers for storing sensitive credentials at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the *cryptography* package.
The Fernet key is derived deterministically from the application's SECRET_KEY
via SHA-256 so no extra configuration variable is required.

Usage::

    from app.core.encryption import encrypt, decrypt

    token  = encrypt("sg-my-api-key")
    plain  = decrypt(token)   # → "sg-my-api-key"
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _make_fernet() -> Fernet:
    """Derive a stable Fernet key from SECRET_KEY (imported lazily to avoid
    circular imports at module load time)."""
    # Import here to avoid circular import on startup
    from app.core.config import settings  # noqa: PLC0415

    raw = settings.SECRET_KEY.encode()
    # SHA-256 gives 32 bytes → base64url-encode it → valid Fernet key
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Encrypt *plaintext* and return a URL-safe base64 token (str)."""
    fernet = _make_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt`.

    Raises :class:`ValueError` when the token is invalid or has been tampered
    with — callers should treat this as a configuration error.
    """
    fernet = _make_fernet()
    try:
        return fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Credential decryption failed — token invalid or key mismatch") from exc
