"""Dependency-free salted password/PIN hashing.

The encoded form fits the existing ``Kullanicilar.sifre_hash nvarchar(255)``
column and is intentionally self-describing so the work factor can be raised
later without a schema change.
"""

import base64
import binascii
import hashlib
import hmac
import secrets


PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_SALT_BYTES = 16
PASSWORD_DIGEST_BYTES = 32
_MAX_PASSWORD_BYTES = 1_024
_MAX_ITERATIONS = 2_000_000


def _encode_component(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_component(value: str) -> bytes:
    if not value or "=" in value:
        raise ValueError("Invalid encoded password component")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid encoded password component") from exc


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("Password must be text")
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > _MAX_PASSWORD_BYTES:
        raise ValueError("Password length is invalid")
    return encoded


def hash_password(
    password: str,
    *,
    iterations: int = PASSWORD_HASH_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise ValueError("Invalid PBKDF2 iteration count")
    if iterations < PASSWORD_HASH_ITERATIONS or iterations > _MAX_ITERATIONS:
        raise ValueError("Invalid PBKDF2 iteration count")

    password_bytes = _password_bytes(password)
    salt_bytes = secrets.token_bytes(PASSWORD_SALT_BYTES) if salt is None else salt
    if not isinstance(salt_bytes, bytes) or len(salt_bytes) < PASSWORD_SALT_BYTES:
        raise ValueError("Password salt is too short")

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_bytes,
        salt_bytes,
        iterations,
        dklen=PASSWORD_DIGEST_BYTES,
    )
    return "$".join(
        (
            PASSWORD_HASH_SCHEME,
            str(iterations),
            _encode_component(salt_bytes),
            _encode_component(digest),
        )
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        scheme, iteration_text, salt_text, digest_text = encoded_hash.split("$")
        if scheme != PASSWORD_HASH_SCHEME:
            return False
        iterations = int(iteration_text)
        if iterations < PASSWORD_HASH_ITERATIONS or iterations > _MAX_ITERATIONS:
            return False
        salt = _decode_component(salt_text)
        expected = _decode_component(digest_text)
        if len(salt) < PASSWORD_SALT_BYTES or len(expected) != PASSWORD_DIGEST_BYTES:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            _password_bytes(password),
            salt,
            iterations,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError):
        return False


def needs_rehash(encoded_hash: str) -> bool:
    try:
        scheme, iteration_text, salt_text, digest_text = encoded_hash.split("$")
        return not (
            scheme == PASSWORD_HASH_SCHEME
            and int(iteration_text) == PASSWORD_HASH_ITERATIONS
            and len(_decode_component(salt_text)) >= PASSWORD_SALT_BYTES
            and len(_decode_component(digest_text)) == PASSWORD_DIGEST_BYTES
        )
    except (AttributeError, TypeError, ValueError):
        return True
