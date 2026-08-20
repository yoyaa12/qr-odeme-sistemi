"""`Siparisler` ve `SiparisDetaylari` tablolarının satır şekilleri.

Tip seçimi neden `TypedDict` — ayrıntı için bkz. `app/schemas/auth/entity.py`.
Alanlar 2026-08-20 tarihinde canlı şemadan doğrulanmıştır.

Bu dosyayı okurken dikkat edilmesi gereken iki nokta:

1. `Siparisler` tablosunda **`odeme_yontemi` kolonu yoktur.** `SiparisResponse`
   böyle bir alan taşır ama o, sipariş durumundan türetilen bir sunum
   bilgisidir — veritabanında saklanan bir kolon değildir.
2. `decimal(10,2)` kolonları sürücüden `Decimal` gelir, `float` değil.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, TypedDict


class SiparisEntity(TypedDict):
    """`Siparisler` tablosunun tam satırı.

    DDL:
        id                  int            IDENTITY PRIMARY KEY
        masa_id             int            NOT NULL -> Masalar.id
        siparis_kodu        nvarchar       NOT NULL  -- misafire gösterilen fiş no
        toplam_tutar        decimal(10,2)  NOT NULL
        odeme_durumu        nvarchar       NULL  -- app.enums.PaymentStatus
        siparis_durumu      nvarchar       NULL  -- app.enums.OrderStatus
        olusturma_tarihi    datetime       NULL
        garson_adi          nvarchar       NULL  -- denetim izi; kimlikten yazılır
        device_id           varchar        NULL  -- istemciden gelir, TAKLİT EDİLEBİLİR
        customer_session_id int            NULL  -> CustomerSessions.id

    `device_id` ile `customer_session_id` arasındaki fark kritik: ilki istek
    gövdesinden gelir, dolayısıyla "bu siparişi kim verdi" sorusunun cevabı
    olarak kullanılamaz — bir cihaz başkasının değerini gönderebilir. İkincisi
    doğrulanmış oturumdan yazılır ve sahiplik kararı (`is_mine`) yalnızca ona
    dayanır. Personel tarafından oluşturulan kayıtlarda NULL kalır.
    """

    id: int
    masa_id: int
    siparis_kodu: str
    toplam_tutar: Decimal
    odeme_durumu: Optional[str]
    siparis_durumu: Optional[str]
    olusturma_tarihi: Optional[datetime]
    garson_adi: Optional[str]
    device_id: Optional[str]
    customer_session_id: Optional[int]


class SiparisWithMasaEntity(SiparisEntity):
    """`Siparisler` satırı + `Masalar` ile JOIN'den gelen masa numarası.

    Repository'nin okuma yolları siparişi neredeyse her zaman bu biçimde döner:
    panellerin hepsi siparişi masa numarasıyla gösterir, `masa_id` tek başına
    ekranda işe yaramaz.
    """

    masa_no: str


class SiparisDetayEntity(TypedDict):
    """`SiparisDetaylari` tablosunun tam satırı.

    DDL:
        id          int            IDENTITY PRIMARY KEY
        siparis_id  int            NOT NULL -> Siparisler.id
        urun_id     int            NOT NULL -> Urunler.id
        adet        int            NOT NULL
        birim_fiyat decimal(10,2)  NOT NULL
        urun_notu   nvarchar(255)  NULL
        ara_toplam  decimal(10,2)  NOT NULL

    `birim_fiyat` sipariş anındaki fiyatın kopyasıdır; ürünün güncel fiyatına
    bakılmaz. Menü fiyatı sonradan değişse bile kesilmiş adisyon değişmez.
    """

    id: int
    siparis_id: int
    urun_id: int
    adet: int
    birim_fiyat: Decimal
    urun_notu: Optional[str]
    ara_toplam: Decimal


class SiparisDetayWithUrunEntity(SiparisDetayEntity):
    """`SiparisDetaylari` satırı + `Urunler` ile JOIN'den gelen ürün adı.

    Kasadaki "seçili kalemleri taşı" akışı satırı `id` ile adresler; ürün adı
    yalnızca kullanıcıya göstermek içindir.
    """

    urun_adi: str


class UndeliveredUrunAdetRow(TypedDict):
    """Ürün bazında toplanmış teslim edilmemiş adet (GROUP BY sonucu).

    Bir tablo satırı değil, bir toplama sorgusunun çıktısıdır: adisyon
    kapanırken stoğa geri verilecek miktarları taşır.
    """

    urun_id: int
    adet: int
