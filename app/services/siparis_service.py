import uuid
import datetime
from fastapi import Depends, HTTPException
from typing import Optional, List

from app.core.events import event_bus
from app.core.socket_manager import clear_browsing_table
from app.repositories.siparis_repo import SiparisRepository
from app.repositories.masa_repo import MasaRepository
from app.repositories.urun_repo import UrunRepository
from app.repositories.auth_repo import AuthRepository
from app.schemas.schemas import SiparisOlusturModel, DurumGuncelleModel, SiparisDuzenleModel
from app.schemas.schemas import SiparisResponse, SiparisDetayResponse, SiparisDurumResponse
from app.database import db_transaction

def sanitize_for_json(data):
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (datetime.datetime, datetime.date, datetime.time)):
        return data.strftime("%H:%M:%S") if isinstance(data, (datetime.datetime, datetime.time)) else str(data)
    import decimal
    if isinstance(data, decimal.Decimal):
        return float(data)
    return data

class SiparisService:
    def __init__(
        self, 
        siparis_repo: SiparisRepository = Depends(),
        masa_repo: MasaRepository = Depends(),
        urun_repo: UrunRepository = Depends(),
        auth_repo: AuthRepository = Depends()
    ):
        self.siparis_repo = siparis_repo
        self.masa_repo = masa_repo
        self.urun_repo = urun_repo
        self.auth_repo = auth_repo

    def _determine_initial_status(self, odeme_yontemi: str):
        odeme_durumu = "odendi" if odeme_yontemi == "pos" else "bekliyor"
        
        if odeme_yontemi == "pos":
            siparis_durumu = "odendi_mutfakta"
        elif odeme_yontemi == "garson_kasada":
            siparis_durumu = "garson_onayi_bekliyor"
        else:
            siparis_durumu = "nakit_bekliyor"
            
        return odeme_durumu, siparis_durumu

    def _process_order_items(self, siparis_id: int, urunler: list) -> List[dict]:
        detaylar = []
        for item in urunler:
            ara_toplam = item.adet * item.birim_fiyat
            self.siparis_repo.create_siparis_detay(
                siparis_id, item.urun_id, item.adet, item.birim_fiyat, item.urun_notu or "", ara_toplam
            )

            u_info = self.urun_repo.get_by_id(item.urun_id)
            urun_adi = u_info['urun_adi'] if u_info else f"Ürün #{item.urun_id}"

            self.urun_repo.update_stock(item.urun_id, item.adet)

            detaylar.append({
                "urun_id": item.urun_id,
                "urun_adi": urun_adi,
                "adet": item.adet,
                "birim_fiyat": item.birim_fiyat,
                "urun_notu": item.urun_notu or "",
                "ara_toplam": ara_toplam
            })
        return detaylar

    async def _publish_order_events(self, data: SiparisOlusturModel, siparis_id: int, masa_no: str, order_dict: dict):
        if data.odeme_yontemi == "pos":
            await event_bus.publish("yeni_siparis", order_dict)

        await event_bus.publish("masa_durumu_degisti", {"masa_id": data.masa_id, "durum": "dolu"})
        
        if data.odeme_yontemi == "garson_kasada":
            await event_bus.publish("garson_onay_talebi", {
                "siparis_id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa_no,
                "toplam_tutar": data.toplam_tutar,
                "siparis": order_dict
            })
        elif data.odeme_yontemi == "nakit":
            await event_bus.publish("nakit_odeme_talebi", {
                "siparis_id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa_no,
                "toplam_tutar": data.toplam_tutar,
                "siparis": order_dict
            })

    async def create_siparis(self, data: SiparisOlusturModel) -> SiparisResponse:
        if data.device_id:
            banned = self.auth_repo.get_banned_device(data.device_id)
            if banned:
                raise HTTPException(status_code=403, detail="Erişiminiz engellendi. Cihazınız yasaklı.")

        with db_transaction():
            masa = self.masa_repo.get_by_id(data.masa_id)
            if not masa:
                raise HTTPException(status_code=404, detail="Geçersiz masa ID!")

            siparis_kodu = f"SIP-{uuid.uuid4().hex[:6].upper()}"
            odeme_durumu, siparis_durumu = self._determine_initial_status(data.odeme_yontemi)

            siparis_id = self.siparis_repo.create_siparis(
                data.masa_id, siparis_kodu, data.toplam_tutar, odeme_durumu, siparis_durumu, data.device_id
            )

            if not siparis_id:
                raise HTTPException(status_code=500, detail="Sipariş veritabanına eklenirken hata oluştu.")

            self.masa_repo.update_durum(data.masa_id, 'dolu')
            detaylar = self._process_order_items(siparis_id, data.urunler)
            clear_browsing_table(data.masa_id)

            full_order_dict = {
                "id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa['masa_no'],
                "siparis_kodu": siparis_kodu,
                "toplam_tutar": data.toplam_tutar,
                "odeme_yontemi": data.odeme_yontemi,
                "odeme_durumu": odeme_durumu,
                "siparis_durumu": siparis_durumu,
                "olusturma_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
                "garson_adi": None,
                "device_id": data.device_id,
                "detaylar": detaylar
            }
            full_order = SiparisResponse.model_validate(full_order_dict)

        await self._publish_order_events(data, siparis_id, masa['masa_no'], full_order.model_dump())
        return full_order

    def _map_to_siparis_response(self, order_dict: dict) -> SiparisResponse:
        order_dict['detaylar'] = self.siparis_repo.get_siparis_detaylari(order_dict['id'])
        for d in order_dict['detaylar']:
            d['urun_notu'] = d.get('urun_notu') or ""
        
        if isinstance(order_dict.get('olusturma_tarihi'), datetime.datetime):
            order_dict['olusturma_tarihi'] = order_dict['olusturma_tarihi'].strftime("%H:%M:%S")
            
        return SiparisResponse.model_validate(order_dict)

    def get_siparisler(self, durum: Optional[str] = None, masa_id: Optional[int] = None) -> List[SiparisResponse]:
        siparisler = self.siparis_repo.get_all(durum, masa_id)
        return [self._map_to_siparis_response(s) for s in siparisler]

    def get_masa_aktif_siparis(self, masa_id: int):
        siparis = self.siparis_repo.get_active_by_masa_id(masa_id)
        if siparis:
            s_dto = self._map_to_siparis_response(siparis)
            return {"has_active": True, "siparis": s_dto}
        return {"has_active": False, "siparis": None}

    async def update_siparis_durumu(self, siparis_id: int, data: DurumGuncelleModel) -> SiparisDurumResponse:
        yeni_durum = data.yeni_durum.lower()
        garson_adi = data.garson_adi or "Garson Berat"
        masa_bosaldi = False

        with db_transaction():
            s_info = self.siparis_repo.get_by_id(siparis_id)
            if not s_info:
                raise HTTPException(status_code=404, detail="Sipariş bulunamadı!")

            if yeni_durum == "nakit_tahsil_edildi":
                self.siparis_repo.update_odeme_and_durum(siparis_id, "odendi", "odendi_mutfakta", garson_adi)
                yeni_durum = "odendi_mutfakta"
            else:
                self.siparis_repo.update_durum(siparis_id, yeni_durum, garson_adi if yeni_durum in ['garson_onayladi_mutfakta', 'teslim_edildi'] else None)

            if yeni_durum in ["teslim_edildi", "iptal"]:
                aktif_sayi = self.siparis_repo.get_active_count_for_masa(s_info['masa_id'])
                unpaid_sayi = self.siparis_repo.get_unpaid_count_for_masa(s_info['masa_id'])
                if aktif_sayi == 0 and unpaid_sayi == 0:
                    self.masa_repo.update_durum(s_info['masa_id'], 'bos')
                    clear_browsing_table(s_info['masa_id'])
                    masa_bosaldi = True

            updated_order = self.siparis_repo.get_by_id(siparis_id)
            if not updated_order:
                updated_order = dict(s_info)
                updated_order['siparis_durumu'] = yeni_durum
            
            s_dto = self._map_to_siparis_response(updated_order)

            event_payload = SiparisDurumResponse(
                siparis_id=siparis_id,
                masa_id=s_info['masa_id'],
                masa_no=s_info['masa_no'],
                yeni_durum=yeni_durum,
                odeme_durumu=updated_order.get("odeme_durumu", "odendi"),
                garson_adi=garson_adi,
                guncelleme_tarihi=datetime.datetime.now().strftime("%H:%M:%S"),
                siparis=s_dto
            )

        payload_dict = event_payload.model_dump()
        s_dto_dict = s_dto.model_dump()

        if masa_bosaldi:
            await event_bus.publish("masa_durumu_degisti", {"masa_id": s_info['masa_id'], "durum": "bos"})

        if data.yeni_durum in ["nakit_tahsil_edildi", "garson_onayladi_mutfakta"]:
            await event_bus.publish("yeni_siparis", s_dto_dict)
            await event_bus.publish("nakit_odendi", payload_dict)

        await event_bus.publish("durum_guncellendi", payload_dict)
        return event_payload

    async def clear_masa(self, masa_id: int):
        with db_transaction():
            self.masa_repo.update_durum(masa_id, 'bos')
            self.siparis_repo.clear_active_orders_for_masa(masa_id)
            clear_browsing_table(masa_id)
        
        event_payload = {"masa_id": masa_id, "durum": "bos"}
        await event_bus.publish("masa_durumu_degisti", event_payload)
        await event_bus.publish("masa_temizlendi", {"masa_id": masa_id})
        await event_bus.publish("durum_guncellendi", {"masa_id": masa_id, "yeni_durum": "bos"})

    async def update_siparis_items(self, siparis_id: int, data: SiparisDuzenleModel) -> SiparisResponse:
        garson_adi = data.garson_adi or "Garson Berat"
        
        with db_transaction():
            s_info = self.siparis_repo.get_by_id(siparis_id)
            if not s_info:
                raise HTTPException(status_code=404, detail="Sipariş bulunamadı!")
            
            self.siparis_repo.update_siparis_items(siparis_id, data.toplam_tutar, data.urunler, garson_adi)
            
            updated_order = self.siparis_repo.get_by_id(siparis_id)
            s_dto = self._map_to_siparis_response(updated_order)

            event_payload = {
                "siparis_id": siparis_id,
                "masa_id": s_info['masa_id'],
                "masa_no": s_info['masa_no'],
                "yeni_durum": s_info.get("siparis_durumu", "garson_onayi_bekliyor"),
                "odeme_durumu": s_info.get("odeme_durumu", "bekliyor"),
                "garson_adi": garson_adi,
                "guncelleme_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
                "siparis": s_dto.model_dump()
            }

        await event_bus.publish("durum_guncellendi", event_payload)
        return s_dto

    async def move_masa(self, from_masa_id: int, to_masa_id: int):
        with db_transaction():
            self.siparis_repo.move_orders_between_masalar(from_masa_id, to_masa_id)
            self.masa_repo.update_durum(to_masa_id, 'dolu')
            
            unpaid_cnt = self.siparis_repo.get_unpaid_count_for_masa(from_masa_id)
            if unpaid_cnt == 0:
                self.masa_repo.update_durum(from_masa_id, 'bos')
                clear_browsing_table(from_masa_id)
        
        await event_bus.publish("masa_durumu_degisti", {"masa_id": from_masa_id, "durum": "bos"})
        await event_bus.publish("masa_durumu_degisti", {"masa_id": to_masa_id, "durum": "dolu"})
        await event_bus.publish("durum_guncellendi", {"from_masa_id": from_masa_id, "to_masa_id": to_masa_id})
