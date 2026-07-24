import uuid
import datetime
from fastapi import Depends, HTTPException
from typing import Optional

from app.core.socket_manager import sio
from app.repositories.siparis_repo import SiparisRepository
from app.repositories.masa_repo import MasaRepository
from app.repositories.urun_repo import UrunRepository
from app.schemas.schemas import SiparisOlusturModel, DurumGuncelleModel

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
        urun_repo: UrunRepository = Depends()
    ):
        self.siparis_repo = siparis_repo
        self.masa_repo = masa_repo
        self.urun_repo = urun_repo

    async def create_siparis(self, data: SiparisOlusturModel):
        masa = self.masa_repo.get_by_id(data.masa_id)
        if not masa:
            raise HTTPException(status_code=404, detail="Geçersiz masa ID!")

        siparis_kodu = f"SIP-{uuid.uuid4().hex[:6].upper()}"
        
        odeme_durumu = "odendi" if data.odeme_yontemi == "pos" else "bekliyor"
        
        if data.odeme_yontemi == "pos":
            siparis_durumu = "odendi_mutfakta"
        elif data.odeme_yontemi == "garson_kasada":
            siparis_durumu = "garson_onayi_bekliyor"
        else:
            siparis_durumu = "nakit_bekliyor"

        siparis_id = self.siparis_repo.create_siparis(
            data.masa_id, siparis_kodu, data.toplam_tutar, odeme_durumu, siparis_durumu
        )

        if not siparis_id:
            raise HTTPException(status_code=500, detail="Sipariş veritabanına eklenirken hata oluştu.")

        self.masa_repo.update_durum(data.masa_id, 'dolu')

        detaylar = []
        for item in data.urunler:
            ara_toplam = item.adet * item.birim_fiyat
            self.siparis_repo.create_siparis_detay(
                siparis_id, item.urun_id, item.adet, item.birim_fiyat, item.urun_notu, ara_toplam
            )

            u_info = self.urun_repo.get_by_id(item.urun_id)
            urun_adi = u_info['urun_adi'] if u_info else f"Ürün #{item.urun_id}"

            self.urun_repo.update_stock(item.urun_id, item.adet)

            detaylar.append({
                "urun_id": item.urun_id,
                "urun_adi": urun_adi,
                "adet": item.adet,
                "birim_fiyat": item.birim_fiyat,
                "urun_notu": item.urun_notu,
                "ara_toplam": ara_toplam
            })

        full_order = {
            "id": siparis_id,
            "masa_id": data.masa_id,
            "masa_no": masa['masa_no'],
            "siparis_kodu": siparis_kodu,
            "toplam_tutar": data.toplam_tutar,
            "odeme_yontemi": data.odeme_yontemi,
            "odeme_durumu": odeme_durumu,
            "siparis_durumu": siparis_durumu,
            "olusturma_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
            "detaylar": detaylar
        }

        if data.odeme_yontemi == "pos":
            await sio.emit("yeni_siparis", full_order)

        await sio.emit("masa_durumu_degisti", {"masa_id": data.masa_id, "durum": "dolu"})
        
        if data.odeme_yontemi == "garson_kasada":
            await sio.emit("garson_onay_talebi", {
                "siparis_id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa['masa_no'],
                "toplam_tutar": data.toplam_tutar,
                "siparis": full_order
            })
        elif data.odeme_yontemi == "nakit":
            await sio.emit("nakit_odeme_talebi", {
                "siparis_id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa['masa_no'],
                "toplam_tutar": data.toplam_tutar,
                "siparis": full_order
            })

        return full_order

    def get_siparisler(self, durum: Optional[str] = None, masa_id: Optional[int] = None):
        siparisler = self.siparis_repo.get_all(durum, masa_id)
        for s in siparisler:
            s['detaylar'] = self.siparis_repo.get_siparis_detaylari(s['id'])
        return sanitize_for_json(siparisler)

    def get_masa_aktif_siparis(self, masa_id: int):
        siparis = self.siparis_repo.get_active_by_masa_id(masa_id)
        if siparis:
            siparis['detaylar'] = self.siparis_repo.get_siparis_detaylari(siparis['id'])
            if isinstance(siparis.get('olusturma_tarihi'), datetime.datetime):
                siparis['olusturma_tarihi'] = siparis['olusturma_tarihi'].strftime("%H:%M:%S")
            return {"has_active": True, "siparis": siparis}
        return {"has_active": False, "siparis": None}

    async def update_siparis_durumu(self, siparis_id: int, data: DurumGuncelleModel):
        yeni_durum = data.yeni_durum.lower()
        
        s_info = self.siparis_repo.get_by_id(siparis_id)
        if not s_info:
            raise HTTPException(status_code=404, detail="Sipariş bulunamadı!")

        garson_adi = data.garson_adi or "Garson Berat"

        if yeni_durum == "nakit_tahsil_edildi":
            self.siparis_repo.update_odeme_and_durum(siparis_id, "odendi", "odendi_mutfakta", garson_adi)
            yeni_durum = "odendi_mutfakta"
        else:
            self.siparis_repo.update_durum(siparis_id, yeni_durum, garson_adi if yeni_durum in ['garson_onayladi_mutfakta', 'teslim_edildi'] else None)

        if yeni_durum in ["teslim_edildi", "iptal"]:
            aktif_sayi = self.siparis_repo.get_active_count_for_masa(s_info['masa_id'])
            if aktif_sayi == 0:
                self.masa_repo.update_durum(s_info['masa_id'], 'bos')
                await sio.emit("masa_durumu_degisti", {"masa_id": s_info['masa_id'], "durum": "bos"})

        updated_order = self.siparis_repo.get_by_id(siparis_id)
        if not updated_order:
            updated_order = dict(s_info)
            updated_order['siparis_durumu'] = yeni_durum
        
        updated_order['detaylar'] = self.siparis_repo.get_siparis_detaylari(siparis_id)
        updated_order = sanitize_for_json(updated_order)

        event_payload = sanitize_for_json({
            "siparis_id": siparis_id,
            "masa_id": s_info['masa_id'],
            "masa_no": s_info['masa_no'],
            "yeni_durum": yeni_durum,
            "odeme_durumu": updated_order.get("odeme_durumu", "odendi"),
            "garson_adi": garson_adi,
            "guncelleme_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
            "siparis": updated_order
        })

        if data.yeni_durum in ["nakit_tahsil_edildi", "garson_onayladi_mutfakta"]:
            await sio.emit("yeni_siparis", updated_order)
            await sio.emit("nakit_odendi", event_payload)

        await sio.emit("durum_guncellendi", event_payload)
        return event_payload

    async def clear_masa(self, masa_id: int):
        self.masa_repo.update_durum(masa_id, 'bos')
        self.siparis_repo.clear_active_orders_for_masa(masa_id)
        
        event_payload = {"masa_id": masa_id, "durum": "bos"}
        await sio.emit("masa_durumu_degisti", event_payload)
        await sio.emit("masa_temizlendi", {"masa_id": masa_id})
