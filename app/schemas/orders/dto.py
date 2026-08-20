"""Servis katmanının kendi içinde taşıdığı ara nesneler.

DTO burada ne bir tablo satırı ne de bir HTTP gövdesidir: iki servis metodu
arasında dolaşan, dışarıya hiç çıkmayan ara veridir. Ayrı bir dosyada
durmasının nedeni tam olarak bu — `entity.py` veritabanına, `response.py` dış
dünyaya bakar; burası ikisinin arasındaki hesaplama adımına bakar.
"""

from typing import Optional, TypedDict


class PricedOrderLine(TypedDict):
    """Sunucunun katalogdan yeniden fiyatlandırdığı tek sipariş kalemi.

    `SiparisService._price_items_authoritatively` üretir; `_assert_stock_available`,
    `_persist_order_items` ve `SiparisRepository.replace_siparis_items` tüketir.

    Neden istek modeli (`SiparisItemModel`) doğrudan repository'ye verilmiyor:
    istekteki `birim_fiyat` istemciden gelir ve güvenilmez. Bu DTO'daki fiyat
    ise `Urunler` tablosundan okunup not seçeneklerine göre yeniden hesaplanmış
    olandır. Araya bu nesnenin girmesi, istemcinin gönderdiği bir fiyatın
    veritabanına ulaşmasını yapısal olarak imkânsız kılar.

    `_stok_miktari` alt çizgiyle başlar: yalnızca stok kontrolü sırasında
    kullanılan geçici bir alandır ve `_persist_order_items` satırı yazmadan önce
    alt çizgiyle başlayan tüm anahtarları eler.
    """

    urun_id: int
    urun_adi: str
    adet: int
    birim_fiyat: float
    urun_notu: str
    ara_toplam: float
    _stok_miktari: Optional[int]


class MasaTasimaSonucu(TypedDict):
    """Kalem taşıma işleminin sonucu.

    `full_move` doğruysa masanın tamamı taşınmıştır (seçim, masadaki her kalemi
    kapsıyordu) ve controller mesajı buna göre kurar. Çalışma zamanında düz bir
    sözlüktür; `TypedDict` yalnızca hangi anahtarları taşıdığını deklare eder.
    """

    moved_detail_count: int
    full_move: bool
