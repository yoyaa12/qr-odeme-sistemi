"""Kimlik doğrulama uçlarının kabul ettiği istek gövdeleri.

Bu dosyadaki her model **dışarıdan gelen** veriyi tarif eder ve bu yüzden her
alanın bir uzunluk sınırı vardır: sınır aşıldığında istek SQL Server'a hiç
ulaşmadan HTTP 422 ile reddedilir.
"""

from pydantic import BaseModel, Field


class LoginModel(BaseModel):
    """`POST /api/auth/login` gövdesi.

    `rol` alanı bilinçli olarak yoktur: rol, veritabanındaki kayıttan okunur.
    İstemcinin kendi rolünü bildirebilmesi, yetki yükseltmenin en kısa yolu
    olurdu.
    """

    kullanici_adi: str = Field(min_length=1, max_length=50)
    sifre: str = Field(min_length=1, max_length=255)


class GarsonPinVerifyModel(BaseModel):
    """`POST /api/garson/verify-pin` gövdesi.

    Yalnızca PIN taşır; hangi garsona ait olduğu sunucuda hash karşılaştırmasıyla
    bulunur. Kullanıcı adının da gönderilmesi, geçerli PIN'i bilen birinin onu
    istediği garsonun üzerine yazdırmasına izin verirdi.
    """

    pin_code: str = Field(min_length=1, max_length=255)


class BanDeviceModel(BaseModel):
    """`POST /api/garson/ban-device` gövdesi."""

    device_id: str = Field(min_length=1, max_length=100)
