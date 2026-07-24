from app.database import execute_query, execute_non_query

class KategoriRepository:
    def get_all_active(self):
        query = "SELECT id, kategori_adi, aktif_mi FROM Kategoriler WHERE aktif_mi = 1 ORDER BY id ASC"
        return execute_query(query) or []

    def create(self, kategori_adi: str):
        query = "INSERT INTO Kategoriler (kategori_adi, aktif_mi) VALUES (?, 1)"
        return execute_non_query(query, (kategori_adi,))

    def delete(self, kategori_id: int):
        query = "DELETE FROM Kategoriler WHERE id = ?"
        execute_non_query(query, (kategori_id,))
