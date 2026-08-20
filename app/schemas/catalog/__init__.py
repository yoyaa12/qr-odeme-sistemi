"""Menü (ürün + kategori) alanının modelleri.

    entity.py    -> veritabanı satırının şekli
    request.py   -> istemciden gelen gövde + kolon uzunluk sınırları
    response.py  -> istemciye dönen gövde
"""

from app.schemas.catalog.entity import (
    KategoriEntity,
    UrunEntity,
    UrunWithKategoriEntity,
)
from app.schemas.catalog.request import (
    ACIKLAMA_MAX,
    GORSEL_URL_MAX,
    KATEGORI_ADI_MAX,
    PARA_MAX,
    STOK_MAX,
    URUN_ADI_MAX,
    KategoriEkleModel,
    UrunEkleModel,
    UrunGuncelleModel,
)
from app.schemas.catalog.response import (
    KaldirilanMenuResponse,
    KategoriResponse,
    UrunResponse,
)

__all__ = [
    # entity
    "KategoriEntity",
    "UrunEntity",
    "UrunWithKategoriEntity",
    # request
    "ACIKLAMA_MAX",
    "GORSEL_URL_MAX",
    "KATEGORI_ADI_MAX",
    "PARA_MAX",
    "STOK_MAX",
    "URUN_ADI_MAX",
    "KategoriEkleModel",
    "UrunEkleModel",
    "UrunGuncelleModel",
    # response
    "KaldirilanMenuResponse",
    "KategoriResponse",
    "UrunResponse",
]
