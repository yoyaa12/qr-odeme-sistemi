"""Personel/kullanıcı alanının modelleri.

Dosya ayrımı katmanları birbirinden ayırır:

    entity.py    -> veritabanı satırının şekli   (içeri, repository katmanı)
    request.py   -> istemciden gelen gövde       (dışarıdan içeri)
    response.py  -> istemciye dönen gövde        (içeriden dışarı)

`from app.schemas.auth import LoginModel` gibi mevcut kullanım aynen çalışmaya
devam eder; hangi dosyada olduğunu bilmek gerekmez.
"""

from app.schemas.auth.entity import (
    BannedDeviceEntity,
    CustomerSessionEntity,
    GarsonCredentialsEntity,
    GarsonListEntity,
    KullaniciEntity,
    StaffIdentityEntity,
)
from app.schemas.auth.request import BanDeviceModel, GarsonPinVerifyModel, LoginModel
from app.schemas.auth.response import (
    GarsonPinResponse,
    GarsonResponse,
    KullaniciResponse,
    LoginResponse,
)

__all__ = [
    # entity
    "BannedDeviceEntity",
    "CustomerSessionEntity",
    "GarsonCredentialsEntity",
    "GarsonListEntity",
    "KullaniciEntity",
    "StaffIdentityEntity",
    # request
    "BanDeviceModel",
    "GarsonPinVerifyModel",
    "LoginModel",
    # response
    "GarsonPinResponse",
    "GarsonResponse",
    "KullaniciResponse",
    "LoginResponse",
]
