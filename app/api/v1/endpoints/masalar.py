from fastapi import APIRouter, Depends
from app.services.masa_service import MasaService
from app.services.siparis_service import SiparisService
from app.core.socket_manager import get_browsing_tables

router = APIRouter()

from typing import List
from app.schemas.schemas import MasaResponse

@router.get("/masalar", response_model=List[MasaResponse])
async def get_masalar(service: MasaService = Depends()):
    masalar = service.get_masalar()
    browsing = get_browsing_tables()
    for m in masalar:
        m.secim_durumu = browsing.get(m.id)
    return masalar

@router.get("/masalar/{masa_id}/aktif-siparis")
async def get_masa_aktif_siparis(masa_id: int, siparis_service: SiparisService = Depends()):
    return siparis_service.get_masa_aktif_siparis(masa_id)

from pydantic import BaseModel

class MoveMasaModel(BaseModel):
    from_masa_id: int
    to_masa_id: int

@router.post("/masalar/move")
async def move_masa(data: MoveMasaModel, siparis_service: SiparisService = Depends()):
    await siparis_service.move_masa(data.from_masa_id, data.to_masa_id)
    return {"status": "success", "message": "Masa adisyonu başarıyla taşındı."}

@router.post("/masalar/{masa_id}/clear")
async def clear_masa(masa_id: int, siparis_service: SiparisService = Depends()):
    await siparis_service.clear_masa(masa_id)
    return {"status": "success", "message": "Masa oturumu sonlandırıldı."}
