from app.database import execute_query, execute_non_query
from typing import Optional, List, Dict

class SiparisRepository:
    def create_siparis(self, masa_id: int, siparis_kodu: str, toplam_tutar: float, odeme_durumu: str, siparis_durumu: str) -> Optional[int]:
        query = """
            INSERT INTO Siparisler (masa_id, siparis_kodu, toplam_tutar, odeme_durumu, siparis_durumu)
            VALUES (?, ?, ?, ?, ?)
        """
        siparis_id = execute_non_query(query, (masa_id, siparis_kodu, toplam_tutar, odeme_durumu, siparis_durumu))
        if not siparis_id:
            s_row = execute_query("SELECT id FROM Siparisler WHERE siparis_kodu = ?", (siparis_kodu,), fetch_one=True)
            if s_row:
                siparis_id = s_row['id']
        return siparis_id

    def create_siparis_detay(self, siparis_id: int, urun_id: int, adet: int, birim_fiyat: float, urun_notu: str, ara_toplam: float):
        query = """
            INSERT INTO SiparisDetaylari (siparis_id, urun_id, adet, birim_fiyat, urun_notu, ara_toplam)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_non_query(query, (siparis_id, urun_id, adet, birim_fiyat, urun_notu, ara_toplam))

    def get_all(self, durum: Optional[str] = None, masa_id: Optional[int] = None):
        if masa_id:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.masa_id = ? ORDER BY s.id DESC"
            return execute_query(query, (masa_id,)) or []
        elif durum:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.siparis_durumu = ? ORDER BY s.id DESC"
            return execute_query(query, (durum,)) or []
        else:
            query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id ORDER BY s.id DESC"
            return execute_query(query) or []

    def get_by_id(self, siparis_id: int):
        query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.id = ?"
        return execute_query(query, (siparis_id,), fetch_one=True)

    def get_siparis_detaylari(self, siparis_id: int):
        query = "SELECT sd.*, u.urun_adi FROM SiparisDetaylari sd JOIN Urunler u ON sd.urun_id = u.id WHERE sd.siparis_id = ?"
        return execute_query(query, (siparis_id,)) or []

    def get_active_by_masa_id(self, masa_id: int):
        query = """
            SELECT TOP 1 s.*, m.masa_no 
            FROM Siparisler s 
            JOIN Masalar m ON s.masa_id = m.id 
            WHERE s.masa_id = ? AND s.siparis_durumu != 'teslim_edildi' 
            ORDER BY s.id DESC
        """
        return execute_query(query, (masa_id,), fetch_one=True)

    def update_durum(self, siparis_id: int, yeni_durum: str, garson_adi: Optional[str] = None):
        if garson_adi:
            execute_non_query(
                "UPDATE Siparisler SET siparis_durumu = ?, garson_adi = ? WHERE id = ?",
                (yeni_durum, garson_adi, siparis_id)
            )
        else:
            execute_non_query(
                "UPDATE Siparisler SET siparis_durumu = ? WHERE id = ?",
                (yeni_durum, siparis_id)
            )

    def update_odeme_and_durum(self, siparis_id: int, odeme_durumu: str, siparis_durumu: str, garson_adi: Optional[str] = None):
        if garson_adi:
            execute_non_query(
                "UPDATE Siparisler SET odeme_durumu = ?, siparis_durumu = ?, garson_adi = ? WHERE id = ?",
                (odeme_durumu, siparis_durumu, garson_adi, siparis_id)
            )
        else:
            execute_non_query(
                "UPDATE Siparisler SET odeme_durumu = ?, siparis_durumu = ? WHERE id = ?",
                (odeme_durumu, siparis_durumu, siparis_id)
            )

    def get_active_count_for_masa(self, masa_id: int) -> int:
        query = "SELECT COUNT(*) as cnt FROM Siparisler WHERE masa_id = ? AND siparis_durumu IN ('nakit_bekliyor', 'odendi_mutfakta', 'hazirlaniyor', 'hazir', 'garson_onayi_bekliyor', 'garson_onayladi_mutfakta')"
        res = execute_query(query, (masa_id,), fetch_one=True)
        return res['cnt'] if res else 0

    def clear_active_orders_for_masa(self, masa_id: int):
        query = "UPDATE Siparisler SET siparis_durumu = 'teslim_edildi' WHERE masa_id = ? AND siparis_durumu IN ('garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir')"
        execute_non_query(query, (masa_id,))
