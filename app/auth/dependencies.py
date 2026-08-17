from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import StaffPrincipal
from app.auth.tokens import (
    AuthConfigurationError,
    TokenValidationError,
    decode_access_token,
)
from app.enums import TokenType, UserRole
from app.repositories.auth_repo import AuthRepository
from app.services.auth_service import AuthService


staff_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description="Kısa ömürlü, imzalı STAFF access token",
    scheme_name="StaffBearer",
)


def _unauthorized(detail: str = "Geçerli personel tokenı gerekli.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_staff(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(staff_bearer),
    ],
    repo: Annotated[AuthRepository, Depends()],
) -> StaffPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        claims = decode_access_token(
            credentials.credentials,
            expected_type=TokenType.STAFF,
        )
    except AuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kimlik doğrulama yapılandırması hazır değil.",
        ) from exc
    except TokenValidationError as exc:
        raise _unauthorized("Personel tokenı geçersiz veya süresi dolmuş.") from exc

    user = repo.get_staff_by_id(claims.subject)
    if not user:
        raise _unauthorized("Personel tokenı artık geçerli değil.")
    try:
        database_role = UserRole(user["rol"])
        username = str(user["kullanici_adi"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _unauthorized("Personel tokenı artık geçerli değil.") from exc
    if database_role is not claims.role:
        raise _unauthorized("Personel tokenı artık geçerli değil.")

    return StaffPrincipal(
        user_id=claims.subject,
        username=username,
        role=database_role,
    )


def get_optional_staff(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(staff_bearer),
    ],
    repo: Annotated[AuthRepository, Depends()],
) -> StaffPrincipal | None:
    """Return the staff principal when one is present, otherwise None.

    For endpoints that are legitimately public but expose extra operational
    detail to signed-in staff. An invalid token yields None rather than an
    error, so a stale staff token cannot lock a customer out of the menu.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        return get_current_staff(credentials, repo)
    except HTTPException:
        return None


def require_roles(*allowed_roles: UserRole) -> Callable[..., StaffPrincipal]:
    if not allowed_roles:
        raise ValueError("At least one role is required")
    allowed = frozenset(
        role if isinstance(role, UserRole) else UserRole(role)
        for role in allowed_roles
    )

    def role_guard(
        principal: Annotated[StaffPrincipal, Depends(get_current_staff)],
    ) -> StaffPrincipal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için personel rolünüz yetkili değil.",
            )
        return principal

    return role_guard

customer_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="Hex",
    description="Müşteri QR oturum token'ı",
    scheme_name="CustomerBearer",
)

def get_current_customer(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(customer_bearer),
    ],
    repo: Annotated[AuthRepository, Depends()],
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçerli müşteri oturum token'ı gerekli.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    service = AuthService(repo)
    session = service.verify_customer_session(credentials.credentials)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Müşteri oturumu geçersiz veya süresi dolmuş. Lütfen QR kodu tekrar okutun.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return session

def get_current_user_or_customer(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(staff_bearer),
    ],
    repo: Annotated[AuthRepository, Depends()],
) -> StaffPrincipal | dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçerli bir oturum token'ı gerekli.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    # A standard JWT has three parts separated by dots
    if len(token.split(".")) == 3:
        return get_current_staff(credentials, repo)
    else:
        return get_current_customer(credentials, repo)
