from fastapi import Depends
from typing import List
from app.repositories.masa_repo import MasaRepository
from app.schemas.schemas import MasaEkleModel, MasaResponse
from app.database import db_transaction

class MasaService:
    def __init__(self, repo: MasaRepository = Depends()):
        self.repo = repo

    def get_masalar(self) -> List[MasaResponse]:
        masalar = self.repo.get_all()
        return [MasaResponse(**m) for m in masalar] if masalar else []
    
    def add_masa(self, data: MasaEkleModel):
        qr_code = f"MASA_{data.masa_no.upper().replace(' ', '_')}"
        with db_transaction():
            inserted_id = self.repo.create(data.masa_no, qr_code)
        return inserted_id

    def delete_masa(self, masa_id: int):
        with db_transaction():
            self.repo.delete(masa_id)
