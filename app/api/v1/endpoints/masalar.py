from fastapi import APIRouter, Depends
from typing import List
from app.services.masa_service import MasaService
from app.services.siparis_service import SiparisService
from app.schemas.schemas import (
    MasaResponse, MoveMasaModel, VerifyQRModel,
    QRDogrulamaResponse, GenelBasariliResponse
)

router = APIRouter()

@router.get("/masalar", response_model=List[MasaResponse])
async def get_masalar(service: MasaService = Depends()):
    return service.get_masalar_with_browsing()

@router.get("/masalar/{masa_id}/aktif-siparis")
async def get_masa_aktif_siparis(masa_id: int, siparis_service: SiparisService = Depends()):
    return siparis_service.get_masa_aktif_siparis(masa_id)

@router.post("/masalar/move", response_model=GenelBasariliResponse)
async def move_masa(data: MoveMasaModel, siparis_service: SiparisService = Depends()):
    await siparis_service.move_masa(data.from_masa_id, data.to_masa_id)
    return GenelBasariliResponse(status="success", message="Masa adisyonu başarıyla taşındı.")

@router.post("/masalar/{masa_id}/clear", response_model=GenelBasariliResponse)
async def clear_masa(masa_id: int, siparis_service: SiparisService = Depends()):
    await siparis_service.clear_masa(masa_id)
    return GenelBasariliResponse(status="success", message="Masa oturumu sonlandırıldı.")

@router.get("/masalar/all-dynamic-qrs")
async def get_all_dynamic_qrs(masa_service: MasaService = Depends()):
    """Tüm masaların canlı 30 saniyelik Dinamik QR verilerini döner."""
    return masa_service.get_all_dynamic_qrs()

@router.get("/masalar/{masa_id}/dynamic-qr")
async def get_dynamic_qr(masa_id: int, masa_service: MasaService = Depends()):
    """Masadaki dijital ekran veya Kasa simülatörü için canlı Dinamik QR bilgisini döner."""
    return masa_service.get_dynamic_qr_info(masa_id)

@router.post("/masalar/{masa_id}/verify-qr", response_model=QRDogrulamaResponse)
async def verify_dynamic_qr(masa_id: int, data: VerifyQRModel, masa_service: MasaService = Depends()):
    """Müşteri QR okuttuğunda gönderdiği dynamic token'ı doğrular."""
    return masa_service.verify_dynamic_qr_with_device(masa_id, data.token, data.device_id)
