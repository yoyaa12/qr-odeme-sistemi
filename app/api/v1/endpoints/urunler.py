from fastapi import APIRouter, Depends
from typing import Optional, List
from app.schemas.schemas import UrunResponse
from app.services.urun_service import UrunService

router = APIRouter()

@router.get("/urunler", response_model=List[UrunResponse])
async def get_urunler(kategori_id: Optional[int] = None, service: UrunService = Depends()):
    return service.get_urunler(kategori_id)
