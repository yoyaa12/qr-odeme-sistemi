"""Menü yönetimi uçlarının kabul ettiği istek gövdeleri."""

from typing import Optional

from pydantic import BaseModel, Field


# Limits taken from the live schema on 2026-08-17 so an over-long or over-large
# value is rejected as HTTP 422 by validation instead of reaching SQL Server and
# failing there as an HTTP 500. Keep these in step with the columns declared in
# `app/schemas/catalog/entity.py`:
#   Urunler.urun_adi        nvarchar(100)
#   Urunler.aciklama        nvarchar(500)
#   Urunler.gorsel_url      nvarchar(255)
#   Kategoriler.kategori_adi nvarchar(50)
#   money columns           decimal(10,2) -> max 99999999.99
#   stok_miktari            int           -> max 2147483647
URUN_ADI_MAX = 100
ACIKLAMA_MAX = 500
GORSEL_URL_MAX = 255
KATEGORI_ADI_MAX = 50
PARA_MAX = 99_999_999.99
STOK_MAX = 2_147_483_647


class UrunEkleModel(BaseModel):
    kategori_id: int = Field(gt=0)
    urun_adi: str = Field(min_length=1, max_length=URUN_ADI_MAX)
    aciklama: Optional[str] = Field(default="", max_length=ACIKLAMA_MAX)
    fiyat: float = Field(ge=0, le=PARA_MAX)
    gorsel_url: Optional[str] = Field(default="", max_length=GORSEL_URL_MAX)
    stok_miktari: Optional[int] = Field(default=100, ge=0, le=STOK_MAX)


class UrunGuncelleModel(BaseModel):
    """Kısmi güncelleme: yalnızca `None` olmayan alanlar yazılır.

    Gönderilmeyen alan "değiştirme" demektir, "boşalt" demek değil. Yönetici
    panelindeki düzenleme formu alanların tamamını gönderir; stok kutusu ise
    yalnızca `stok_miktari` gönderir.

    `kategori_id` ürünü başka bir kategoriye taşır. Servis katmanı hedef
    kategorinin var olduğunu ve menüden kaldırılmamış olduğunu doğrular:
    kaldırılmış bir kategoriye taşınan ürün menüde hiç görünmezdi.
    """

    urun_adi: Optional[str] = Field(default=None, min_length=1, max_length=URUN_ADI_MAX)
    kategori_id: Optional[int] = Field(default=None, gt=0)
    fiyat: Optional[float] = Field(default=None, ge=0, le=PARA_MAX)
    aciklama: Optional[str] = Field(default=None, max_length=ACIKLAMA_MAX)
    stok_miktari: Optional[int] = Field(default=None, ge=0, le=STOK_MAX)


class KategoriEkleModel(BaseModel):
    kategori_adi: str = Field(min_length=1, max_length=KATEGORI_ADI_MAX)
