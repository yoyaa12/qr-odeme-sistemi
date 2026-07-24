from fastapi import APIRouter, Depends
from typing import Optional
from app.services.urun_service import UrunService

router = APIRouter()

@router.get("/urunler")
async def get_urunler(kategori_id: Optional[int] = None, service: UrunService = Depends()):
    return service.get_urunler(kategori_id)
