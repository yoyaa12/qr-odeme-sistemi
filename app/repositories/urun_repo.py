"""`Urunler` tablosunun veri erişimi.

Satır şeması: `app/schemas/catalog/entity.py` -> `UrunEntity` /
`UrunWithKategoriEntity`.
"""

from typing import List, Optional

from fastapi import Depends

from app.database import DatabaseSession, get_db
from app.schemas.catalog.entity import UrunEntity, UrunWithKategoriEntity


class UrunRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_all(self, kategori_id: Optional[int] = None) -> List[UrunWithKategoriEntity]:
        """Aktif ürünler, kategori adıyla birlikte.

        `k.aktif_mi = 1` koşulu bilinçli: pasifleştirilmiş bir kategorinin ürünü
        menüde görünürse, kategori listesinde karşılığı olmayan bir ürün ortaya
        çıkar. Servis katmanı kategoriyi kapatırken ürünlerini de kapatıyor;
        buradaki koşul o adımın atlandığı durumlar için ikinci savunma hattı.
        """
        if kategori_id:
            query = "SELECT u.*, k.kategori_adi FROM Urunler u JOIN Kategoriler k ON u.kategori_id = k.id WHERE u.kategori_id = ? AND u.aktif_mi = 1 AND k.aktif_mi = 1"
            return self.db.execute_query(query, (kategori_id,)) or []
        else:
            query = "SELECT u.*, k.kategori_adi FROM Urunler u JOIN Kategoriler k ON u.kategori_id = k.id WHERE u.aktif_mi = 1 AND k.aktif_mi = 1"
            return self.db.execute_query(query) or []

    def get_by_id(self, urun_id: int) -> Optional[UrunEntity]:
        """Tek ürünün tam satırı.

        Fiyatlandırma yolu bunu kullanır: `fiyat` ve `aktif_mi` alanları
        istemcinin gönderdiği değerlerin yerine geçer.
        """
        query = "SELECT * FROM Urunler WHERE id = ?"
        return self.db.execute_query(query, (urun_id,), fetch_one=True)

    def create(
        self,
        kategori_id: int,
        urun_adi: str,
        aciklama: str,
        fiyat: float,
        gorsel_url: str,
        stok_miktari: int,
    ) -> Optional[int]:
        """Ürünü oluşturur ve yeni satırın id'sini döner."""
        query = "INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)"
        return self.db.execute_non_query(query, (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari))

    # Güncellemeye açık kolonlar. SET ifadesi çalışma zamanında kurulduğu için
    # kolon adı sorgu metnine gömülmek zorunda; parametreleştirilemez. Bu yüzden
    # ad, SQL'e girmeden ÖNCE bu kümeye karşı doğrulanır. `id` ve `aktif_mi`
    # bilinçli olarak dışarıda: birincisi kimlik, ikincisi menüden kaldırma
    # yolunun (`deactivate` / `activate`) sorumluluğunda.
    GUNCELLENEBILIR_KOLONLAR = frozenset(
        {"kategori_id", "urun_adi", "aciklama", "fiyat", "gorsel_url", "stok_miktari"}
    )

    def update(self, urun_id: int, updates: dict) -> int:
        """Kısmi güncelleme; etkilenen satır sayısını döner.

        `None` değerler atlanır ("bu alana dokunma"). Boş metin atlanmaz: bir
        açıklamayı bilerek boşaltmak geçerli bir işlemdir.

        Tüm alanlar TEK bir UPDATE ile yazılır. Önceden her alan için ayrı bir
        sorgu çalışıyordu; bu hem gereksizdi hem de bir alan yazıldıktan sonra
        hata olursa ürünü yarı güncellenmiş halde bırakabiliyordu.

        Dönüş 0 ise böyle bir ürün yoktu; çağıran bunu 404'e çevirir.
        """
        atamalar = [(kolon, deger) for kolon, deger in updates.items() if deger is not None]

        bilinmeyen = sorted(k for k, _ in atamalar if k not in self.GUNCELLENEBILIR_KOLONLAR)
        if bilinmeyen:
            raise ValueError(f"Guncellenemeyecek kolon(lar): {', '.join(bilinmeyen)}")

        if not atamalar:
            return 0

        set_ifadesi = ", ".join(f"{kolon} = ?" for kolon, _ in atamalar)
        parametreler = tuple(deger for _, deger in atamalar) + (urun_id,)
        return self.db.execute_update(
            f"UPDATE Urunler SET {set_ifadesi} WHERE id = ?", parametreler
        )

    def update_stock(self, urun_id: int, decrement: int) -> int:
        """Stoğu atomik olarak düşürür ve etkilenen satır sayısını döner.

        `0` dönmesi, araya giren başka bir siparişin stoğu bu isteğin altına
        indirdiği anlamına gelir. Çağıran bunu sessizce geçemez: koşul
        tutmadığında sorgu hiçbir şey yapmaz, yani sipariş stoktan düşülmeden
        kabul edilmiş olur.
        """
        query = "UPDATE Urunler SET stok_miktari = stok_miktari - ? WHERE id = ? AND stok_miktari >= ?"
        return self.db.execute_update(query, (decrement, urun_id, decrement))

    def restore_stock(self, urun_id: int, increment: int) -> None:
        """Return quantities to stock when an order line shrinks or is removed."""
        query = "UPDATE Urunler SET stok_miktari = stok_miktari + ? WHERE id = ?"
        self.db.execute_non_query(query, (increment, urun_id))

    def deactivate(self, urun_id: int) -> int:
        """Ürünü menüden kaldırır ve etkilenen satır sayısını döner.

        Satır SİLİNMEZ, `aktif_mi = 0` yapılır. İki nedenle:

        1. `SiparisDetaylari.urun_id` bu satıra FK ile bağlı ve FK kuralı
           `NO_ACTION`. Bir kez sipariş edilmiş ürünü `DELETE` etmek
           `IntegrityError` fırlatır ve uca HTTP 500 olarak yansırdı — yani
           satılmış hiçbir ürün menüden kaldırılamıyordu.
        2. Satır silinseydi geçmiş adisyonlardaki kalemler hangi ürüne ait
           olduğunu kaybederdi. Kesilmiş bir fiş sonradan değişmemelidir.

        `aktif_mi = 0` olan ürün menüde listelenmez (`get_all`) ve sipariş
        edilemez: `SiparisService._price_items_authoritatively` bu ürünleri
        "satışa kapalıdır" diyerek reddeder.

        Dönüş 0 ise böyle bir ürün yoktu; çağıran bunu 404'e çevirir.
        """
        return self.db.execute_update(
            "UPDATE Urunler SET aktif_mi = 0 WHERE id = ? AND aktif_mi = 1", (urun_id,)
        )

    def get_inactive(self) -> List[UrunWithKategoriEntity]:
        """Menüden kaldırılmış ürünler, kategori adıyla birlikte.

        Kategori JOIN'inde `k.aktif_mi` koşulu YOKTUR: kategorisi de kaldırılmış
        bir ürünün yönetici listesinde görünmesi gerekir, yoksa geri getirmek
        imkânsız olurdu.
        """
        query = """
            SELECT u.*, k.kategori_adi
            FROM Urunler u JOIN Kategoriler k ON u.kategori_id = k.id
            WHERE u.aktif_mi = 0
            ORDER BY k.kategori_adi ASC, u.urun_adi ASC
        """
        return self.db.execute_query(query) or []

    def activate(self, urun_id: int) -> int:
        """Kaldırılmış ürünü menüye geri getirir; etkilenen satır sayısını döner.

        `AND aktif_mi = 0` koşulu, zaten menüde olan bir ürün için 0 döndürür;
        çağıran bunu "geri getirilecek bir şey yok" olarak ayırt eder.
        """
        return self.db.execute_update(
            "UPDATE Urunler SET aktif_mi = 1 WHERE id = ? AND aktif_mi = 0", (urun_id,)
        )

    def count_inactive_by_kategori(self, kategori_id: int) -> int:
        """Bir kategorinin hâlâ kaldırılmış durumdaki ürün sayısı."""
        row = self.db.execute_query(
            "SELECT COUNT(*) AS c FROM Urunler WHERE kategori_id = ? AND aktif_mi = 0",
            (kategori_id,),
            fetch_one=True,
        )
        return row["c"] if row else 0

    def deactivate_by_kategori(self, kategori_id: int) -> int:
        """Bir kategorinin tüm aktif ürünlerini menüden kaldırır.

        Kategori kapatılırken ürünlerinin açıkta kalmaması için gerekir.
        Etkilenen ürün sayısını döner ki kullanıcıya kaç ürünün kaldırıldığı
        söylenebilsin — eski `ON DELETE CASCADE` davranışı bunu sessizce
        yapıyordu.
        """
        return self.db.execute_update(
            "UPDATE Urunler SET aktif_mi = 0 WHERE kategori_id = ? AND aktif_mi = 1",
            (kategori_id,),
        )
