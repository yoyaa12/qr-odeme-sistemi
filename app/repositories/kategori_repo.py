"""`Kategoriler` tablosunun veri erişimi.

Satır şeması: `app/schemas/catalog/entity.py` -> `KategoriEntity`.
"""

from typing import List, Optional

from fastapi import Depends

from app.database import DatabaseSession, get_db
from app.schemas.catalog.entity import KategoriEntity


class KategoriRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_all_active(self) -> List[KategoriEntity]:
        """Yalnızca `aktif_mi = 1` olan kategoriler; pasifler menüde görünmez."""
        query = "SELECT id, kategori_adi, gorsel_url, aktif_mi FROM Kategoriler WHERE aktif_mi = 1 ORDER BY id ASC"
        return self.db.execute_query(query) or []

    def create(self, kategori_adi: str) -> Optional[int]:
        """Kategoriyi oluşturur ve yeni satırın id'sini döner."""
        query = "INSERT INTO Kategoriler (kategori_adi, aktif_mi) VALUES (?, 1)"
        return self.db.execute_non_query(query, (kategori_adi,))

    def get_by_id(self, kategori_id: int) -> Optional[KategoriEntity]:
        """Tek kategorinin tam satırı; `aktif_mi` durumuna bakmaz."""
        return self.db.execute_query(
            "SELECT id, kategori_adi, aktif_mi, gorsel_url FROM Kategoriler WHERE id = ?",
            (kategori_id,),
            fetch_one=True,
        )

    def get_inactive(self) -> List[KategoriEntity]:
        """Menüden kaldırılmış kategoriler."""
        query = """
            SELECT id, kategori_adi, gorsel_url, aktif_mi
            FROM Kategoriler WHERE aktif_mi = 0 ORDER BY kategori_adi ASC
        """
        return self.db.execute_query(query) or []

    def activate(self, kategori_id: int) -> int:
        """Kaldırılmış kategoriyi menüye geri getirir; etkilenen satır sayısını döner."""
        return self.db.execute_update(
            "UPDATE Kategoriler SET aktif_mi = 1 WHERE id = ? AND aktif_mi = 0",
            (kategori_id,),
        )

    def deactivate(self, kategori_id: int) -> int:
        """Kategoriyi menüden kaldırır ve etkilenen satır sayısını döner.

        Satır SİLİNMEZ, `aktif_mi = 0` yapılır. `Urunler.kategori_id` bu satıra
        `ON DELETE CASCADE` ile bağlı: gerçek bir `DELETE`, kategorideki bütün
        ürünleri hiçbir uyarı vermeden silerdi. Ürünlerden biri daha önce
        sipariş edilmişse cascade `SiparisDetaylari` FK'sına çarpar ve işlem
        HTTP 500 ile düşerdi. Yani aynı düğme bazen sessizce veri siliyor,
        bazen hata veriyordu.

        Uygulama artık hiçbir yerde `DELETE FROM Kategoriler` çalıştırmadığı
        için cascade tetiklenemez.

        Dönüş 0 ise böyle bir kategori yoktu; çağıran bunu 404'e çevirir.
        """
        return self.db.execute_update(
            "UPDATE Kategoriler SET aktif_mi = 0 WHERE id = ? AND aktif_mi = 1",
            (kategori_id,),
        )
