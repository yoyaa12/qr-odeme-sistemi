"""`Kullanicilar`, `CustomerSessions` ve `BannedDevices` tablolarının satır şekilleri.

Proje bir ORM kullanmıyor; repository katmanı ham SQL yazıyor ve
`app/database.py` her satırı `dict(zip(columns, row))` ile sözlüğe çeviriyor.
Bu yüzden "entity" burada bir ORM sınıfı değil, **o sözlüğün şeması**:
`TypedDict` satırın hangi kolonları taşıdığını ve tiplerini deklare eder.

Neden `TypedDict` de pydantic `BaseModel` değil:

- Repository'nin döndürdüğü nesne çalışma zamanında yine düz `dict`'tir; hiçbir
  dönüştürme, kopyalama veya doğrulama maliyeti eklenmez.
- Dolayısıyla mevcut davranış birebir korunur — entity katmanı tamamen
  tip düzeyinde bir belgelendirmedir.
- Doğrulama ve dış dünyaya serileştirme zaten `response.py` içindeki pydantic
  modellerinin işi. Entity içeri, response dışarı bakar.

Alanlar 2026-08-20 tarihinde canlı şemadan (`INFORMATION_SCHEMA.COLUMNS`)
doğrulanmıştır. `Optional[...]` işaretli olanlar kolonun NULL kabul ettiğini
gösterir.
"""

from datetime import datetime
from typing import Optional, TypedDict


class KullaniciEntity(TypedDict):
    """`Kullanicilar` tablosunun tam satırı.

    DDL:
        id            int           IDENTITY PRIMARY KEY
        kullanici_adi nvarchar      NOT NULL
        sifre_hash    nvarchar      NOT NULL
        rol           nvarchar      NOT NULL   -- app.enums.UserRole değerleri
    """

    id: int
    kullanici_adi: str
    sifre_hash: str
    rol: str


class StaffIdentityEntity(TypedDict):
    """`Kullanicilar`'ın parolasız izdüşümü.

    Token doğrulandıktan sonra "bu kullanıcı hâlâ var mı ve rolü hâlâ aynı mı"
    sorusunu cevaplamak için okunur. `sifre_hash` bilinçli olarak seçilmez:
    sorgu neye ihtiyaç duyuyorsa onu çeker, parola hash'i bu yola hiç girmez.
    """

    id: int
    kullanici_adi: str
    rol: str


class GarsonCredentialsEntity(TypedDict):
    """PIN doğrulaması için okunan garson satırı.

    `kullanici_adi` sorguda `garson_adi` olarak yeniden adlandırılır; sözlük
    anahtarı da bu yüzden `garson_adi`'dır.

    `sifre_hash` burada bilinçli olarak taşınır: garson PIN'i kullanıcı adı
    olmadan girildiği için servis, hash'i eşleşen kaydı bulmak üzere aday
    garsonların hash'lerini tek tek denemek zorundadır. Bu nesne asla
    controller'a veya HTTP yanıtına ulaşmaz; `AuthService.verify_garson_pin`
    içinde tüketilir ve dışarıya `KullaniciResponse` döner.
    """

    id: int
    garson_adi: str
    rol: str
    sifre_hash: str


class GarsonListEntity(TypedDict):
    """Garson seçim listesi için okunan izdüşüm (parola taşımaz)."""

    id: int
    garson_adi: str


class CustomerSessionEntity(TypedDict):
    """`CustomerSessions` tablosunun okunan alanları.

    Tabloda ayrıca `session_token_hash`, `is_active` ve `created_at` kolonları
    vardır; `get_active_customer_session` bunları seçmez çünkü ilk ikisi zaten
    WHERE koşuludur, üçüncüsü ise kullanılmaz.

    Ham token hiçbir zaman saklanmaz — yalnızca SHA-256 hash'i tutulur, bu
    yüzden veritabanını okuyan biri canlı oturum token'ı elde edemez.
    """

    id: int
    masa_id: int
    device_id: Optional[str]
    expires_at: datetime


class BannedDeviceEntity(TypedDict):
    """`BannedDevices` tablosundan varlık kontrolü için okunan izdüşüm."""

    id: int
