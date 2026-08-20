from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import (
    get_current_user_or_customer,
    get_optional_staff,
    require_roles,
)
from app.auth.models import StaffPrincipal
from app.enums import UserRole
from app.services.masa_service import MasaService
from app.services.siparis_service import SiparisService
from app.schemas.common import GenelBasariliResponse
from app.schemas.orders import MasaAktifSiparisResponse
from app.schemas.tables import (
    DinamikQRResponse,
    MasaResponse,
    MasaTahsilatToplamlariResponse,
    MoveMasaItemsModel,
    MoveMasaModel,
    QRDogrulamaResponse,
    TahsilatModel,
    TumDinamikQRResponse,
    VerifyQRModel,
)

router = APIRouter()

table_operator = require_roles(UserRole.ADMIN, UserRole.WAITER, UserRole.CASHIER)
qr_display_operator = require_roles(UserRole.ADMIN, UserRole.CASHIER)

@router.get("/masalar", response_model=List[MasaResponse])
async def get_masalar(
    service: MasaService = Depends(),
    staff: StaffPrincipal | None = Depends(get_optional_staff),
) -> List[MasaResponse]:
    """Masa listesi.

    Müşteri menüsü masa adını okumak için bu ucu kimliksiz çağırır, bu yüzden
    uç public kalır. Ancak "hangi masa menüye bakıyor / sepete ne ekledi"
    bilgisi operasyonel veridir ve yalnızca kimliği doğrulanmış personele
    döndürülür.
    """
    if staff is not None:
        return service.get_masalar_with_browsing()
    return service.get_masalar()

@router.get(
    "/masalar/{masa_id}/aktif-siparis",
    response_model=MasaAktifSiparisResponse,
)
async def get_masa_aktif_siparis(
    masa_id: int,
    siparis_service: SiparisService = Depends(),
    actor: StaffPrincipal | dict = Depends(get_current_user_or_customer)
) -> MasaAktifSiparisResponse:
    viewer_session_id = None
    if isinstance(actor, dict):
        if actor["masa_id"] != masa_id:
            raise HTTPException(
                status_code=403,
                detail="Bu masanın siparişlerini görüntüleme yetkiniz yok."
            )
        # "Benim Siparişlerim" görünümü bu kimliğe dayanır. Doğrulanmış
        # oturumdan geldiği için bir cihaz başkasının siparişlerini kendi
        # siparişiymiş gibi listeleyemez.
        viewer_session_id = actor.get("id")

    return siparis_service.get_masa_aktif_siparis(
        masa_id, viewer_session_id=viewer_session_id
    )

@router.post(
    "/masalar/move",
    response_model=GenelBasariliResponse,
    dependencies=[Depends(table_operator)],
)
async def move_masa(
    data: MoveMasaModel, siparis_service: SiparisService = Depends()
) -> GenelBasariliResponse:
    await siparis_service.move_masa(data.from_masa_id, data.to_masa_id)
    return GenelBasariliResponse(status="success", message="Masa adisyonu başarıyla taşındı.")

@router.post(
    "/masalar/move-items",
    response_model=GenelBasariliResponse,
    dependencies=[Depends(table_operator)],
)
async def move_masa_items(
    data: MoveMasaItemsModel, siparis_service: SiparisService = Depends()
) -> GenelBasariliResponse:
    """Adisyonun yalnızca seçilen kalemlerini başka masaya aktarır.

    Kalem kimlikleri istemciden gelir ve servis katmanı her birinin gerçekten
    kaynak masaya ait olduğunu doğrular.
    """
    result = await siparis_service.move_masa_items(
        data.from_masa_id, data.to_masa_id, data.detay_ids
    )
    mesaj = (
        "Masa adisyonu başarıyla taşındı."
        if result.get("full_move")
        else f"{result.get('moved_detail_count', 0)} ürün seçili masaya aktarıldı."
    )
    return GenelBasariliResponse(status="success", message=mesaj)


@router.post(
    "/masalar/{masa_id}/clear",
    response_model=GenelBasariliResponse,
    dependencies=[Depends(table_operator)],
)
async def clear_masa(
    masa_id: int, siparis_service: SiparisService = Depends()
) -> GenelBasariliResponse:
    await siparis_service.clear_masa(masa_id)
    return GenelBasariliResponse(status="success", message="Masa oturumu sonlandırıldı.")

@router.get(
    "/masalar/all-dynamic-qrs",
    response_model=TumDinamikQRResponse,
    dependencies=[Depends(qr_display_operator)],
)
async def get_all_dynamic_qrs(masa_service: MasaService = Depends()) -> TumDinamikQRResponse:
    """Tüm masaların canlı 30 saniyelik Dinamik QR verilerini döner."""
    return masa_service.get_all_dynamic_qrs()

@router.get(
    "/masalar/all-tahsilatlar",
    response_model=MasaTahsilatToplamlariResponse,
    dependencies=[Depends(table_operator)],
)
async def get_all_tahsilatlar(
    siparis_service: SiparisService = Depends(),
) -> MasaTahsilatToplamlariResponse:
    """Tüm masaların aktif tahsilat toplamlarını döner."""
    return siparis_service.get_all_masa_tahsilatlari()

@router.get(
    "/masalar/{masa_id}/dynamic-qr",
    response_model=DinamikQRResponse,
    dependencies=[Depends(qr_display_operator)],
)
async def get_dynamic_qr(
    masa_id: int, masa_service: MasaService = Depends()
) -> DinamikQRResponse:
    """Masadaki dijital ekran veya Kasa simülatörü için canlı Dinamik QR bilgisini döner."""
    qr_info = masa_service.get_dynamic_qr_info(masa_id)
    if qr_info is None:
        raise HTTPException(status_code=404, detail="Masa bulunamadı.")
    return qr_info

@router.post("/masalar/{masa_id}/verify-qr", response_model=QRDogrulamaResponse)
async def verify_dynamic_qr(
    masa_id: int,
    data: VerifyQRModel,
    request: Request,
    masa_service: MasaService = Depends(),
) -> QRDogrulamaResponse:
    """Müşteri QR okuttuğunda gönderdiği dynamic token'ı doğrular.

    Kimlik doğrulaması gerektirmeyen tek doğrulama ucu olduğu için kaynak IP ve
    masa bazlı hız sınırına tabidir.
    """
    client_host = request.client.host if request.client else "unknown"
    return masa_service.verify_dynamic_qr_with_device(
        masa_id, data.token, data.device_id, client_host=client_host
    )

@router.post(
    "/masalar/{masa_id}/tahsilat",
    response_model=GenelBasariliResponse,
    dependencies=[Depends(table_operator)],
)
async def add_masa_tahsilat(
    masa_id: int, data: TahsilatModel, siparis_service: SiparisService = Depends()
) -> GenelBasariliResponse:
    await siparis_service.add_tahsilat(masa_id, data.tutar, data.odeme_yontemi)
    return GenelBasariliResponse(status="success", message="Tahsilat eklendi.")
