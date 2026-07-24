from fastapi import APIRouter, Depends
from app.services.kategori_service import KategoriService

router = APIRouter()

@router.get("/kategoriler")
async def get_kategoriler(service: KategoriService = Depends()):
    return service.get_kategoriler()
