from fastapi import APIRouter, Depends
from app.services.urun_service import UrunService
from app.services.kategori_service import KategoriService
from app.services.masa_service import MasaService
from app.schemas.schemas import (
    UrunEkleModel, UrunGuncelleModel, KategoriEkleModel, MasaEkleModel,
    AdminIslemResponse
)

router = APIRouter()

@router.post("/admin/urunler", response_model=AdminIslemResponse)
async def add_urun(data: UrunEkleModel, service: UrunService = Depends()):
    uid = service.add_urun(data)
    return AdminIslemResponse(status="success", id=uid)

@router.put("/admin/urunler/{urun_id}", response_model=AdminIslemResponse)
async def update_urun(urun_id: int, data: UrunGuncelleModel, service: UrunService = Depends()):
    service.update_urun(urun_id, data)
    return AdminIslemResponse(status="success", message="Ürün bilgileri güncellendi.")

@router.delete("/admin/urunler/{urun_id}", response_model=AdminIslemResponse)
async def delete_urun(urun_id: int, service: UrunService = Depends()):
    service.delete_urun(urun_id)
    return AdminIslemResponse(status="success")

@router.post("/admin/kategoriler", response_model=AdminIslemResponse)
async def add_kategori(data: KategoriEkleModel, service: KategoriService = Depends()):
    kid = service.add_kategori(data.kategori_adi)
    return AdminIslemResponse(status="success", id=kid)

@router.delete("/admin/kategoriler/{kategori_id}", response_model=AdminIslemResponse)
async def delete_kategori(kategori_id: int, service: KategoriService = Depends()):
    service.delete_kategori(kategori_id)
    return AdminIslemResponse(status="success")

@router.post("/admin/masalar", response_model=AdminIslemResponse)
async def add_masa(data: MasaEkleModel, service: MasaService = Depends()):
    mid = service.add_masa(data)
    return AdminIslemResponse(status="success", id=mid)

@router.delete("/admin/masalar/{masa_id}", response_model=AdminIslemResponse)
async def delete_masa(masa_id: int, service: MasaService = Depends()):
    service.delete_masa(masa_id)
    return AdminIslemResponse(status="success")

