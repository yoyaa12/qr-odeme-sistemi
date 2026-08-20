"""`Masalar` ve `MasaTahsilatlari` tablolarının satır şekilleri.

Tip seçimi neden `TypedDict` — ayrıntı için bkz. `app/schemas/auth/entity.py`.
Alanlar 2026-08-20 tarihinde canlı şemadan doğrulanmıştır.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, TypedDict


class MasaEntity(TypedDict):
    """`Masalar` tablosunun tam satırı.

    DDL:
        id          int            IDENTITY PRIMARY KEY
        masa_no     nvarchar(20)   NOT NULL
        qr_kodu     nvarchar       NOT NULL
        durum       nvarchar       NULL   -- app.enums.TableStatus değerleri
        totp_secret varchar        NULL

    `totp_secret` masanın dinamik QR kodunu üreten sırdır ve **asla dışarı
    çıkmaz**: `MasaResponse` bu alanı taşımaz, dolayısıyla repository satırı
    sırrı içerse bile HTTP yanıtına giremez. Masa boşaltıldığında sır yeniden
    üretilir (`MasaRepository.update_durum`), böylece önceki misafirin ekran
    görüntüsünü aldığı QR bir daha çalışmaz.
    """

    id: int
    masa_no: str
    qr_kodu: str
    durum: Optional[str]
    totp_secret: Optional[str]


class MasaTahsilatEntity(TypedDict):
    """`MasaTahsilatlari` tablosunun tam satırı.

    DDL:
        id               int            IDENTITY PRIMARY KEY
        masa_id          int            NOT NULL
        tutar            decimal(10,2)  NOT NULL
        odeme_yontemi    nvarchar(50)   NOT NULL
        is_closed        bit            NULL
        olusturma_tarihi datetime       NULL

    Kısmi ödemeler buraya satır satır yazılır. `is_closed = 0` olanlar açık
    adisyona sayılır; adisyon kapanınca satırlar silinmez, `is_closed = 1`
    yapılır — ödeme geçmişi korunur.
    """

    id: int
    masa_id: int
    tutar: Decimal
    odeme_yontemi: str
    is_closed: Optional[bool]
    olusturma_tarihi: Optional[datetime]
