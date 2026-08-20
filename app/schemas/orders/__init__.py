"""Sipariş alanının modelleri.

    entity.py    -> veritabanı satırının şekli   (repository katmanı)
    dto.py       -> servisler arası ara nesneler (dışarı çıkmaz)
    request.py   -> istemciden gelen gövde
    response.py  -> istemciye dönen gövde
"""

from app.schemas.orders.dto import MasaTasimaSonucu, PricedOrderLine
from app.schemas.orders.entity import (
    SiparisDetayEntity,
    SiparisDetayWithUrunEntity,
    SiparisEntity,
    SiparisWithMasaEntity,
    UndeliveredUrunAdetRow,
)
from app.schemas.orders.request import (
    MAX_LINE_QUANTITY,
    DurumGuncelleModel,
    SiparisDuzenleModel,
    SiparisItemModel,
    SiparisOlusturModel,
)
from app.schemas.orders.response import (
    MasaAktifSiparisResponse,
    SiparisDetayResponse,
    SiparisDurumIslemCevapModel,
    SiparisDurumResponse,
    SiparisIslemCevapModel,
    SiparisResponse,
)

__all__ = [
    # entity
    "SiparisDetayEntity",
    "SiparisDetayWithUrunEntity",
    "SiparisEntity",
    "SiparisWithMasaEntity",
    "UndeliveredUrunAdetRow",
    # dto
    "MasaTasimaSonucu",
    "PricedOrderLine",
    # request
    "MAX_LINE_QUANTITY",
    "DurumGuncelleModel",
    "SiparisDuzenleModel",
    "SiparisItemModel",
    "SiparisOlusturModel",
    # response
    "MasaAktifSiparisResponse",
    "SiparisDetayResponse",
    "SiparisDurumIslemCevapModel",
    "SiparisDurumResponse",
    "SiparisIslemCevapModel",
    "SiparisResponse",
]
