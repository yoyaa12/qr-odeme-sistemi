from fastapi import Depends, HTTPException
from app.repositories.auth_repo import AuthRepository
from app.schemas.schemas import LoginModel, GarsonPinVerifyModel, KullaniciResponse
from typing import List

class AuthService:
    def __init__(self, repo: AuthRepository = Depends()):
        self.repo = repo

    def login(self, data: LoginModel) -> KullaniciResponse:
        user = self.repo.get_user_by_credentials(data.kullanici_adi, data.sifre)
        if not user:
            raise HTTPException(status_code=401, detail="Hatalı giriş!")
        return KullaniciResponse(**user)

    def verify_garson_pin(self, data: GarsonPinVerifyModel) -> KullaniciResponse:
        pin = data.pin_code.strip()
        if len(pin) != 6 or not pin.isdigit():
            raise HTTPException(status_code=400, detail="PIN kodu 6 haneli rakamlardan oluşmalıdır!")
        
        garson = self.repo.get_garson_by_pin(pin)
        if not garson:
            raise HTTPException(status_code=401, detail="Hatalı 6 Haneli Garson PIN Kodu!")
        return KullaniciResponse(**garson)

    def get_garsonlar(self) -> List[KullaniciResponse]:
        garsonlar = self.repo.get_all_garsonlar()
        return [KullaniciResponse(**g) for g in garsonlar] if garsonlar else []

    def ban_device(self, device_id: str):
        existing = self.repo.get_banned_device(device_id)
        if existing:
            return {"status": "success", "message": "Cihaz zaten yasaklı."}
        
        self.repo.ban_device(device_id)
        return {"status": "success", "message": "Cihaz başarıyla yasaklandı."}
