from fastapi import Depends, HTTPException
from app.repositories.auth_repo import AuthRepository
from app.schemas.schemas import LoginModel, GarsonPinVerifyModel

class AuthService:
    def __init__(self, repo: AuthRepository = Depends()):
        self.repo = repo

    def login(self, data: LoginModel):
        user = self.repo.get_user_by_credentials(data.kullanici_adi, data.sifre)
        if not user:
            raise HTTPException(status_code=401, detail="Hatalı giriş!")
        return user

    def verify_garson_pin(self, data: GarsonPinVerifyModel):
        pin = data.pin_code.strip()
        if len(pin) != 6 or not pin.isdigit():
            raise HTTPException(status_code=400, detail="PIN kodu 6 haneli rakamlardan oluşmalıdır!")
        
        garson = self.repo.get_garson_by_pin(pin)
        if not garson:
            raise HTTPException(status_code=401, detail="Hatalı 6 Haneli Garson PIN Kodu!")
        return garson

    def get_garsonlar(self):
        return self.repo.get_all_garsonlar()
