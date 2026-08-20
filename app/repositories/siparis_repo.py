"""`Siparisler`, `SiparisDetaylari` ve `MasaTahsilatlari` tablolarının veri erişimi.

Satır şemaları:
    `app/schemas/orders/entity.py` -> `SiparisEntity`, `SiparisWithMasaEntity`,
                                      `SiparisDetayWithUrunEntity`, `UndeliveredUrunAdetRow`
    `app/schemas/tables/entity.py` -> `MasaTahsilatEntity`
"""

from typing import List, Optional

from fastapi import Depends

from app.database import DatabaseSession, get_db
from app.enums import OrderStatus, PaymentStatus
from app.schemas.orders.dto import PricedOrderLine
from app.schemas.orders.entity import (
    SiparisDetayWithUrunEntity,
    SiparisWithMasaEntity,
    UndeliveredUrunAdetRow,
)


class SiparisRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def create_siparis(
        self,
        masa_id: int,
        siparis_kodu: str,
        toplam_tutar: float,
        odeme_durumu: str,
        siparis_durumu: str,
        device_id: Optional[str] = None,
        customer_session_id: Optional[int] = None,
    ) -> Optional[int]:
        """Sipariş başlığını yazar.

        ``device_id`` istemciden gelir ve taklit edilebilir; yalnızca cihaz
        yasaklama gibi kaba işlemler için tutulur. ``customer_session_id`` ise
        doğrulanmış oturumdan gelir: "bu siparişi masadaki hangi oturum verdi"
        sorusunun güvenilebilir tek cevabı budur. Personel tarafından oluşan
        kayıtlarda NULL kalır.
        """
        query = """
            INSERT INTO Siparisler (masa_id, siparis_kodu, toplam_tutar, odeme_durumu, siparis_durumu, device_id, customer_session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        siparis_id = self.db.execute_non_query(
            query,
            (masa_id, siparis_kodu, toplam_tutar, odeme_durumu, siparis_durumu, device_id, customer_session_id),
        )
        if not siparis_id:
            s_row = self.db.execute_query("SELECT id FROM Siparisler WHERE siparis_kodu = ?", (siparis_kodu,), fetch_one=True)
            if s_row:
                siparis_id = s_row['id']
        return siparis_id

    def create_siparis_detay(
        self,
        siparis_id: int,
        urun_id: int,
        adet: int,
        birim_fiyat: float,
        urun_notu: str,
        ara_toplam: float,
    ) -> None:
        query = """
            INSERT INTO SiparisDetaylari (siparis_id, urun_id, adet, birim_fiyat, urun_notu, ara_toplam)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self.db.execute_non_query(query, (siparis_id, urun_id, adet, birim_fiyat, urun_notu, ara_toplam))

    def get_all(
        self, durum: Optional[str] = None, masa_id: Optional[int] = None
    ) -> List[SiparisWithMasaEntity]:
        if masa_id:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.masa_id = ? ORDER BY s.id DESC"
            return self.db.execute_query(query, (masa_id,)) or []
        elif durum:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.siparis_durumu = ? ORDER BY s.id DESC"
            return self.db.execute_query(query, (durum,)) or []
        else:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id ORDER BY s.id DESC"
            return self.db.execute_query(query) or []

    def get_by_id(self, siparis_id: int) -> Optional[SiparisWithMasaEntity]:
        query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.id = ?"
        return self.db.execute_query(query, (siparis_id,), fetch_one=True)

    def get_siparis_detaylari(self, siparis_id: int) -> List[SiparisDetayWithUrunEntity]:
        query = "SELECT sd.*, u.urun_adi FROM SiparisDetaylari sd JOIN Urunler u ON sd.urun_id = u.id WHERE sd.siparis_id = ?"
        return self.db.execute_query(query, (siparis_id,)) or []

    def get_all_active_by_masa_id(self, masa_id: int) -> List[SiparisWithMasaEntity]:
        """Masanın kapanmamış siparişleri (iptal ve kapatılmış olanlar hariç)."""
        query = """
            SELECT s.*, m.masa_no
            FROM Siparisler s
            JOIN Masalar m ON s.masa_id = m.id
            WHERE s.masa_id = ? AND s.siparis_durumu NOT IN (?, ?)
            ORDER BY s.id ASC
        """
        return self.db.execute_query(
            query,
            (masa_id, OrderStatus.CANCELLED.value, OrderStatus.PAID_CLOSED.value),
        ) or []

    def update_durum(
        self, siparis_id: int, yeni_durum: str, garson_adi: Optional[str] = None
    ) -> None:
        if garson_adi:
            self.db.execute_non_query(
                "UPDATE Siparisler SET siparis_durumu = ?, garson_adi = ? WHERE id = ?",
                (yeni_durum, garson_adi, siparis_id)
            )
        else:
            self.db.execute_non_query(
                "UPDATE Siparisler SET siparis_durumu = ? WHERE id = ?",
                (yeni_durum, siparis_id)
            )

    def update_odeme_and_durum(
        self,
        siparis_id: int,
        odeme_durumu: str,
        siparis_durumu: str,
        garson_adi: Optional[str] = None,
    ) -> None:
        if garson_adi:
            self.db.execute_non_query(
                "UPDATE Siparisler SET odeme_durumu = ?, siparis_durumu = ?, garson_adi = ? WHERE id = ?",
                (odeme_durumu, siparis_durumu, garson_adi, siparis_id)
            )
        else:
            self.db.execute_non_query(
                "UPDATE Siparisler SET odeme_durumu = ?, siparis_durumu = ? WHERE id = ?",
                (odeme_durumu, siparis_durumu, siparis_id)
            )

    def get_active_count_for_masa(self, masa_id: int) -> int:
        active_statuses = (
            OrderStatus.CASH_PENDING.value,
            OrderStatus.PAID_IN_KITCHEN.value,
            OrderStatus.PREPARING.value,
            OrderStatus.READY.value,
            OrderStatus.WAITER_APPROVAL_PENDING.value,
            OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
        )
        placeholders = ", ".join("?" for _ in active_statuses)
        query = f"SELECT COUNT(*) as cnt FROM Siparisler WHERE masa_id = ? AND siparis_durumu IN ({placeholders})"
        res = self.db.execute_query(query, (masa_id, *active_statuses), fetch_one=True)
        return res['cnt'] if res else 0

    def get_unpaid_count_for_masa(self, masa_id: int) -> int:
        query = "SELECT COUNT(*) as cnt FROM Siparisler WHERE masa_id = ? AND odeme_durumu != ? AND siparis_durumu NOT IN (?, ?)"
        res = self.db.execute_query(
            query,
            (
                masa_id,
                PaymentStatus.PAID.value,
                OrderStatus.CANCELLED.value,
                OrderStatus.PAID_CLOSED.value,
            ),
            fetch_one=True,
        )
        return res['cnt'] if res else 0

    def get_undelivered_details_for_masa(self, masa_id: int) -> List[UndeliveredUrunAdetRow]:
        """Masada teslim edilmemiş kalemlerin ürün bazında toplam adedi.

        Stok sipariş anında düşülür: bu bir rezervasyondur, tüketim değil. Ürün
        gerçekten `teslim_edildi` olduğunda rezervasyon tüketime dönüşür.
        Adisyon kapanırken hâlâ teslim edilmemiş olan kalemler ise hiç
        servis edilmemiştir ve stoğa geri dönmelidir.

        `iptal` ve `odendi_kapatildi` bilinçli olarak dışarıda: iptal kendi
        iadesini zaten yapmıştır, `odendi_kapatildi` ise bu iadenin daha önce
        çalıştığı anlamına gelir. Böylece aynı masa iki kez kapatılsa da stok
        yalnızca bir kez geri verilir.
        """
        query = """
            SELECT sd.urun_id, SUM(sd.adet) AS adet
            FROM SiparisDetaylari sd
            JOIN Siparisler s ON sd.siparis_id = s.id
            WHERE s.masa_id = ? AND s.siparis_durumu NOT IN (?, ?, ?)
            GROUP BY sd.urun_id
        """
        return self.db.execute_query(
            query,
            (
                masa_id,
                OrderStatus.DELIVERED.value,
                OrderStatus.CANCELLED.value,
                OrderStatus.PAID_CLOSED.value,
            ),
        ) or []

    def clear_active_orders_for_masa(self, masa_id: int) -> None:
        query = "UPDATE Siparisler SET siparis_durumu = ?, odeme_durumu = ? WHERE masa_id = ? AND siparis_durumu NOT IN (?, ?)"
        self.db.execute_non_query(
            query,
            (
                OrderStatus.PAID_CLOSED.value,
                PaymentStatus.PAID.value,
                masa_id,
                OrderStatus.CANCELLED.value,
                OrderStatus.PAID_CLOSED.value,
            ),
        )

    def replace_siparis_items(
        self,
        siparis_id: int,
        toplam_tutar: float,
        priced_items: List[PricedOrderLine],
        garson_adi: Optional[str] = None,
    ) -> None:
        """Replace an order's lines with server-priced ones.

        ``priced_items`` carries unit prices and line totals already computed by
        the service against the product catalogue. The repository deliberately
        accepts no request model, so a client-supplied price cannot reach the
        database through this path.
        """
        if garson_adi:
            self.db.execute_non_query("UPDATE Siparisler SET toplam_tutar = ?, garson_adi = ? WHERE id = ?", (toplam_tutar, garson_adi, siparis_id))
        else:
            self.db.execute_non_query("UPDATE Siparisler SET toplam_tutar = ? WHERE id = ?", (toplam_tutar, siparis_id))

        self.db.execute_non_query("DELETE FROM SiparisDetaylari WHERE siparis_id = ?", (siparis_id,))
        for line in priced_items:
            self.create_siparis_detay(
                siparis_id,
                line["urun_id"],
                line["adet"],
                line["birim_fiyat"],
                line.get("urun_notu") or "",
                line["ara_toplam"],
            )

    def get_movable_detail_rows(self, masa_id: int) -> List[SiparisDetayWithUrunEntity]:
        """Masanın taşınabilir sipariş kalemleri, satır kimliğiyle birlikte.

        Kapsam bilinçli olarak `move_orders_between_masalar` ile aynı: iptal ve
        kapatılmış siparişler hariç her şey. Böylece "tümünü taşı" ile "seçili
        kalemleri taşı" aynı kümede çalışır ve ikisi birbirinden sapmaz.
        """
        query = """
            SELECT sd.id, sd.siparis_id, sd.urun_id, sd.adet, sd.birim_fiyat,
                   sd.urun_notu, sd.ara_toplam, u.urun_adi
            FROM SiparisDetaylari sd
            JOIN Siparisler s ON sd.siparis_id = s.id
            JOIN Urunler u ON sd.urun_id = u.id
            WHERE s.masa_id = ? AND s.siparis_durumu NOT IN (?, ?)
            ORDER BY sd.siparis_id ASC, sd.id ASC
        """
        return self.db.execute_query(
            query,
            (masa_id, OrderStatus.CANCELLED.value, OrderStatus.PAID_CLOSED.value),
        ) or []

    def reassign_detaylar_to_siparis(self, detay_ids: List[int], hedef_siparis_id: int) -> None:
        """Seçili kalemleri başka bir sipariş başlığının altına taşır."""
        if not detay_ids:
            return
        placeholders = ", ".join("?" for _ in detay_ids)
        query = f"UPDATE SiparisDetaylari SET siparis_id = ? WHERE id IN ({placeholders})"
        self.db.execute_non_query(query, (hedef_siparis_id, *detay_ids))

    def move_single_order_to_masa(self, siparis_id: int, to_masa_id: int) -> None:
        self.db.execute_non_query(
            "UPDATE Siparisler SET masa_id = ? WHERE id = ?", (to_masa_id, siparis_id)
        )

    def sync_siparis_total(self, siparis_id: int) -> None:
        """Başlık toplamını kalemlerinden yeniden hesaplar.

        Kalem taşındıktan sonra iki başlığın da toplamı değişir. Tutarı
        istemciden almak yerine veritabanındaki satırlardan türetmek, kasadaki
        rakamın her zaman gerçekten duran kalemlerle uyuşmasını garanti eder.
        """
        query = """
            UPDATE Siparisler
            SET toplam_tutar = ISNULL(
                (SELECT SUM(ara_toplam) FROM SiparisDetaylari WHERE siparis_id = ?), 0
            )
            WHERE id = ?
        """
        self.db.execute_non_query(query, (siparis_id, siparis_id))

    def move_orders_between_masalar(self, from_masa_id: int, to_masa_id: int) -> None:
        query = """
            UPDATE Siparisler
            SET masa_id = ?
            WHERE masa_id = ? AND siparis_durumu NOT IN (?, ?)
        """
        self.db.execute_non_query(
            query,
            (
                to_masa_id,
                from_masa_id,
                OrderStatus.CANCELLED.value,
                OrderStatus.PAID_CLOSED.value,
            ),
        )

    def add_masa_tahsilat(self, masa_id: int, tutar: float, odeme_yontemi: str) -> None:
        """Kısmi ödemeyi açık (`is_closed = 0`) satır olarak yazar."""
        query = """
            INSERT INTO MasaTahsilatlari (masa_id, tutar, odeme_yontemi, is_closed)
            VALUES (?, ?, ?, 0)
        """
        self.db.execute_non_query(query, (masa_id, tutar, odeme_yontemi))

    def get_masa_tahsilat_toplami(self, masa_id: int) -> float:
        query = "SELECT SUM(tutar) as toplam FROM MasaTahsilatlari WHERE masa_id = ? AND is_closed = 0"
        res = self.db.execute_query(query, (masa_id,), fetch_one=True)
        return float(res['toplam']) if res and res['toplam'] else 0.0

    def close_tahsilatlar_for_masa(self, masa_id: int) -> None:
        """Adisyon kapanınca tahsilat satırları silinmez, kapatılır."""
        query = "UPDATE MasaTahsilatlari SET is_closed = 1 WHERE masa_id = ? AND is_closed = 0"
        self.db.execute_non_query(query, (masa_id,))
