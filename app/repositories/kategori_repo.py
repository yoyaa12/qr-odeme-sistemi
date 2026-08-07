from fastapi import Depends
from app.database import DatabaseSession, get_db

class KategoriRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_all_active(self):
        query = "SELECT id, kategori_adi, gorsel_url, aktif_mi FROM Kategoriler WHERE aktif_mi = 1 ORDER BY id ASC"
        return self.db.execute_query(query) or []

    def create(self, kategori_adi: str):
        query = "INSERT INTO Kategoriler (kategori_adi, aktif_mi) VALUES (?, 1)"
        return self.db.execute_non_query(query, (kategori_adi,))

    def delete(self, kategori_id: int):
        query = "DELETE FROM Kategoriler WHERE id = ?"
        self.db.execute_non_query(query, (kategori_id,))

