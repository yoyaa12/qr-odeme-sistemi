"""Staff authentication primitives.

This package deliberately contains no database schema or migration logic.
"""

from app.auth.models import StaffLoginResult, StaffPrincipal, TokenClaims
from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.tokens import create_access_token, decode_access_token

__all__ = [
    "StaffLoginResult",
    "StaffPrincipal",
    "TokenClaims",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "needs_rehash",
    "verify_password",
]
