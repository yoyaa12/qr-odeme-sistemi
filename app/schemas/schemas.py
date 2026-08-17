"""Compatibility exports for code that still imports the former schema module."""

from app.schemas.auth import (
    BanDeviceModel,
    GarsonPinResponse,
    GarsonPinVerifyModel,
    GarsonResponse,
    KullaniciResponse,
    LoginModel,
    LoginResponse,
)
from app.schemas.catalog import (
    KategoriEkleModel,
    KategoriResponse,
    UrunEkleModel,
    UrunGuncelleModel,
    UrunResponse,
)
from app.schemas.common import AdminIslemResponse, GenelBasariliResponse
from app.schemas.orders import (
    DurumGuncelleModel,
    SiparisDetayResponse,
    SiparisDurumIslemCevapModel,
    SiparisDurumResponse,
    SiparisIslemCevapModel,
    SiparisItemModel,
    SiparisOlusturModel,
    SiparisDuzenleModel,
    SiparisResponse,
)
from app.schemas.tables import (
    MasaEkleModel,
    MasaResponse,
    MoveMasaModel,
    QRDogrulamaResponse,
    VerifyQRModel,
)

__all__ = [
    "AdminIslemResponse",
    "BanDeviceModel",
    "DurumGuncelleModel",
    "GarsonPinResponse",
    "GarsonPinVerifyModel",
    "GarsonResponse",
    "GenelBasariliResponse",
    "KategoriEkleModel",
    "KategoriResponse",
    "KullaniciResponse",
    "LoginModel",
    "LoginResponse",
    "MasaEkleModel",
    "MasaResponse",
    "MoveMasaModel",
    "QRDogrulamaResponse",
    "SiparisDetayResponse",
    "SiparisDurumIslemCevapModel",
    "SiparisDurumResponse",
    "SiparisIslemCevapModel",
    "SiparisItemModel",
    "SiparisOlusturModel",
    "SiparisDuzenleModel",
    "SiparisResponse",
    "UrunEkleModel",
    "UrunGuncelleModel",
    "UrunResponse",
    "VerifyQRModel",
]
