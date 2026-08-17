from fastapi import Depends
from typing import List
from app.repositories.kategori_repo import KategoriRepository
from app.schemas.catalog import KategoriResponse
from app.database import db_transaction

class KategoriService:
    def __init__(self, repo: KategoriRepository = Depends()):
        self.repo = repo

    def get_kategoriler(self) -> List[KategoriResponse]:
        kategoriler = self.repo.get_all_active()
        return [KategoriResponse(**k) for k in kategoriler] if kategoriler else []

    def add_kategori(self, kategori_adi: str):
        with db_transaction():
            inserted_id = self.repo.create(kategori_adi)
        return inserted_id

    def delete_kategori(self, kategori_id: int):
        with db_transaction():
            self.repo.delete(kategori_id)
