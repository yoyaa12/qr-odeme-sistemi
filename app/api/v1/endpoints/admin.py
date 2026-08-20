from fastapi import APIRouter, Depends
from app.auth.dependencies import require_roles
from app.enums import UserRole
from app.services.urun_service import UrunService
from app.services.kategori_service import KategoriService
from app.services.masa_service import MasaService
from app.schemas.catalog import (
    KaldirilanMenuResponse,
    KategoriEkleModel,
    UrunEkleModel,
    UrunGuncelleModel,
)
from app.schemas.common import AdminIslemResponse
from app.schemas.tables import MasaEkleModel

router = APIRouter(
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)

@router.post("/admin/urunler", response_model=AdminIslemResponse)
async def add_urun(data: UrunEkleModel, service: UrunService = Depends()) -> AdminIslemResponse:
    uid = service.add_urun(data)
    return AdminIslemResponse(status="success", id=uid)

@router.put("/admin/urunler/{urun_id}", response_model=AdminIslemResponse)
async def update_urun(
    urun_id: int, data: UrunGuncelleModel, service: UrunService = Depends()
) -> AdminIslemResponse:
    await service.update_urun(urun_id, data)
    return AdminIslemResponse(status="success", message="Ürün bilgileri güncellendi.")

@router.delete("/admin/urunler/{urun_id}", response_model=AdminIslemResponse)
async def delete_urun(urun_id: int, service: UrunService = Depends()) -> AdminIslemResponse:
    """Ürünü menüden kaldırır.

    Kaldırma yumuşaktır: satır sipariş geçmişi için durmaya devam eder, ürün
    yalnızca menüden çıkar. Bilinmeyen ürün için 404 döner.
    """
    service.delete_urun(urun_id)
    return AdminIslemResponse(status="success", message="Ürün menüden kaldırıldı.")

@router.post("/admin/kategoriler", response_model=AdminIslemResponse)
async def add_kategori(
    data: KategoriEkleModel, service: KategoriService = Depends()
) -> AdminIslemResponse:
    kid = service.add_kategori(data.kategori_adi)
    return AdminIslemResponse(status="success", id=kid)

@router.delete("/admin/kategoriler/{kategori_id}", response_model=AdminIslemResponse)
async def delete_kategori(
    kategori_id: int, service: KategoriService = Depends()
) -> AdminIslemResponse:
    """Kategoriyi ve altındaki ürünleri menüden kaldırır.

    Kaç ürünün etkilendiği yanıtta bildirilir; eski cascade davranışı bunu
    sessizce yapıyordu.
    """
    etkilenen = service.delete_kategori(kategori_id)
    mesaj = (
        f"Kategori ve içindeki {etkilenen} ürün menüden kaldırıldı."
        if etkilenen
        else "Kategori menüden kaldırıldı."
    )
    return AdminIslemResponse(
        status="success", message=mesaj, etkilenen_urun_sayisi=etkilenen
    )

@router.post("/admin/masalar", response_model=AdminIslemResponse)
async def add_masa(data: MasaEkleModel, service: MasaService = Depends()) -> AdminIslemResponse:
    mid = service.add_masa(data)
    return AdminIslemResponse(status="success", id=mid)

@router.delete("/admin/masalar/{masa_id}", response_model=AdminIslemResponse)
async def delete_masa(masa_id: int, service: MasaService = Depends()) -> AdminIslemResponse:
    service.delete_masa(masa_id)
    return AdminIslemResponse(status="success")



# --- Menüden kaldırılanları geri getirme -------------------------------------
#
# Kaldırma yumuşak olduğu için (`aktif_mi = 0`) kayıtlar veritabanında durur.
# Bu uçlar olmadan geri getirmenin tek yolu veritabanına elle müdahale etmekti.


@router.get("/admin/menu/kaldirilanlar", response_model=KaldirilanMenuResponse)
async def get_kaldirilan_menu(
    urun_service: UrunService = Depends(),
    kategori_service: KategoriService = Depends(),
) -> KaldirilanMenuResponse:
    """Menüden kaldırılmış ürün ve kategoriler."""
    return KaldirilanMenuResponse(
        kategoriler=kategori_service.get_kaldirilan_kategoriler(),
        urunler=urun_service.get_kaldirilan_urunler(),
    )


@router.post("/admin/urunler/{urun_id}/geri-yukle", response_model=AdminIslemResponse)
async def restore_urun(
    urun_id: int, service: UrunService = Depends()
) -> AdminIslemResponse:
    """Kaldırılmış ürünü menüye geri getirir.

    Ürünün kategorisi hâlâ kaldırılmışsa 409 döner: o durumda ürün aktif olsa
    bile menüde görünmezdi.
    """
    service.restore_urun(urun_id)
    return AdminIslemResponse(status="success", message="Ürün menüye geri getirildi.")


@router.post(
    "/admin/kategoriler/{kategori_id}/geri-yukle", response_model=AdminIslemResponse
)
async def restore_kategori(
    kategori_id: int, service: KategoriService = Depends()
) -> AdminIslemResponse:
    """Kaldırılmış kategoriyi menüye geri getirir.

    Ürünleri otomatik geri gelmez; kaç ürünün hâlâ kaldırılmış olduğu yanıtta
    bildirilir ki yönetici tek tek karar verebilsin.
    """
    kalan = service.restore_kategori(kategori_id)
    mesaj = (
        f"Kategori menüye geri getirildi. {kalan} ürünü hâlâ kaldırılmış durumda."
        if kalan
        else "Kategori menüye geri getirildi."
    )
    return AdminIslemResponse(
        status="success", message=mesaj, etkilenen_urun_sayisi=kalan
    )
