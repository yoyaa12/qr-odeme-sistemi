from fastapi import APIRouter, Depends
from app.services.masa_service import MasaService
from app.services.siparis_service import SiparisService

router = APIRouter()

@router.get("/masalar")
async def get_masalar(service: MasaService = Depends()):
    return service.get_masalar()

@router.get("/masalar/{masa_id}/aktif-siparis")
async def get_masa_aktif_siparis(masa_id: int, siparis_service: SiparisService = Depends()):
    return siparis_service.get_masa_aktif_siparis(masa_id)

@router.post("/masalar/{masa_id}/clear")
async def clear_masa(masa_id: int, siparis_service: SiparisService = Depends()):
    await siparis_service.clear_masa(masa_id)
    return {"status": "success", "message": "Masa temizlendi ve oturum kapatıldı."}
