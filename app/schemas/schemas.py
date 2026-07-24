from pydantic import BaseModel
from typing import List, Optional

class SiparisItemModel(BaseModel):
    urun_id: int
    adet: int
    birim_fiyat: float
    urun_notu: Optional[str] = ""

class SiparisOlusturModel(BaseModel):
    masa_id: int
    toplam_tutar: float
    odeme_yontemi: Optional[str] = "pos" # pos veya nakit
    urunler: List[SiparisItemModel]

class DurumGuncelleModel(BaseModel):
    yeni_durum: str
    garson_adi: Optional[str] = None
    pin_code: Optional[str] = None

class GarsonPinVerifyModel(BaseModel):
    pin_code: str

class LoginModel(BaseModel):
    kullanici_adi: str
    sifre: str

class UrunEkleModel(BaseModel):
    kategori_id: int
    urun_adi: str
    aciklama: Optional[str] = ""
    fiyat: float
    gorsel_url: Optional[str] = ""
    stok_miktari: Optional[int] = 100

class UrunGuncelleModel(BaseModel):
    urun_adi: Optional[str] = None
    fiyat: Optional[float] = None
    aciklama: Optional[str] = None
    stok_miktari: Optional[int] = None

class KategoriEkleModel(BaseModel):
    kategori_adi: str

class MasaEkleModel(BaseModel):
    masa_no: str
