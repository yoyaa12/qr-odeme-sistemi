from fastapi import Depends
from typing import List, Optional
from app.repositories.masa_repo import MasaRepository
from app.schemas.schemas import MasaEkleModel, MasaResponse
from app.database import db_transaction
from app.core.totp_service import generate_secret_key, generate_dynamic_token, get_seconds_remaining, verify_dynamic_token

class MasaService:
    def __init__(self, repo: MasaRepository = Depends()):
        self.repo = repo

    def get_masalar(self) -> List[MasaResponse]:
        masalar = self.repo.get_all()
        return [MasaResponse(**m) for m in masalar] if masalar else []
    
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
        if not totp_secret:
            return False
            
        return verify_dynamic_token(masa_id, totp_secret, token)

