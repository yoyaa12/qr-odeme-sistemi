from typing import List

from fastapi import APIRouter, Depends

from app.schemas.catalog import KategoriResponse
from app.services.kategori_service import KategoriService

router = APIRouter()


@router.get("/kategoriler", response_model=List[KategoriResponse])
async def get_kategoriler(service: KategoriService = Depends()) -> List[KategoriResponse]:
    return service.get_kategoriler()
