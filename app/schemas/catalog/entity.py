"""`Urunler` ve `Kategoriler` tablolarının satır şekilleri.

Tip seçimi neden `TypedDict` — ayrıntı için bkz. `app/schemas/auth/entity.py`.

Dikkat edilmesi gereken nokta: `decimal(10,2)` kolonları sürücüden
`decimal.Decimal` olarak gelir, `float` olarak değil. Servis katmanı fiyatla
aritmetik yapmadan önce bunu bilinçli olarak `float()`'a çevirir
(`SiparisService._calculate_item_authoritative_price`). Entity'nin bunu
`Decimal` diye deklare etmesinin amacı da bu: `Decimal * float` çalışmaz ve
dönüşümün nerede yapılması gerektiğini okurken görmek gerekir.

Alanlar 2026-08-20 tarihinde canlı şemadan doğrulanmıştır.
"""

from decimal import Decimal
from typing import Optional, TypedDict


class UrunEntity(TypedDict):
    """`Urunler` tablosunun tam satırı (`SELECT * FROM Urunler`).

    DDL:
        id           int      IDENTITY PRIMARY KEY
        kategori_id  int      NOT NULL  -> Kategoriler.id
        urun_adi     nvarchar(100)  NOT NULL
        aciklama     nvarchar(500)  NULL
        fiyat        decimal(10,2)  NOT NULL
        gorsel_url   nvarchar(255)  NULL
        stok_miktari int            NULL
        aktif_mi     bit            NULL   -- silme yerine pasifleştirme
    """

    id: int
    kategori_id: int
    urun_adi: str
    aciklama: Optional[str]
    fiyat: Decimal
    gorsel_url: Optional[str]
    stok_miktari: Optional[int]
    aktif_mi: Optional[bool]


class UrunWithKategoriEntity(UrunEntity):
    """`Urunler` satırı + `Kategoriler` ile JOIN'den gelen kategori adı.

    Menü listesi ürünü kategori adıyla birlikte gösterir; ayrı bir sorgu
    yerine tek JOIN ile alınır.
    """

    kategori_adi: str


class KategoriEntity(TypedDict):
    """`Kategoriler` tablosunun tam satırı.

    DDL:
        id           int      IDENTITY PRIMARY KEY
        kategori_adi nvarchar(50)   NOT NULL
        aktif_mi     bit            NULL
        gorsel_url   nvarchar(255)  NULL
    """

    id: int
    kategori_adi: str
    aktif_mi: Optional[bool]
    gorsel_url: Optional[str]
