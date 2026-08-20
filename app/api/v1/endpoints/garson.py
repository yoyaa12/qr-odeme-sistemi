from fastapi import APIRouter, Depends, Request
from typing import List
from app.auth.dependencies import require_roles
from app.enums import UserRole
from app.services.auth_service import AuthService
from app.schemas.auth import (
    BanDeviceModel,
    GarsonPinResponse,
    GarsonPinVerifyModel,
    KullaniciResponse,
)
from app.schemas.common import GenelBasariliResponse

router = APIRouter()

waiter_or_admin = require_roles(UserRole.WAITER, UserRole.ADMIN)

@router.post("/garson/verify-pin", response_model=GarsonPinResponse)
def verify_garson_pin(
    data: GarsonPinVerifyModel,
    request: Request,
    service: AuthService = Depends(),
) -> GarsonPinResponse:
    client_host = request.client.host if request.client else "unknown"
    result = service.verify_garson_pin(data, client_host)
    garson = KullaniciResponse(
        id=result.principal.user_id,
        garson_adi=result.principal.username,
        rol=result.principal.role,
    )
    return GarsonPinResponse(
        status="success",
        garson=garson,
        access_token=result.access_token,
        expires_in=result.expires_in,
    )

@router.get(
    "/garsonlar",
    response_model=List[KullaniciResponse],
    dependencies=[Depends(waiter_or_admin)],
)
async def get_garsonlar(service: AuthService = Depends()) -> List[KullaniciResponse]:
    return service.get_garsonlar()

@router.post(
    "/garson/ban-device",
    response_model=GenelBasariliResponse,
    dependencies=[Depends(waiter_or_admin)],
)
async def ban_device(
    data: BanDeviceModel, service: AuthService = Depends()
) -> GenelBasariliResponse:
    return service.ban_device(data.device_id)
