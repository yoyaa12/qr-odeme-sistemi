from fastapi import APIRouter, Depends
from typing import List
from app.services.auth_service import AuthService
from app.schemas.schemas import (
    GarsonPinVerifyModel, BanDeviceModel,
    GarsonPinResponse, KullaniciResponse, GenelBasariliResponse
)

router = APIRouter()

@router.post("/garson/verify-pin", response_model=GarsonPinResponse)
async def verify_garson_pin(data: GarsonPinVerifyModel, service: AuthService = Depends()):
    garson = service.verify_garson_pin(data)
    return GarsonPinResponse(status="success", garson=garson)

@router.get("/garsonlar", response_model=List[KullaniciResponse])
async def get_garsonlar(service: AuthService = Depends()):
    return service.get_garsonlar()

@router.post("/garson/ban-device", response_model=GenelBasariliResponse)
async def ban_device(data: BanDeviceModel, service: AuthService = Depends()):
    result = service.ban_device(data.device_id)
    return GenelBasariliResponse(**result)
