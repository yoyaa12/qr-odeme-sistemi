import hashlib
from typing import List, Optional

from fastapi import Depends, HTTPException, status

from app.auth.rate_limit import ProcessLocalLoginRateLimiter, qr_verify_limiter
from app.repositories.auth_repo import AuthRepository
from app.repositories.masa_repo import MasaRepository
from app.repositories.siparis_repo import SiparisRepository
from app.services.auth_service import AuthService
from app.services.siparis_service import TABLE_MOVES_MAP
from app.schemas.tables import MasaEkleModel, MasaResponse, QRDogrulamaResponse
from app.database import db_transaction
from app.core.totp_service import generate_secret_key, generate_dynamic_token, get_seconds_remaining, verify_dynamic_token
from app.core.socket_manager import get_browsing_tables

class MasaService:
    def __init__(self, repo: MasaRepository = Depends()):
        self.repo = repo

    def get_masalar(self) -> List[MasaResponse]:
        masalar = self.repo.get_all()
        return [MasaResponse(**m) for m in masalar] if masalar else []

    def get_masalar_with_browsing(self) -> List[MasaResponse]:
        """Masaları browsing (göz atma) durumu ile birlikte döner."""
        masalar = self.get_masalar()
        browsing = get_browsing_tables()
        for m in masalar:
            m.secim_durumu = browsing.get(m.id)
        return masalar
    
    def add_masa(self, data: MasaEkleModel):
        qr_code = f"MASA_{data.masa_no.upper().replace(' ', '_')}"
        with db_transaction():
            inserted_id = self.repo.create(data.masa_no, qr_code)
        return inserted_id

    def delete_masa(self, masa_id: int):
        with db_transaction():
            self.repo.delete(masa_id)

    def get_or_create_totp_secret(self, masa_id: int) -> str:
        masa = self.repo.get_by_id(masa_id)
        if not masa:
            return ""
        
        totp_secret = masa.get("totp_secret")
        if not totp_secret:
            totp_secret = generate_secret_key()
            with db_transaction():
                self.repo.update_totp_secret(masa_id, totp_secret)
        return totp_secret

    def get_dynamic_qr_info(self, masa_id: int) -> dict:
        masa = self.repo.get_by_id(masa_id)
        if not masa:
            return {}
            
        totp_secret = self.get_or_create_totp_secret(masa_id)
        token = generate_dynamic_token(totp_secret)
        remaining = get_seconds_remaining()
        
        return {
            "masa_id": masa_id,
            "masa_no": masa.get("masa_no"),
            "token": token,
            "remaining_seconds": remaining,
            "qr_url": f"/m/{masa_id}?token={token}"
        }

    def get_all_dynamic_qrs(self) -> dict:
        masalar = self.repo.get_all()
        remaining = get_seconds_remaining()
        result = {}
        for m in masalar:
            m_id = m['id']
            secret = m.get('totp_secret')
            if not secret:
                secret = generate_secret_key()
                with db_transaction():
                    self.repo.update_totp_secret(m_id, secret)
            token = generate_dynamic_token(secret)
            result[m_id] = {
                "masa_id": m_id,
                "masa_no": m.get("masa_no"),
                "token": token,
                "remaining_seconds": remaining,
                "qr_url": f"/m/{m_id}?token={token}"
            }
        return result

    def verify_dynamic_qr_token(self, masa_id: int, token: str, mark_as_used: bool = False) -> bool:
        masa = self.repo.get_by_id(masa_id)
        if not masa:
            return False
            
        totp_secret = masa.get("totp_secret")
        if totp_secret and verify_dynamic_token(masa_id, totp_secret, token, mark_as_used=mark_as_used):
            return True

        for from_id, to_id in TABLE_MOVES_MAP.items():
            if to_id == masa_id:
                from_masa = self.repo.get_by_id(from_id)
                if from_masa and from_masa.get("totp_secret"):
                    if verify_dynamic_token(from_id, from_masa.get("totp_secret"), token, mark_as_used=mark_as_used):
                        return True
        return False

    def _issue_customer_session(self, masa_id: int, device_id: Optional[str]) -> str:
        auth_repo = AuthRepository(db=self.repo.db)
        return AuthService(repo=auth_repo).create_customer_session(masa_id, device_id)

    def verify_dynamic_qr_with_device(
        self,
        masa_id: int,
        token: str,
        device_id: Optional[str] = None,
        *,
        client_host: str = "unknown",
        limiter: ProcessLocalLoginRateLimiter = qr_verify_limiter,
    ) -> QRDogrulamaResponse:
        """
        Müşteri QR okuttuğunda cihaz + TOTP birleşik doğrulaması yapar.
        1. Cihaz masada kayıtlıysa (DOLU masa) → doğrudan geçir
        2. Değilse → normal TOTP doğrulaması yap

        Kimlik doğrulaması gerektirmediği için her başarısız deneme kaynak IP ve
        masa bazlı sayaçlara işlenir; eşiği aşan istekler 429 alır.
        """
        rate_keys = (
            f"qr-verify-ip:{hashlib.sha256(client_host.encode('utf-8', 'replace')).hexdigest()}",
            f"qr-verify-masa:{masa_id}",
        )
        decision = limiter.check(rate_keys)
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Çok fazla başarısız QR doğrulama denemesi. Lütfen biraz sonra tekrar deneyin.",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

        # 1. Cihaz masada zaten kayıtlı mı?
        if device_id:
            siparis_repo = SiparisRepository(db=self.repo.db)
            aktif_siparisler = siparis_repo.get_all_active_by_masa_id(masa_id)

            if aktif_siparisler:
                if any(s.get('device_id') == device_id for s in aktif_siparisler):
                    limiter.record_success(rate_keys)
                    return QRDogrulamaResponse(
                        valid=True,
                        message="Cihazınız masada kayıtlı, doğrudan giriş yapıldı.",
                        masa_id=masa_id,
                        session_token=self._issue_customer_session(masa_id, device_id),
                    )

        # 2. Normal TOTP doğrulaması
        if self.verify_dynamic_qr_token(masa_id, token):
            limiter.record_success(rate_keys)
            return QRDogrulamaResponse(
                valid=True,
                message="Dinamik QR başarıyla doğrulandı.",
                masa_id=masa_id,
                session_token=self._issue_customer_session(masa_id, device_id),
            )

        limiter.record_failure(rate_keys)
        return QRDogrulamaResponse(
            valid=False,
            message="Geçersiz veya süresi dolmuş QR kodu! Lütfen masadaki güncel QR kodunu tekrar okutunuz."
        )
