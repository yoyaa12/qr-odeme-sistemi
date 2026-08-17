from typing import Optional
from fastapi import Depends
from app.database import DatabaseSession, get_db

class UrunRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_all(self, kategori_id: Optional[int] = None):
        if kategori_id:
            query = "SELECT u.*, k.kategori_adi FROM Urunler u JOIN Kategoriler k ON u.kategori_id = k.id WHERE u.kategori_id = ? AND u.aktif_mi = 1"
            return self.db.execute_query(query, (kategori_id,)) or []
        else:
            query = "SELECT u.*, k.kategori_adi FROM Urunler u JOIN Kategoriler k ON u.kategori_id = k.id WHERE u.aktif_mi = 1"
            return self.db.execute_query(query) or []

    def get_by_id(self, urun_id: int):
        query = "SELECT * FROM Urunler WHERE id = ?"
        return self.db.execute_query(query, (urun_id,), fetch_one=True)

    def create(self, kategori_id: int, urun_adi: str, aciklama: str, fiyat: float, gorsel_url: str, stok_miktari: int):
        query = "INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)"
        return self.db.execute_non_query(query, (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari))

    def update(self, urun_id: int, updates: dict):
        for key, value in updates.items():
            if value is not None:
                self.db.execute_non_query(f"UPDATE Urunler SET {key} = ? WHERE id = ?", (value, urun_id))

    def update_stock(self, urun_id: int, decrement: int):
        query = "UPDATE Urunler SET stok_miktari = stok_miktari - ? WHERE id = ? AND stok_miktari >= ?"
        self.db.execute_non_query(query, (decrement, urun_id, decrement))

    def restore_stock(self, urun_id: int, increment: int):
        """Return quantities to stock when an order line shrinks or is removed."""
        query = "UPDATE Urunler SET stok_miktari = stok_miktari + ? WHERE id = ?"
        self.db.execute_non_query(query, (increment, urun_id))

    def delete(self, urun_id: int):
        self.db.execute_non_query("DELETE FROM Urunler WHERE id = ?", (urun_id,))
