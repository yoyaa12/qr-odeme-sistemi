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

class SiparisDuzenleModel(BaseModel):
    toplam_tutar: float
    urunler: List[SiparisItemModel]
    garson_adi: Optional[str] = None

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

class SiparisDetayResponse(BaseModel):
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
    odeme_yontemi: Optional[str] = None
    odeme_durumu: str
    siparis_durumu: str
    olusturma_tarihi: Optional[str] = None
    garson_adi: Optional[str] = None
    detaylar: List[SiparisDetayResponse] = []

class SiparisDurumResponse(BaseModel):
    siparis_id: int
    masa_id: int
    masa_no: str
    yeni_durum: str
    odeme_durumu: str
    garson_adi: Optional[str] = None
    guncelleme_tarihi: str
    siparis: SiparisResponse

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

class MasaResponse(BaseModel):
    id: int
    masa_no: str
    durum: str
    secim_durumu: Optional[dict] = None

class KullaniciResponse(BaseModel):
    id: int
    kullanici_adi: Optional[str] = None
    garson_adi: Optional[str] = None
    rol: Optional[str] = None

