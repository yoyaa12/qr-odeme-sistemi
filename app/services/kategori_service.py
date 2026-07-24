from fastapi import Depends
from app.repositories.kategori_repo import KategoriRepository

class KategoriService:
    def __init__(self, repo: KategoriRepository = Depends()):
        self.repo = repo

    def get_kategoriler(self):
        return self.repo.get_all_active()

    def add_kategori(self, kategori_adi: str):
        return self.repo.create(kategori_adi)

    def delete_kategori(self, kategori_id: int):
        self.repo.delete(kategori_id)
