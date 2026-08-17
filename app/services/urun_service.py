from fastapi import Depends
from typing import Optional, List
from app.repositories.urun_repo import UrunRepository
from app.schemas.catalog import UrunEkleModel, UrunGuncelleModel, UrunResponse
from app.database import db_transaction

class UrunService:
    def __init__(self, repo: UrunRepository = Depends()):
        self.repo = repo

    def get_urunler(self, kategori_id: Optional[int] = None) -> List[UrunResponse]:
        urunler = self.repo.get_all(kategori_id)
        return [UrunResponse(**u) for u in urunler] if urunler else []

    def add_urun(self, data: UrunEkleModel):
        with db_transaction():
            inserted_id = self.repo.create(data.kategori_id, data.urun_adi, data.aciklama, data.fiyat, data.gorsel_url, data.stok_miktari)
        return inserted_id

    def update_urun(self, urun_id: int, data: UrunGuncelleModel):
        updates = {
            "urun_adi": data.urun_adi,
            "fiyat": data.fiyat,
            "aciklama": data.aciklama,
            "stok_miktari": data.stok_miktari
        }
        with db_transaction():
            self.repo.update(urun_id, updates)

    def delete_urun(self, urun_id: int):
        with db_transaction():
            self.repo.delete(urun_id)
