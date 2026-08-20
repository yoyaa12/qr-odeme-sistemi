"""Sipariş uçlarının döndürdüğü yanıt nesneleri.

Entity ile yanıt arasındaki fark bu alanda en belirgin olanıdır:
`SiparisEntity` `customer_session_id` taşır, `SiparisResponse` taşımaz —
onun yerine sunucunun hesapladığı `is_mine` bayrağı gider. Masadaki bir
müşterinin diğerlerinin oturum kimliklerini öğrenmesi için hiçbir neden yok.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.enums import OrderStatus, PaymentMethod, PaymentStatus


class SiparisDetayResponse(BaseModel):
    # `SiparisDetaylari.id`. Kasadaki "seçili ürünleri taşı" akışı kalemi tek tek
    # adreslemek zorunda: ürün adı + adet benzersiz değil, aynı üründen iki ayrı
    # satır olabiliyor. Sunucu yine de gönderilen her id'nin gerçekten kaynak
    # masaya ait olduğunu doğrular; id bilmek yetki anlamına gelmez.
    id: Optional[int] = None
    urun_id: int
    urun_adi: str
    adet: int
    birim_fiyat: float
    urun_notu: str
    ara_toplam: float


class SiparisResponse(BaseModel):
    id: int
    masa_id: int
    masa_no: str
    siparis_kodu: str
    toplam_tutar: float
    # `Siparisler` tablosunda böyle bir kolon yoktur; sipariş durumundan
    # türetilen sunum bilgisidir (bkz. `app/schemas/orders/entity.py`).
    odeme_yontemi: Optional[PaymentMethod] = None
    odeme_durumu: PaymentStatus
    siparis_durumu: OrderStatus
    olusturma_tarihi: Optional[str] = None
    garson_adi: Optional[str] = None
    device_id: Optional[str] = None
    # Bu siparişi isteği yapan müşteri oturumunun verip vermediği. Sunucu
    # hesaplar; istemcinin gönderdiği hiçbir alana bakılmaz. Personel
    # yollarında ve oturumu bilinmeyen eski kayıtlarda `None` kalır.
    #
    # Ham `customer_session_id` bilinçli olarak dışarı verilmez: masadaki bir
    # müşterinin diğerlerinin oturum kimliklerini görmesi için hiçbir neden yok.
    is_mine: Optional[bool] = None
    detaylar: List[SiparisDetayResponse] = Field(default_factory=list)


class SiparisDurumResponse(BaseModel):
    siparis_id: int
    masa_id: int
    masa_no: str
    yeni_durum: OrderStatus
    odeme_durumu: PaymentStatus
    garson_adi: Optional[str] = None
    guncelleme_tarihi: str
    siparis: SiparisResponse


class SiparisIslemCevapModel(BaseModel):
    status: str
    message: str
    siparis: SiparisResponse


class SiparisDurumIslemCevapModel(BaseModel):
    status: str
    message: str
    data: SiparisDurumResponse


class MasaAktifSiparisResponse(BaseModel):
    """Bir masanın açık adisyonunun tamamı.

    Yanıt her zaman masanın TAMAMINI içerir: ödenecek tutar masanın tamamıdır ve
    müşteriye yalnızca kendi kalemlerini göstermek, hesap geldiğinde sürprize
    yol açar. Kişisel görünüm istemcide bir filtredir; hangi siparişin kime ait
    olduğu ise sunucuda `SiparisResponse.is_mine` ile işaretlenir.

    `benim_toplamim` yalnızca müşteri oturumuyla yapılan çağrılarda dolar;
    personel yollarında `None` kalır ("bu soru sorulmadı").

    `redirect_masa_id` ve `redirect_masa_no` yalnızca adisyon başka bir masaya
    taşınmışsa dolar: müşterinin telefonu eski masa numarasını sorgulamaya devam
    ettiği için sunucu onu yeni masaya yönlendirir.
    """

    has_active: bool
    siparisler: List[SiparisResponse] = Field(default_factory=list)
    siparis: Optional[SiparisResponse] = None
    genel_toplam: float
    benim_toplamim: Optional[float] = None
    alinan_tutar: float
    redirect_masa_id: Optional[int] = None
    redirect_masa_no: Optional[str] = None
