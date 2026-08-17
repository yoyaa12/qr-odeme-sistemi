"""Small, strict HS256 JWT implementation for short-lived staff access tokens."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any

from app.auth.models import TokenClaims
from app.enums import TokenType, UserRole


AUTH_SECRET_ENV = "AUTH_SECRET_KEY"
AUTH_TOKEN_TTL_ENV = "AUTH_STAFF_TOKEN_TTL_SECONDS"
DEFAULT_STAFF_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60
MIN_STAFF_TOKEN_TTL_SECONDS = 60
MAX_STAFF_TOKEN_TTL_SECONDS = 365 * 24 * 60 * 60
TOKEN_ISSUER = "qr-restoran-api"
TOKEN_AUDIENCE = "qr-restoran-staff"
TOKEN_TYPE_HEADERS = {
    TokenType.STAFF: "staff+jwt",
    TokenType.CUSTOMER_SESSION: "customer-session+jwt",
}
TOKEN_TYPE_AUDIENCES = {
    TokenType.STAFF: TOKEN_AUDIENCE,
    TokenType.CUSTOMER_SESSION: "qr-restoran-customer-session",
}
_JWT_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class AuthConfigurationError(RuntimeError):
    pass


class TokenValidationError(ValueError):
    pass


class ExpiredTokenError(TokenValidationError):
    pass


class WrongTokenTypeError(TokenValidationError):
    pass


def get_auth_secret() -> bytes:
    raw_secret = os.getenv(AUTH_SECRET_ENV)
    if not raw_secret:
        raise AuthConfigurationError(f"{AUTH_SECRET_ENV} is not configured")
    encoded = raw_secret.encode("utf-8")
    if len(encoded) < 32:
        raise AuthConfigurationError(f"{AUTH_SECRET_ENV} must contain at least 32 bytes")
    return encoded


def get_staff_token_ttl_seconds() -> int:
    raw_value = os.getenv(AUTH_TOKEN_TTL_ENV)
    if raw_value is None:
        return DEFAULT_STAFF_TOKEN_TTL_SECONDS
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise AuthConfigurationError(f"{AUTH_TOKEN_TTL_ENV} must be an integer") from exc
    if value < MIN_STAFF_TOKEN_TTL_SECONDS or value > MAX_STAFF_TOKEN_TTL_SECONDS:
        raise AuthConfigurationError(
            f"{AUTH_TOKEN_TTL_ENV} must be between "
            f"{MIN_STAFF_TOKEN_TTL_SECONDS} and {MAX_STAFF_TOKEN_TTL_SECONDS}"
        )
    return value


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str, *, max_bytes: int) -> bytes:
    if not value or len(value) > max_bytes * 2 or not _JWT_SEGMENT_RE.fullmatch(value):
        raise TokenValidationError("Malformed token")
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise TokenValidationError("Malformed token") from exc
    if len(decoded) > max_bytes:
        raise TokenValidationError("Malformed token")
    if _b64url_encode(decoded) != value:
        raise TokenValidationError("Malformed token")
    return decoded


def _json_object(value: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TokenValidationError("Malformed token") from exc
    if not isinstance(decoded, dict):
        raise TokenValidationError("Malformed token")
    return decoded


def _integer_claim(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TokenValidationError("Invalid token claims")
    return value


def create_access_token(
    subject: int,
    role: UserRole,
    *,
    token_type: TokenType = TokenType.STAFF,
    now: int | None = None,
    expires_in: int | None = None,
    secret: bytes | None = None,
) -> str:
    if not isinstance(subject, int) or isinstance(subject, bool) or subject <= 0:
        raise ValueError("Token subject must be a positive integer")
    if not isinstance(role, UserRole):
        role = UserRole(role)
    if not isinstance(token_type, TokenType):
        token_type = TokenType(token_type)

    issued_at = int(time.time()) if now is None else int(now)
    ttl = get_staff_token_ttl_seconds() if expires_in is None else int(expires_in)
    if ttl < MIN_STAFF_TOKEN_TTL_SECONDS or ttl > MAX_STAFF_TOKEN_TTL_SECONDS:
        raise ValueError("Token lifetime is outside the allowed range")

    header = {"alg": "HS256", "typ": TOKEN_TYPE_HEADERS[token_type]}
    payload = {
        "sub": str(subject),
        "role": role.value,
        "type": token_type.value,
        "iat": issued_at,
        "exp": issued_at + ttl,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_TYPE_AUDIENCES[token_type],
    }
    header_segment = _b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_segment = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signing_secret = get_auth_secret() if secret is None else secret
    if len(signing_secret) < 32:
        raise AuthConfigurationError("Signing secret must contain at least 32 bytes")
    signature = hmac.new(signing_secret, signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


def decode_access_token(
    token: str,
    *,
    expected_type: TokenType = TokenType.STAFF,
    now: int | None = None,
    secret: bytes | None = None,
) -> TokenClaims:
    if not isinstance(token, str) or len(token) > 4_096:
        raise TokenValidationError("Malformed token")
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenValidationError("Malformed token")
    header_segment, payload_segment, signature_segment = parts
    header = _json_object(_b64url_decode(header_segment, max_bytes=512))
    payload = _json_object(_b64url_decode(payload_segment, max_bytes=2_048))
    signature = _b64url_decode(signature_segment, max_bytes=64)

    if header.get("alg") != "HS256" or header.get("typ") not in TOKEN_TYPE_HEADERS.values():
        raise TokenValidationError("Unsupported token header")

    signing_secret = get_auth_secret() if secret is None else secret
    if len(signing_secret) < 32:
        raise AuthConfigurationError("Signing secret must contain at least 32 bytes")
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(signing_secret, signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenValidationError("Invalid token signature")

    if payload.get("iss") != TOKEN_ISSUER:
        raise TokenValidationError("Invalid token claims")

    issued_at = _integer_claim(payload, "iat")
    expires_at = _integer_claim(payload, "exp")
    current_time = int(time.time()) if now is None else int(now)
    if (
        issued_at > current_time + 60
        or expires_at <= issued_at
        or expires_at - issued_at > MAX_STAFF_TOKEN_TTL_SECONDS
    ):
        raise TokenValidationError("Invalid token claims")
    if expires_at <= current_time:
        raise ExpiredTokenError("Token has expired")

    subject_text = payload.get("sub")
    if not isinstance(subject_text, str) or not subject_text.isdigit():
        raise TokenValidationError("Invalid token claims")
    subject = int(subject_text)
    if subject <= 0:
        raise TokenValidationError("Invalid token claims")

    try:
        role = UserRole(payload.get("role"))
        token_type = TokenType(payload.get("type"))
        expected = expected_type if isinstance(expected_type, TokenType) else TokenType(expected_type)
    except (TypeError, ValueError) as exc:
        raise TokenValidationError("Invalid token claims") from exc
    if (
        header.get("typ") != TOKEN_TYPE_HEADERS[token_type]
        or payload.get("aud") != TOKEN_TYPE_AUDIENCES[token_type]
    ):
        raise TokenValidationError("Invalid token profile")
    if token_type is not expected:
        raise WrongTokenTypeError("Wrong token type")

    return TokenClaims(
        subject=subject,
        role=role,
        token_type=token_type,
        issued_at=issued_at,
        expires_at=expires_at,
    )
