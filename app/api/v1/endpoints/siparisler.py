from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user_or_customer, require_roles
from app.auth.models import StaffPrincipal
from app.enums import UserRole
from app.schemas.orders import (
    DurumGuncelleModel,
    SiparisDurumIslemCevapModel,
    SiparisDuzenleModel,
    SiparisIslemCevapModel,
    SiparisOlusturModel,
    SiparisResponse,
)
from app.services.siparis_service import SiparisService

router = APIRouter()

authenticated_staff = require_roles(
    UserRole.ADMIN,
    UserRole.WAITER,
    UserRole.KITCHEN,
    UserRole.CASHIER,
)
order_editor = require_roles(UserRole.ADMIN, UserRole.WAITER)


@router.post("/siparisler", response_model=SiparisIslemCevapModel)
async def create_siparis(
    data: SiparisOlusturModel,
    service: SiparisService = Depends(),
    actor: StaffPrincipal | dict = Depends(get_current_user_or_customer)
):
    if isinstance(actor, dict):
        if actor["masa_id"] != data.masa_id:
            raise HTTPException(
                status_code=403,
                detail="Bu oturum ile sadece yetkili olduğunuz masaya sipariş verebilirsiniz."
            )

    full_order = await service.create_siparis(data)
    return {"status": "success", "message": "Sipariş oluşturuldu.", "siparis": full_order}


@router.get("/siparisler", response_model=List[SiparisResponse])
async def get_siparisler(
    durum: Optional[str] = None,
    masa_id: Optional[int] = None,
    service: SiparisService = Depends(),
    _principal: StaffPrincipal = Depends(authenticated_staff),
):
    return service.get_siparisler(durum, masa_id)


@router.patch("/siparisler/{siparis_id}/durum", response_model=SiparisDurumIslemCevapModel)
async def update_siparis_durumu(
    siparis_id: int,
    data: DurumGuncelleModel,
    service: SiparisService = Depends(),
    principal: StaffPrincipal = Depends(authenticated_staff),
):
    event_payload = await service.update_siparis_durumu(siparis_id, data, principal)
    return {"status": "success", "message": "Sipariş güncellendi.", "data": event_payload}


@router.put("/siparisler/{siparis_id}", response_model=SiparisIslemCevapModel)
async def update_siparis_items(
    siparis_id: int,
    data: SiparisDuzenleModel,
    service: SiparisService = Depends(),
    principal: StaffPrincipal = Depends(order_editor),
):
    updated_order = await service.update_siparis_items(siparis_id, data, principal)
    return {"status": "success", "message": "Sipariş kalemleri güncellendi.", "siparis": updated_order}
