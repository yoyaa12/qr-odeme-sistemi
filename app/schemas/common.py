from typing import Optional

from pydantic import BaseModel


class AdminIslemResponse(BaseModel):
    """Yönetici panelindeki oluştur/güncelle/kaldır işlemlerinin yanıtı.

    `etkilenen_urun_sayisi` yalnızca kategori kaldırmada dolar: kategoriyle
    birlikte menüden çıkan ürün sayısını taşır. Eski `ON DELETE CASCADE`
    davranışı bu ürünleri hiçbir bildirim yapmadan siliyordu; sayıyı yanıta
    koymak, işlemin kapsamını yöneticiye görünür kılar.
    """

    status: str
    message: Optional[str] = None
    id: Optional[int] = None
    etkilenen_urun_sayisi: Optional[int] = None


class GenelBasariliResponse(BaseModel):
    status: str
    message: str
