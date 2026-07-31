from fastapi import Depends
from app.database import DatabaseSession, get_db

class MasaRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_all(self):
        query = "SELECT id, masa_no, qr_kodu, durum FROM Masalar ORDER BY id ASC"
        return self.db.execute_query(query) or []

    def get_by_id(self, masa_id: int):
        query = "SELECT * FROM Masalar WHERE id = ?"
        return self.db.execute_query(query, (masa_id,), fetch_one=True)

    def create(self, masa_no: str, qr_kodu: str):
        query = "INSERT INTO Masalar (masa_no, qr_kodu, durum) VALUES (?, ?, 'bos')"
        return self.db.execute_non_query(query, (masa_no, qr_kodu))

    def update_durum(self, masa_id: int, durum: str):
        query = "UPDATE Masalar SET durum = ? WHERE id = ?"
        self.db.execute_non_query(query, (durum, masa_id))

    def delete(self, masa_id: int):
        self.db.execute_non_query("DELETE FROM Masalar WHERE id = ?", (masa_id,))
