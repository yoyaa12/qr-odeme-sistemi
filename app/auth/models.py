from dataclasses import dataclass

from app.enums import TokenType, UserRole


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: int
    role: UserRole
    token_type: TokenType
    issued_at: int
    expires_at: int


@dataclass(frozen=True, slots=True)
class StaffPrincipal:
    user_id: int
    username: str
    role: UserRole


@dataclass(frozen=True, slots=True)
class StaffLoginResult:
    principal: StaffPrincipal
    access_token: str
    expires_in: int
