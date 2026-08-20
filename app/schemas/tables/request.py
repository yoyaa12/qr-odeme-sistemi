"""Masa ve QR uçlarının kabul ettiği istek gövdeleri."""

from typing import List, Optional

from pydantic import BaseModel, Field


class MasaEkleModel(BaseModel):
    masa_no: str = Field(min_length=1, max_length=20)


class MoveMasaModel(BaseModel):
    """Bir masanın adisyonunun tamamını başka masaya aktarma isteği."""

    from_masa_id: int = Field(gt=0)
    to_masa_id: int = Field(gt=0)


class MoveMasaItemsModel(BaseModel):
    """Adisyonun bir bölümünü başka masaya aktarma isteği.

    ``detay_ids`` `SiparisDetaylari.id` listesidir. Üst sınır, tek istekle
    masanın tamamını tarayan denemeleri sınırlamak için; gerçek bir masanın
    kalem sayısının çok üzerinde.
    """

    from_masa_id: int = Field(gt=0)
    to_masa_id: int = Field(gt=0)
    detay_ids: List[int] = Field(min_length=1, max_length=200)


class VerifyQRModel(BaseModel):
    """Müşterinin QR okuttuktan sonra gönderdiği dinamik token."""

    token: str = Field(min_length=1, max_length=32)
    device_id: Optional[str] = Field(default=None, max_length=100)


class TahsilatModel(BaseModel):
    """Partial payment recorded against a table.

    ``tutar`` must be positive: a negative amount would subtract from the table's
    collected total and make an unpaid bill look settled.
    """

    tutar: float = Field(gt=0)
    odeme_yontemi: str = Field(min_length=1, max_length=50)
