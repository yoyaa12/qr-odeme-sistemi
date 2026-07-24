from fastapi import APIRouter, Depends
from app.services.urun_service import UrunService
from app.services.kategori_service import KategoriService
from app.services.masa_service import MasaService
from app.schemas.schemas import UrunEkleModel, UrunGuncelleModel, KategoriEkleModel, MasaEkleModel

router = APIRouter()

@router.post("/admin/urunler")
async def add_urun(data: UrunEkleModel, service: UrunService = Depends()):
    uid = service.add_urun(data)
    return {"status": "success", "id": uid}

@router.put("/admin/urunler/{urun_id}")
async def update_urun(urun_id: int, data: UrunGuncelleModel, service: UrunService = Depends()):
    service.update_urun(urun_id, data)
    return {"status": "success", "message": "Ürün bilgileri güncellendi."}

@router.delete("/admin/urunler/{urun_id}")
async def delete_urun(urun_id: int, service: UrunService = Depends()):
    service.delete_urun(urun_id)
    return {"status": "success"}

@router.post("/admin/kategoriler")
async def add_kategori(data: KategoriEkleModel, service: KategoriService = Depends()):
    kid = service.add_kategori(data.kategori_adi)
    return {"status": "success", "id": kid}

@router.delete("/admin/kategoriler/{kategori_id}")
async def delete_kategori(kategori_id: int, service: KategoriService = Depends()):
    service.delete_kategori(kategori_id)
    return {"status": "success"}

@router.post("/admin/masalar")
async def add_masa(data: MasaEkleModel, service: MasaService = Depends()):
    mid = service.add_masa(data)
    return {"status": "success", "id": mid}

@router.delete("/admin/masalar/{masa_id}")
async def delete_masa(masa_id: int, service: MasaService = Depends()):
    service.delete_masa(masa_id)
    return {"status": "success"}
