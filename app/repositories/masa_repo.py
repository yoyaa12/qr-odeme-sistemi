from fastapi import Depends
from app.database import DatabaseSession, get_db
from app.core.totp_service import generate_secret_key
from app.enums import TableStatus

class MasaRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_all(self):
        query = "SELECT id, masa_no, qr_kodu, durum, totp_secret FROM Masalar ORDER BY id ASC"
        return self.db.execute_query(query) or []

    def get_by_id(self, masa_id: int):
        query = "SELECT * FROM Masalar WHERE id = ?"
        return self.db.execute_query(query, (masa_id,), fetch_one=True)

    def create(self, masa_no: str, qr_kodu: str):
        secret = generate_secret_key()
        query = "INSERT INTO Masalar (masa_no, qr_kodu, durum, totp_secret) VALUES (?, ?, ?, ?)"
        return self.db.execute_non_query(
            query, (masa_no, qr_kodu, TableStatus.EMPTY.value, secret)
        )

    def update_totp_secret(self, masa_id: int, secret: str):
        query = "UPDATE Masalar SET totp_secret = ? WHERE id = ?"
        self.db.execute_non_query(query, (secret, masa_id))

    def update_durum(self, masa_id: int, durum: str):
        query = "UPDATE Masalar SET durum = ? WHERE id = ?"
        self.db.execute_non_query(query, (durum, masa_id))
        
        # Masa kapatılıyorsa (durum = 'bos') Güvenlik için Secret Rotation yap
        # Eski masa oturumuna ait HİÇBİR QR kod bir daha çalışamaz!
        if durum == TableStatus.EMPTY.value:
            new_secret = generate_secret_key()
            self.update_totp_secret(masa_id, new_secret)

    def delete(self, masa_id: int):
        self.db.execute_non_query("DELETE FROM Masalar WHERE id = ?", (masa_id,))

