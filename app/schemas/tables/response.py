"""Masa ve QR uçlarının döndürdüğü yanıt nesneleri.

`MasaResponse` ile `MasaEntity` arasındaki fark bu ayrımın neden var olduğunun
en net örneğidir: entity `totp_secret` ve `qr_kodu` taşır, yanıt taşımaz. Masa
listesi kimlik doğrulaması olmadan da okunabildiği için (müşteri menüsü masa
adını buradan alır), sırrın yanıt modelinde hiç tanımlı olmaması tek başına
yeterli bir güvencedir.
"""

from typing import Dict, Optional

from pydantic import BaseModel

from app.enums import TableStatus


class MasaResponse(BaseModel):
    """Masa listesi öğesi.

    `secim_durumu` yalnızca kimliği doğrulanmış personele doldurulur; müşteri
    çağrısında `None` kalır (bkz. `GET /api/masalar`).
    """

    id: int
    masa_no: str
    durum: TableStatus
    secim_durumu: Optional[dict] = None


class QRDogrulamaResponse(BaseModel):
    """QR doğrulama sonucu.

    Başarısız doğrulamada `session_token` doldurulmaz; `valid=False` ile birlikte
    yalnızca kullanıcıya gösterilecek mesaj döner.
    """

    valid: bool
    message: str
    masa_id: Optional[int] = None
    session_token: Optional[str] = None


class DinamikQRResponse(BaseModel):
    """Bir masanın o an geçerli olan 30 saniyelik dinamik QR bilgisi.

    `token` masanın `totp_secret`'ından türetilir ama sırrın kendisi değildir:
    süresi dolduğunda işe yaramaz hale gelir. Sır hiçbir koşulda bu yanıta
    girmez.
    """

    masa_id: int
    masa_no: str
    token: str
    remaining_seconds: int
    qr_url: str


# Kasa ekranı bütün masaların QR'ını tek çağrıda ister; anahtar masa id'sidir.
TumDinamikQRResponse = Dict[int, DinamikQRResponse]

# Aktif (kapatılmamış) kısmi ödeme toplamları, masa id'sine göre.
# Anahtar JSON'da her zaman metin olduğu için burada da `str` olarak deklare
# edilir; `SiparisService.get_all_masa_tahsilatlari` sözlüğü zaten böyle kurar.
MasaTahsilatToplamlariResponse = Dict[str, float]
