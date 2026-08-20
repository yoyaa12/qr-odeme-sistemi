"""Masa alanının modelleri.

    entity.py    -> veritabanı satırının şekli
    request.py   -> istemciden gelen gövde
    response.py  -> istemciye dönen gövde
"""

from app.schemas.tables.entity import MasaEntity, MasaTahsilatEntity
from app.schemas.tables.request import (
    MasaEkleModel,
    MoveMasaItemsModel,
    MoveMasaModel,
    TahsilatModel,
    VerifyQRModel,
)
from app.schemas.tables.response import (
    DinamikQRResponse,
    MasaResponse,
    MasaTahsilatToplamlariResponse,
    QRDogrulamaResponse,
    TumDinamikQRResponse,
)

__all__ = [
    # entity
    "MasaEntity",
    "MasaTahsilatEntity",
    # request
    "MasaEkleModel",
    "MoveMasaItemsModel",
    "MoveMasaModel",
    "TahsilatModel",
    "VerifyQRModel",
    # response
    "DinamikQRResponse",
    "MasaResponse",
    "MasaTahsilatToplamlariResponse",
    "QRDogrulamaResponse",
    "TumDinamikQRResponse",
]
