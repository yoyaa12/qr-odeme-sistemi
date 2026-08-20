"""`Kullanicilar`, `CustomerSessions` ve `BannedDevices` tablolarının veri erişimi.

Her metodun dönüş tipi `app/schemas/auth/entity.py` içindeki satır şemasına
işaret eder: sorgunun hangi kolonları getirdiğini görmek için SQL metnini
okumak gerekmez, entity'ye bakmak yeterlidir.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import Depends

from app.database import DatabaseSession, get_db
from app.enums import UserRole
from app.schemas.auth.entity import (
    BannedDeviceEntity,
    CustomerSessionEntity,
    GarsonCredentialsEntity,
    GarsonListEntity,
    KullaniciEntity,
    StaffIdentityEntity,
)


class AuthRepository:
    def __init__(self, db: DatabaseSession = Depends(get_db)):
        self.db = db

    def get_user_by_username(self, kullanici_adi: str) -> Optional[KullaniciEntity]:
        """Personel girişi için kullanıcıyı parola hash'iyle birlikte okur."""
        query = """
            SELECT id, kullanici_adi, rol, sifre_hash
            FROM Kullanicilar
            WHERE kullanici_adi = ?
        """
        return self.db.execute_query(query, (kullanici_adi,), fetch_one=True)

    def get_staff_by_id(self, user_id: int) -> Optional[StaffIdentityEntity]:
        """Token doğrulandıktan sonra kullanıcının hâlâ var olduğunu teyit eder.

        Parola hash'i bilinçli olarak seçilmez: bu yol yalnızca kimliği ve rolü
        tazelemek içindir.
        """
        query = """
            SELECT id, kullanici_adi, rol
            FROM Kullanicilar
            WHERE id = ?
        """
        return self.db.execute_query(query, (user_id,), fetch_one=True)

    def get_garson_credentials(self) -> List[GarsonCredentialsEntity]:
        """PIN doğrulaması için tüm garsonları hash'leriyle birlikte okur.

        Garson PIN'i kullanıcı adı olmadan girildiği için hangi kayda ait
        olduğu önceden bilinemez; servis katmanı adayları sırayla dener
        (`AuthService.verify_garson_pin`). Bu yüzden `sifre_hash` burada
        taşınmak zorundadır ve bu nesne asla HTTP yanıtına ulaşmaz.
        """
        query = """
            SELECT id, kullanici_adi AS garson_adi, rol, sifre_hash
            FROM Kullanicilar
            WHERE rol = ?
            ORDER BY id ASC
        """
        return self.db.execute_query(query, (UserRole.WAITER.value,)) or []

    def get_all_garsonlar(self) -> List[GarsonListEntity]:
        """Garson seçim listesi; parola hash'i taşımaz."""
        query = "SELECT id, kullanici_adi AS garson_adi FROM Kullanicilar WHERE rol = ? ORDER BY kullanici_adi ASC"
        return self.db.execute_query(query, (UserRole.WAITER.value,)) or []

    def get_banned_device(self, device_id: str) -> Optional[BannedDeviceEntity]:
        return self.db.execute_query("SELECT id FROM BannedDevices WHERE device_id = ?", (device_id,), fetch_one=True)

    def ban_device(self, device_id: str) -> None:
        self.db.execute_non_query("INSERT INTO BannedDevices (device_id) VALUES (?)", (device_id,))

    def create_customer_session(
        self,
        session_token_hash: str,
        masa_id: int,
        expires_at: datetime,
        device_id: Optional[str] = None,
    ) -> None:
        """Yalnızca token'ın SHA-256 hash'i saklanır, ham token değil."""
        query = """
            INSERT INTO CustomerSessions (session_token_hash, masa_id, device_id, expires_at, is_active)
            VALUES (?, ?, ?, ?, 1)
        """
        self.db.execute_non_query(query, (session_token_hash, masa_id, device_id, expires_at))

    def get_active_customer_session(self, session_token_hash: str) -> Optional[CustomerSessionEntity]:
        query = """
            SELECT id, masa_id, device_id, expires_at
            FROM CustomerSessions
            WHERE session_token_hash = ? AND is_active = 1 AND expires_at > GETDATE()
        """
        return self.db.execute_query(query, (session_token_hash,), fetch_one=True)

    def touch_customer_session(self, session_token_hash: str, expires_at: datetime) -> None:
        """Kayan oturum ömrü: kullanılan oturumun bitiş zamanını ileri atar."""
        query = """
            UPDATE CustomerSessions
            SET expires_at = ?
            WHERE session_token_hash = ? AND is_active = 1
        """
        self.db.execute_non_query(query, (expires_at, session_token_hash))

    def revoke_customer_session(self, session_token_hash: str) -> None:
        query = "UPDATE CustomerSessions SET is_active = 0 WHERE session_token_hash = ?"
        self.db.execute_non_query(query, (session_token_hash,))

    def revoke_all_sessions_for_masa(self, masa_id: int) -> None:
        """Adisyon kapanınca masadaki tüm müşteri oturumlarını geçersiz kılar."""
        query = "UPDATE CustomerSessions SET is_active = 0 WHERE masa_id = ?"
        self.db.execute_non_query(query, (masa_id,))
