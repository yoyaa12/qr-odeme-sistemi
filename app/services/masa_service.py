from fastapi import Depends
from app.repositories.masa_repo import MasaRepository
from app.schemas.schemas import MasaEkleModel

class MasaService:
    def __init__(self, repo: MasaRepository = Depends()):
        self.repo = repo

    def get_masalar(self):
        return self.repo.get_all()
    
    def add_masa(self, data: MasaEkleModel):
        qr_code = f"MASA_{data.masa_no.upper().replace(' ', '_')}"
        return self.repo.create(data.masa_no, qr_code)

    def delete_masa(self, masa_id: int):
        self.repo.delete(masa_id)
