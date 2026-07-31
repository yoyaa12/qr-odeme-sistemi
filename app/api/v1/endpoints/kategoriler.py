from fastapi import APIRouter, Depends
from app.services.kategori_service import KategoriService

router = APIRouter()

from typing import List
from app.schemas.schemas import KategoriResponse

@router.get("/kategoriler", response_model=List[KategoriResponse])
async def get_kategoriler(service: KategoriService = Depends()):
    return service.get_kategoriler()
