from fastapi import Depends
from typing import List, Optional
from app.repositories.masa_repo import MasaRepository
from app.schemas.schemas import MasaEkleModel, MasaResponse, QRDogrulamaResponse
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

    def verify_dynamic_qr_token(self, masa_id: int, token: str) -> bool:
        masa = self.repo.get_by_id(masa_id)
        if not masa:
            return False
            
        totp_secret = masa.get("totp_secret")
        if totp_secret and verify_dynamic_token(masa_id, totp_secret, token):
            return True

        from app.services.siparis_service import TABLE_MOVES_MAP
        for from_id, to_id in TABLE_MOVES_MAP.items():
            if to_id == masa_id:
                from_masa = self.repo.get_by_id(from_id)
                if from_masa and from_masa.get("totp_secret"):
                    if verify_dynamic_token(from_id, from_masa.get("totp_secret"), token):
                        return True
        return False

    def verify_dynamic_qr_with_device(self, masa_id: int, token: str, device_id: Optional[str] = None) -> QRDogrulamaResponse:
        """
        Müşteri QR okuttuğunda cihaz + TOTP birleşik doğrulaması yapar.
        1. Cihaz masada kayıtlıysa (DOLU masa) → doğrudan geçir
        2. Değilse → normal TOTP doğrulaması yap
        """
        # 1. Cihaz masada zaten kayıtlı mı?
        if device_id:
            from app.services.siparis_service import SiparisService
            from app.repositories.siparis_repo import SiparisRepository
            from app.repositories.urun_repo import UrunRepository
            from app.repositories.auth_repo import AuthRepository
            
            siparis_repo = SiparisRepository(db=self.repo.db)
            aktif_siparisler = siparis_repo.get_all_active_by_masa_id(masa_id)
            
            if aktif_siparisler:
                if any(s.get('device_id') == device_id for s in aktif_siparisler):
                    return QRDogrulamaResponse(
                        valid=True,
                        message="Cihazınız masada kayıtlı, doğrudan giriş yapıldı.",
                        masa_id=masa_id
                    )

        # 2. Normal TOTP doğrulaması
        is_valid = self.verify_dynamic_qr_token(masa_id, token)
        if is_valid:
            return QRDogrulamaResponse(
                valid=True,
                message="Dinamik QR başarıyla doğrulandı.",
                masa_id=masa_id
            )
        
        return QRDogrulamaResponse(
            valid=False,
            message="Geçersiz veya süresi dolmuş QR kodu! Lütfen masadaki güncel QR kodunu tekrar okutunuz."
        )

