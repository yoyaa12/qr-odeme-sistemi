"""`Masalar` tablosunun veri erişimi.

Satır şeması: `app/schemas/tables/entity.py` -> `MasaEntity`.
"""

from typing import List, Optional

from fastapi import Depends

from app.core.totp_service import generate_secret_key
from app.database import DatabaseSession, get_db
from app.enums import TableStatus
from app.schemas.tables.entity import MasaEntity


class MasaRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_all(self) -> List[MasaEntity]:
        """Masaları `totp_secret` dahil okur.

        Sır burada taşınır çünkü kasa ekranı tüm masaların dinamik QR'ını tek
        çağrıda üretir. Dışarı çıkmaması yanıt modelinin sorumluluğudur:
        `MasaResponse` böyle bir alan tanımlamaz.
        """
        query = "SELECT id, masa_no, qr_kodu, durum, totp_secret FROM Masalar ORDER BY id ASC"
        return self.db.execute_query(query) or []

    def get_by_id(self, masa_id: int) -> Optional[MasaEntity]:
        query = "SELECT * FROM Masalar WHERE id = ?"
        return self.db.execute_query(query, (masa_id,), fetch_one=True)

    def create(self, masa_no: str, qr_kodu: str) -> Optional[int]:
        """Masayı oluşturur ve yeni satırın id'sini döner."""
        secret = generate_secret_key()
        query = "INSERT INTO Masalar (masa_no, qr_kodu, durum, totp_secret) VALUES (?, ?, ?, ?)"
        return self.db.execute_non_query(
            query, (masa_no, qr_kodu, TableStatus.EMPTY.value, secret)
        )

    def update_totp_secret(self, masa_id: int, secret: str) -> None:
        self.db.execute_non_query(
            "UPDATE Masalar SET totp_secret = ? WHERE id = ?", (secret, masa_id)
        )

    def update_durum(self, masa_id: int, durum: str) -> None:
        query = "UPDATE Masalar SET durum = ? WHERE id = ?"
        self.db.execute_non_query(query, (durum, masa_id))

        # Masa kapatılıyorsa (durum = 'bos') Güvenlik için Secret Rotation yap
        # Eski masa oturumuna ait HİÇBİR QR kod bir daha çalışamaz!
        if durum == TableStatus.EMPTY.value:
            new_secret = generate_secret_key()
            self.update_totp_secret(masa_id, new_secret)

    def delete(self, masa_id: int) -> None:
        self.db.execute_non_query("DELETE FROM Masalar WHERE id = ?", (masa_id,))
