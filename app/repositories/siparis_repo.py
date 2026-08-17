from typing import Optional, List, Dict
from fastapi import Depends
from app.database import DatabaseSession, get_db
from app.enums import OrderStatus, PaymentStatus

class SiparisRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def create_siparis(self, masa_id: int, siparis_kodu: str, toplam_tutar: float, odeme_durumu: str, siparis_durumu: str, device_id: Optional[str] = None) -> Optional[int]:
        query = """
            INSERT INTO Siparisler (masa_id, siparis_kodu, toplam_tutar, odeme_durumu, siparis_durumu, device_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        siparis_id = self.db.execute_non_query(query, (masa_id, siparis_kodu, toplam_tutar, odeme_durumu, siparis_durumu, device_id))
        if not siparis_id:
            s_row = self.db.execute_query("SELECT id FROM Siparisler WHERE siparis_kodu = ?", (siparis_kodu,), fetch_one=True)
            if s_row:
                siparis_id = s_row['id']
        return siparis_id

    def create_siparis_detay(self, siparis_id: int, urun_id: int, adet: int, birim_fiyat: float, urun_notu: str, ara_toplam: float):
        query = """
            INSERT INTO SiparisDetaylari (siparis_id, urun_id, adet, birim_fiyat, urun_notu, ara_toplam)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self.db.execute_non_query(query, (siparis_id, urun_id, adet, birim_fiyat, urun_notu, ara_toplam))

    def get_all(self, durum: Optional[str] = None, masa_id: Optional[int] = None):
        if masa_id:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.masa_id = ? ORDER BY s.id DESC"
            return self.db.execute_query(query, (masa_id,)) or []
        elif durum:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.siparis_durumu = ? ORDER BY s.id DESC"
            return self.db.execute_query(query, (durum,)) or []
        else:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id ORDER BY s.id DESC"
            return self.db.execute_query(query) or []

    def get_by_id(self, siparis_id: int):
        query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.id = ?"
        return self.db.execute_query(query, (siparis_id,), fetch_one=True)

    def get_siparis_detaylari(self, siparis_id: int):
        query = "SELECT sd.*, u.urun_adi FROM SiparisDetaylari sd JOIN Urunler u ON sd.urun_id = u.id WHERE sd.siparis_id = ?"
        return self.db.execute_query(query, (siparis_id,)) or []

    def get_all_active_by_masa_id(self, masa_id: int):
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

    def update_durum(self, siparis_id: int, yeni_durum: str, garson_adi: Optional[str] = None):
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

    def update_odeme_and_durum(self, siparis_id: int, odeme_durumu: str, siparis_durumu: str, garson_adi: Optional[str] = None):
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

    def clear_active_orders_for_masa(self, masa_id: int):
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
        priced_items: List[Dict],
        garson_adi: Optional[str] = None,
    ):
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

    def move_orders_between_masalar(self, from_masa_id: int, to_masa_id: int):
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

    def add_masa_tahsilat(self, masa_id: int, tutar: float, odeme_yontemi: str):
        query = """
            INSERT INTO MasaTahsilatlari (masa_id, tutar, odeme_yontemi, is_closed)
            VALUES (?, ?, ?, 0)
        """
        self.db.execute_non_query(query, (masa_id, tutar, odeme_yontemi))

    def get_masa_tahsilat_toplami(self, masa_id: int) -> float:
        query = "SELECT SUM(tutar) as toplam FROM MasaTahsilatlari WHERE masa_id = ? AND is_closed = 0"
        res = self.db.execute_query(query, (masa_id,), fetch_one=True)
        return float(res['toplam']) if res and res['toplam'] else 0.0

    def close_tahsilatlar_for_masa(self, masa_id: int):
        query = "UPDATE MasaTahsilatlari SET is_closed = 1 WHERE masa_id = ? AND is_closed = 0"
        self.db.execute_non_query(query, (masa_id,))
