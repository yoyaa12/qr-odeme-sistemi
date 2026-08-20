import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status

from app.auth.models import StaffLoginResult, StaffPrincipal
from app.auth.passwords import hash_password, verify_password
from app.auth.rate_limit import ProcessLocalLoginRateLimiter, staff_login_limiter
from app.auth.tokens import (
    AuthConfigurationError,
    create_access_token,
    get_auth_secret,
    get_staff_token_ttl_seconds,
)
from app.enums import UserRole
from app.repositories.auth_repo import AuthRepository
from app.schemas.auth import GarsonPinVerifyModel, KullaniciResponse, LoginModel
from app.schemas.common import GenelBasariliResponse
from typing import List


_DUMMY_PASSWORD_HASH = hash_password(
    "dummy-password-used-only-for-timing-equalization",
    salt=b"\x00" * 16,
)

# Müşteri QR oturumunun ömrü. Kayan pencere: her kullanımda yeniden bu kadar
# ileri atılır, böylece masada oturan müşterinin oturumu yemek ortasında bitmez.
CUSTOMER_SESSION_TTL_MINUTES = 90
# Oturum bu kadar eskimeden yenileme yazılmaz; aksi halde her istek bir UPDATE
# üretirdi.
_SESSION_REFRESH_AFTER_MINUTES = 15

class AuthService:
    def __init__(self, repo: AuthRepository = Depends()):
        self.repo = repo

    @staticmethod
    def _rate_key(kind: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
        return f"{kind}:{digest}"

    @staticmethod
    def _ensure_auth_configured() -> None:
        try:
            get_auth_secret()
            get_staff_token_ttl_seconds()
        except AuthConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kimlik doğrulama yapılandırması hazır değil.",
            ) from exc

    @staticmethod
    def _check_rate_limit(
        limiter: ProcessLocalLoginRateLimiter,
        keys: tuple[str, ...],
    ) -> None:
        decision = limiter.check(keys)
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Çok fazla başarısız giriş denemesi. Lütfen daha sonra tekrar deneyin.",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

    @staticmethod
    def _principal_from_record(user: dict, *, username_field: str) -> StaffPrincipal:
        try:
            return StaffPrincipal(
                user_id=int(user["id"]),
                username=str(user[username_field]),
                role=UserRole(user["rol"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hatalı personel bilgileri.",
            ) from exc

    @staticmethod
    def _issue_token(principal: StaffPrincipal) -> StaffLoginResult:
        try:
            ttl = get_staff_token_ttl_seconds()
            token = create_access_token(
                principal.user_id,
                principal.role,
                expires_in=ttl,
            )
        except AuthConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kimlik doğrulama yapılandırması hazır değil.",
            ) from exc
        return StaffLoginResult(principal=principal, access_token=token, expires_in=ttl)

    def login(
        self,
        data: LoginModel,
        client_host: str,
        *,
        limiter: ProcessLocalLoginRateLimiter = staff_login_limiter,
    ) -> StaffLoginResult:
        self._ensure_auth_configured()
        username = data.kullanici_adi.strip()
        keys = (
            self._rate_key("staff-login-ip", client_host),
            self._rate_key("staff-login-account", username.casefold()),
        )
        self._check_rate_limit(limiter, keys)

        user = self.repo.get_user_by_username(username) if username else None
        encoded_hash = user.get("sifre_hash") if user else _DUMMY_PASSWORD_HASH
        credentials_valid = verify_password(data.sifre, encoded_hash)
        if not user or not credentials_valid:
            limiter.record_failure(keys)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hatalı personel bilgileri.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        principal = self._principal_from_record(user, username_field="kullanici_adi")
        # A successful account login clears that account's failures, but not
        # the source-IP bucket. Otherwise one known credential could reset the
        # IP throttle before attacking other accounts.
        limiter.record_success(keys[1:])
        return self._issue_token(principal)

    def verify_garson_pin(
        self,
        data: GarsonPinVerifyModel,
        client_host: str,
        *,
        limiter: ProcessLocalLoginRateLimiter = staff_login_limiter,
    ) -> StaffLoginResult:
        self._ensure_auth_configured()
        pin = data.pin_code.strip()
        if len(pin) != 6 or not pin.isascii() or not pin.isdigit():
            raise HTTPException(status_code=400, detail="PIN kodu 6 haneli rakamlardan oluşmalıdır!")

        keys = (self._rate_key("waiter-pin-ip", client_host),)
        self._check_rate_limit(limiter, keys)
        matches = [
            garson
            for garson in self.repo.get_garson_credentials()
            if verify_password(pin, garson.get("sifre_hash", ""))
        ]
        if len(matches) != 1:
            limiter.record_failure(keys)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hatalı garson PIN kodu.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        principal = self._principal_from_record(matches[0], username_field="garson_adi")
        if principal.role is not UserRole.WAITER:
            limiter.record_failure(keys)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hatalı garson PIN kodu.",
            )
        # PIN login has no account key until verification has succeeded. Keep
        # prior source-IP failures so success cannot reset the shared throttle.
        limiter.record_success(())
        return self._issue_token(principal)

    def get_garsonlar(self) -> List[KullaniciResponse]:
        garsonlar = self.repo.get_all_garsonlar()
        return [KullaniciResponse(**g) for g in garsonlar] if garsonlar else []

    def ban_device(self, device_id: str) -> GenelBasariliResponse:
        existing = self.repo.get_banned_device(device_id)
        if existing:
            return GenelBasariliResponse(status="success", message="Cihaz zaten yasaklı.")

        self.repo.ban_device(device_id)
        return GenelBasariliResponse(status="success", message="Cihaz başarıyla yasaklandı.")

    def create_customer_session(self, masa_id: int, device_id: Optional[str] = None) -> str:
        # Generate a random 64-character hex token
        raw_token = secrets.token_hex(32)
        # Only the hash is stored, so a database read cannot reveal live tokens.
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        expires_at = datetime.now() + timedelta(minutes=CUSTOMER_SESSION_TTL_MINUTES)

        self.repo.create_customer_session(token_hash, masa_id, expires_at, device_id)
        return raw_token

    def verify_customer_session(self, raw_token: str) -> Optional[dict]:
        if not raw_token:
            return None

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        session = self.repo.get_active_customer_session(token_hash)
        if not session:
            return None

        self._extend_session_if_stale(token_hash, session)
        return session

    def _extend_session_if_stale(self, token_hash: str, session: dict) -> None:
        """Kayan oturum ömrü.

        Masada oturmaya devam eden müşteri, oturumunu sadece kullanarak canlı
        tutar; masadan kalkıp giden birinin oturumu ise yenilenmediği için kendi
        kendine söner. Sabit ömürde ikisi ayırt edilemiyordu.

        Yazma yalnızca oturum `_SESSION_REFRESH_AFTER_MINUTES` kadar
        eskidiğinde yapılır, yoksa her istek bir UPDATE üretirdi. Sürücüden
        `datetime` dışında bir değer gelirse (test sahteleri, beklenmedik tip)
        yenileme sessizce atlanır: oturum yine de sabit ömrüyle geçerlidir.
        """
        expires_at = session.get("expires_at")
        if not isinstance(expires_at, datetime):
            return

        full_ttl = timedelta(minutes=CUSTOMER_SESSION_TTL_MINUTES)
        remaining = expires_at - datetime.now()
        if remaining > full_ttl - timedelta(minutes=_SESSION_REFRESH_AFTER_MINUTES):
            return

        new_expiry = datetime.now() + full_ttl
        self.repo.touch_customer_session(token_hash, new_expiry)
        session["expires_at"] = new_expiry
