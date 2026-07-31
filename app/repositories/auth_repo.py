from fastapi import Depends
from app.database import DatabaseSession, get_db

class AuthRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_user_by_credentials(self, kullanici_adi: str, sifre_hash: str):
        query = "SELECT id, kullanici_adi, rol FROM Kullanicilar WHERE kullanici_adi = ? AND sifre_hash = ?"
        return self.db.execute_query(query, (kullanici_adi, sifre_hash), fetch_one=True)
    
    def get_garson_by_pin(self, pin_code: str):
        query = "SELECT id, kullanici_adi AS garson_adi, rol FROM Kullanicilar WHERE sifre_hash = ?"
        return self.db.execute_query(query, (pin_code,), fetch_one=True)

    def get_all_garsonlar(self):
        query = "SELECT id, kullanici_adi AS garson_adi FROM Kullanicilar WHERE rol = 'garson' ORDER BY kullanici_adi ASC"
        return self.db.execute_query(query) or []

    def get_banned_device(self, device_id: str):
        return self.db.execute_query("SELECT id FROM BannedDevices WHERE device_id = ?", (device_id,), fetch_one=True)

    def ban_device(self, device_id: str):
        self.db.execute_non_query("INSERT INTO BannedDevices (device_id) VALUES (?)", (device_id,))
