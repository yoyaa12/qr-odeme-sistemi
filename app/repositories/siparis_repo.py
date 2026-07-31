from typing import Optional, List, Dict
from fastapi import Depends
from app.database import DatabaseSession, get_db

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

    def get_active_by_masa_id(self, masa_id: int):
        query = """
            SELECT TOP 1 s.*, m.masa_no 
            FROM Siparisler s 
            JOIN Masalar m ON s.masa_id = m.id 
            WHERE s.masa_id = ? AND s.siparis_durumu != 'teslim_edildi' 
            ORDER BY s.id DESC
        """
        return self.db.execute_query(query, (masa_id,), fetch_one=True)

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
        query = "SELECT COUNT(*) as cnt FROM Siparisler WHERE masa_id = ? AND siparis_durumu IN ('nakit_bekliyor', 'odendi_mutfakta', 'hazirlaniyor', 'hazir', 'garson_onayi_bekliyor', 'garson_onayladi_mutfakta')"
        res = self.db.execute_query(query, (masa_id,), fetch_one=True)
        return res['cnt'] if res else 0

    def get_unpaid_count_for_masa(self, masa_id: int) -> int:
        query = "SELECT COUNT(*) as cnt FROM Siparisler WHERE masa_id = ? AND odeme_durumu != 'odendi' AND siparis_durumu != 'iptal'"
        res = self.db.execute_query(query, (masa_id,), fetch_one=True)
        return res['cnt'] if res else 0

    def clear_active_orders_for_masa(self, masa_id: int):
        query = "UPDATE Siparisler SET siparis_durumu = 'teslim_edildi', odeme_durumu = 'odendi' WHERE masa_id = ? AND siparis_durumu IN ('garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir', 'teslim_edildi')"
        self.db.execute_non_query(query, (masa_id,))

    def update_siparis_items(self, siparis_id: int, toplam_tutar: float, urunler: list, garson_adi: Optional[str] = None):
        if garson_adi:
            self.db.execute_non_query("UPDATE Siparisler SET toplam_tutar = ?, garson_adi = ? WHERE id = ?", (toplam_tutar, garson_adi, siparis_id))
        else:
            self.db.execute_non_query("UPDATE Siparisler SET toplam_tutar = ? WHERE id = ?", (toplam_tutar, siparis_id))
        
        self.db.execute_non_query("DELETE FROM SiparisDetaylari WHERE siparis_id = ?", (siparis_id,))
        for item in urunler:
            ara_toplam = item.adet * item.birim_fiyat
            self.create_siparis_detay(siparis_id, item.urun_id, item.adet, item.birim_fiyat, item.urun_notu or "", ara_toplam)

    def move_orders_between_masalar(self, from_masa_id: int, to_masa_id: int):
        query = """
            UPDATE Siparisler 
            SET masa_id = ? 
            WHERE masa_id = ? AND odeme_durumu != 'odendi' AND siparis_durumu != 'iptal'
        """
        self.db.execute_non_query(query, (to_masa_id, from_masa_id))
