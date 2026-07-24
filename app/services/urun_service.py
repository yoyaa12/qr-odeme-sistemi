from fastapi import Depends
from typing import Optional
from app.repositories.urun_repo import UrunRepository
from app.schemas.schemas import UrunEkleModel, UrunGuncelleModel

class UrunService:
    def __init__(self, repo: UrunRepository = Depends()):
        self.repo = repo

    def get_urunler(self, kategori_id: Optional[int] = None):
        return self.repo.get_all(kategori_id)

    def add_urun(self, data: UrunEkleModel):
        return self.repo.create(data.kategori_id, data.urun_adi, data.aciklama, data.fiyat, data.gorsel_url, data.stok_miktari)

    def update_urun(self, urun_id: int, data: UrunGuncelleModel):
        updates = {
            "urun_adi": data.urun_adi,
            "fiyat": data.fiyat,
            "aciklama": data.aciklama,
            "stok_miktari": data.stok_miktari
        }
        self.repo.update(urun_id, updates)

    def delete_urun(self, urun_id: int):
        self.repo.delete(urun_id)
