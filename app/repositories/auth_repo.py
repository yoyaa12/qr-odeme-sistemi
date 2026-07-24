from app.database import execute_query

class AuthRepository:
    def get_user_by_credentials(self, kullanici_adi: str, sifre_hash: str):
        query = "SELECT id, kullanici_adi, rol FROM Kullanicilar WHERE kullanici_adi = ? AND sifre_hash = ?"
        return execute_query(query, (kullanici_adi, sifre_hash), fetch_one=True)
    
    def get_garson_by_pin(self, pin_code: str):
        query = "SELECT id, kullanici_adi AS garson_adi, rol FROM Kullanicilar WHERE sifre_hash = ?"
        return execute_query(query, (pin_code,), fetch_one=True)

    def get_all_garsonlar(self):
        query = "SELECT id, kullanici_adi AS garson_adi FROM Kullanicilar WHERE rol = 'garson' ORDER BY kullanici_adi ASC"
        return execute_query(query) or []
