from fastapi import APIRouter, Depends
from app.services.auth_service import AuthService
from app.schemas.schemas import GarsonPinVerifyModel, BanDeviceModel

router = APIRouter()

@router.post("/garson/verify-pin")
async def verify_garson_pin(data: GarsonPinVerifyModel, service: AuthService = Depends()):
    garson = service.verify_garson_pin(data)
    return {"status": "success", "garson": garson}

@router.get("/garsonlar")
async def get_garsonlar(service: AuthService = Depends()):
    return service.get_garsonlar()

@router.post("/garson/ban-device")
async def ban_device(data: BanDeviceModel, service: AuthService = Depends()):
    return service.ban_device(data.device_id)
