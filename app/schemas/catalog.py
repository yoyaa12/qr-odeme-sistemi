from typing import Optional

from pydantic import BaseModel, Field


class UrunEkleModel(BaseModel):
    kategori_id: int = Field(gt=0)
    urun_adi: str = Field(min_length=1)
    aciklama: Optional[str] = ""
    fiyat: float = Field(ge=0)
    gorsel_url: Optional[str] = ""
    stok_miktari: Optional[int] = Field(default=100, ge=0)


class UrunGuncelleModel(BaseModel):
    urun_adi: Optional[str] = Field(default=None, min_length=1)
    fiyat: Optional[float] = Field(default=None, ge=0)
    aciklama: Optional[str] = None
    stok_miktari: Optional[int] = Field(default=None, ge=0)


class KategoriEkleModel(BaseModel):
    kategori_adi: str = Field(min_length=1)


class UrunResponse(BaseModel):
    id: int
    kategori_id: int
    kategori_adi: Optional[str] = None
    urun_adi: str
    aciklama: Optional[str] = None
    fiyat: float
    gorsel_url: Optional[str] = None
    stok_miktari: int


class KategoriResponse(BaseModel):
    id: int
    kategori_adi: str
    gorsel_url: Optional[str] = None
