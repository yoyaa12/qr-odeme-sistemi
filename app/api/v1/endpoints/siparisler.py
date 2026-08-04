from fastapi import APIRouter, Depends
from typing import Optional, List
from app.services.siparis_service import SiparisService
from app.schemas.schemas import (
    SiparisOlusturModel, 
    DurumGuncelleModel, 
    SiparisDuzenleModel,
    SiparisIslemCevapModel,
    SiparisDurumIslemCevapModel,
    SiparisResponse
)

router = APIRouter()

from fastapi import HTTPException

@router.post("/siparisler", response_model=SiparisIslemCevapModel)
async def create_siparis(data: SiparisOlusturModel, service: SiparisService = Depends()):
    full_order = await service.create_siparis(data)
    return {"status": "success", "message": "Sipariş oluşturuldu.", "siparis": full_order}

@router.get("/siparisler", response_model=List[SiparisResponse])
async def get_siparisler(durum: Optional[str] = None, masa_id: Optional[int] = None, service: SiparisService = Depends()):
    return service.get_siparisler(durum, masa_id)

@router.patch("/siparisler/{siparis_id}/durum", response_model=SiparisDurumIslemCevapModel)
async def update_siparis_durumu(siparis_id: int, data: DurumGuncelleModel, service: SiparisService = Depends()):
    event_payload = await service.update_siparis_durumu(siparis_id, data)
    return {"status": "success", "message": "Sipariş güncellendi.", "data": event_payload}

@router.put("/siparisler/{siparis_id}", response_model=SiparisIslemCevapModel)
async def update_siparis_items(siparis_id: int, data: SiparisDuzenleModel, service: SiparisService = Depends()):
    updated_order = await service.update_siparis_items(siparis_id, data)
    return {"status": "success", "message": "Sipariş kalemleri güncellendi.", "siparis": updated_order}
