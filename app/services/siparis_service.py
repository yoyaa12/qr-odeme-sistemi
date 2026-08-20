import uuid
import datetime
import time
from fastapi import Depends, HTTPException
from typing import Dict, List, Optional

from app.core.events import event_bus
from app.core.socket_manager import clear_browsing_table
from app.core.totp_service import verify_dynamic_token
from app.auth.models import StaffPrincipal
from app.enums import OrderAction, OrderStatus, PaymentMethod, PaymentStatus, TableStatus
from app.repositories.siparis_repo import SiparisRepository
from app.repositories.masa_repo import MasaRepository
from app.repositories.urun_repo import UrunRepository
from app.repositories.auth_repo import AuthRepository
from app.schemas.orders import DurumGuncelleModel, SiparisDuzenleModel, SiparisOlusturModel
from app.schemas.orders import (
    MasaAktifSiparisResponse,
    SiparisDurumResponse,
    SiparisResponse,
)
from app.schemas.common import GenelBasariliResponse
from app.schemas.orders.dto import MasaTasimaSonucu, PricedOrderLine
from app.schemas.orders.entity import SiparisWithMasaEntity
from app.services.order_authorization import enforce_order_status_role, validate_order_state_transition
from app.database import db_transaction

# Masa taşıma yönlendirmeleri ve tekrarlı sipariş penceresi. Her ikisi de
# process belleğindedir: yeniden başlatmada sıfırlanır ve birden fazla worker
# arasında paylaşılmaz. Kalıcı hale getirmek yeni tablo (schema değişikliği)
# gerektirdiği için AGENTS.md §40 uyarınca kullanıcı onayına bırakıldı.
TABLE_MOVES_MAP = {}
_RECENT_ORDERS_CACHE = {}
_IDEMPOTENCY_WINDOW_SECONDS = 5
_IDEMPOTENCY_MAX_ENTRIES = 512


def _prune_idempotency_cache(now: float) -> None:
    """Drop expired entries so the cache cannot grow without bound.

    Without this the dictionary retained one SiparisResponse per distinct
    (masa, cihaz, sepet) combination for the entire process lifetime.
    """
    expired = [
        key
        for key, (ts, _response) in _RECENT_ORDERS_CACHE.items()
        if now - ts >= _IDEMPOTENCY_WINDOW_SECONDS
    ]
    for key in expired:
        _RECENT_ORDERS_CACHE.pop(key, None)

    # Hard ceiling for the pathological case of many distinct carts inside a
    # single window: evict oldest first.
    if len(_RECENT_ORDERS_CACHE) > _IDEMPOTENCY_MAX_ENTRIES:
        for key, _value in sorted(
            _RECENT_ORDERS_CACHE.items(), key=lambda kv: kv[1][0]
        )[: len(_RECENT_ORDERS_CACHE) - _IDEMPOTENCY_MAX_ENTRIES]:
            _RECENT_ORDERS_CACHE.pop(key, None)

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

    def _determine_initial_status(self, odeme_yontemi: PaymentMethod) -> tuple[str, str]:
        odeme_durumu = (
            PaymentStatus.PAID.value
            if odeme_yontemi == PaymentMethod.POS
            else PaymentStatus.PENDING.value
        )
        
        if odeme_yontemi == PaymentMethod.POS:
            siparis_durumu = OrderStatus.PAID_IN_KITCHEN.value
        elif odeme_yontemi == PaymentMethod.WAITER_AT_CASHIER:
            siparis_durumu = OrderStatus.WAITER_APPROVAL_PENDING.value
        else:
            siparis_durumu = OrderStatus.CASH_PENDING.value
            
        return odeme_durumu, siparis_durumu

    def _calculate_item_authoritative_price(
        self,
        u_info: dict,
        item,
        *,
        reject_underpriced_claim: bool = True,
    ) -> tuple[float, float]:
        base_price = float(u_info.get("fiyat", 0.0))
        calculated_unit_price = base_price
        note = (item.urun_notu or "").strip()

        if "Orta Boy" in note:
            calculated_unit_price += 40.0
        elif "Büyük Boy" in note:
            calculated_unit_price += 85.0
        elif "En Büyük Boy" in note:
            calculated_unit_price += 140.0

        if "1.5 Porsiyon" in note:
            calculated_unit_price += round(base_price * 0.40, 2)
        elif "2 Porsiyon" in note or "Çift Porsiyon" in note:
            calculated_unit_price += round(base_price * 0.80, 2)

        if "Manda Kaymağı" in note:
            calculated_unit_price += 35.0
        if "Maraş Dondurması" in note:
            calculated_unit_price += 40.0
        if "Çikolata Sosu" in note:
            calculated_unit_price += 25.0
        if "Antep Fıstığı" in note:
            calculated_unit_price += 30.0

        expected_unit_price = round(calculated_unit_price, 2)

        # Tamper signal only. The charged price is always expected_unit_price;
        # this guard merely rejects a client that openly claims a price below
        # the catalogue base. It is skipped on the staff edit path, where
        # discounts and ikram legitimately produce lower line prices.
        if reject_underpriced_claim and item.birim_fiyat < base_price:
            raise HTTPException(
                status_code=400,
                detail=f"'{u_info.get('urun_adi')}' için gönderilen birim fiyat ({item.birim_fiyat} TL) veritabanı taban fiyatından ({base_price} TL) düşük olamaz."
            )

        line_total = round(item.adet * expected_unit_price, 2)
        return expected_unit_price, line_total

    def _price_items_authoritatively(
        self,
        urunler: list,
        *,
        reject_underpriced_claim: bool = True,
    ) -> tuple[List[PricedOrderLine], float]:
        """Resolve, validate and price every line against the database.

        Each product is read exactly once. Unit prices come from ``Urunler`` and
        the order total is the sum of the recomputed lines, so neither
        ``birim_fiyat`` nor ``toplam_tutar`` from the request is ever trusted.
        """
        priced: List[PricedOrderLine] = []
        order_total = 0.0

        for item in urunler:
            u_info = self.urun_repo.get_by_id(item.urun_id)
            if not u_info:
                raise HTTPException(status_code=404, detail=f"Siparişteki Ürün #{item.urun_id} veritabanında bulunamadı!")

            if not u_info.get("aktif_mi", True):
                raise HTTPException(status_code=400, detail=f"'{u_info.get('urun_adi')}' isimli ürün satışa kapalıdır.")

            unit_price, line_total = self._calculate_item_authoritative_price(
                u_info, item, reject_underpriced_claim=reject_underpriced_claim
            )
            order_total += line_total

            priced.append({
                "urun_id": item.urun_id,
                "urun_adi": u_info.get("urun_adi", f"Ürün #{item.urun_id}"),
                "adet": item.adet,
                "birim_fiyat": unit_price,
                "urun_notu": item.urun_notu or "",
                "ara_toplam": line_total,
                "_stok_miktari": u_info.get("stok_miktari"),
            })

        return priced, round(order_total, 2)

    @staticmethod
    def _assert_stock_available(
        priced: List[PricedOrderLine],
        already_reserved: Optional[dict] = None,
    ) -> None:
        """Reject lines that exceed available stock.

        ``already_reserved`` holds quantities this same order has previously
        taken out of stock, so editing an order does not double-count what it
        already holds.
        """
        reserved = already_reserved or {}
        wanted: dict = {}
        for line in priced:
            wanted[line["urun_id"]] = wanted.get(line["urun_id"], 0) + line["adet"]

        seen: dict = {}
        for line in priced:
            seen.setdefault(line["urun_id"], line)

        for urun_id, requested in wanted.items():
            line = seen[urun_id]
            current_stock = line.get("_stok_miktari")
            if current_stock is None:
                continue
            available = current_stock + reserved.get(urun_id, 0)
            if available < requested:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{line['urun_adi']}' için yetersiz stok! (Mevcut stok: {available}, İstenen: {requested})"
                )

    def _deduct_stock_or_fail(self, urun_id: int, adet: int, urun_adi: str) -> None:
        """Take quantities out of stock, or abort the whole transaction.

        `_assert_stock_available` reads stock before the write, and under READ
        COMMITTED that value can be stale: two devices ordering the last unit
        both pass the pre-check. The atomic
        `WHERE id = ? AND stok_miktari >= ?` update then decrements for the
        first one and matches zero rows for the second. Without this check the
        loser's order was still created and confirmed to the customer while
        stock was never reduced - a silent oversell. Raising here rolls back the
        surrounding `db_transaction()`, so the order row goes with it.

        A driver that cannot report the row count returns -1; that is treated as
        "unknown" rather than "no rows", so an unsupported driver degrades to the
        previous behaviour instead of rejecting valid orders.
        """
        affected = self.urun_repo.update_stock(urun_id, adet)
        if affected == 0:
            raise HTTPException(
                status_code=409,
                detail=f"'{urun_adi}' stoğu az önce tükendi, siparişiniz alınamadı. Lütfen sepetinizi güncelleyip tekrar deneyin.",
            )

    def _restore_undelivered_stock(self, masa_id: int) -> List[int]:
        """Adisyon kapanırken teslim edilmemiş kalemleri stoğa geri verir.

        Stok sipariş anında düşülür. Bu bilinçli: aynı anda menüye bakan diğer
        masalar, henüz mutfağa gitmemiş bir siparişin adetlerini müsait
        sanmamalıdır (rezervasyon). Ancak rezervasyon tüketim değildir. Müşteri
        çorbasını almadan kalkarsa ya da kasa masayı zorla kapatırsa o çorba
        hiç servis edilmemiştir; stoktan kalıcı olarak düşmesi gerçek envanteri
        olduğundan az gösterir ve o adetler bir daha satılamaz.

        Yalnızca `teslim_edildi` olmayan kalemler iade edilir: teslim edilmiş
        ürün gerçekten tüketilmiştir.

        Çağıran zaten `db_transaction()` içinde olmalıdır.
        """
        restored: List[int] = []
        for row in self.siparis_repo.get_undelivered_details_for_masa(masa_id):
            adet = int(row.get("adet") or 0)
            urun_id = row.get("urun_id")
            if adet > 0 and urun_id is not None:
                self.urun_repo.restore_stock(urun_id, adet)
                restored.append(urun_id)
        return restored

    async def _publish_stock_changed(self, urun_ids) -> None:
        """Stoğu değişen ürünlerin güncel adedini tüm istemcilere duyurur.

        Menüdeki "Son X Adet" uyarısı sayfa açılışında ve 60 saniyelik
        tazelemede hesaplanıyordu, yani bir masa son 3 çorbayı sipariş ettiğinde
        diğer masaların ekranı bir dakikaya kadar eski kalıyordu. Stok adedi
        `GET /api/urunler` üzerinden zaten herkese açık olduğu için yayın oda
        ayrımı yapmadan yapılır.

        `db_transaction()` bloğunun DIŞINDAN çağrılmalıdır: amaç commit edilmiş
        değeri duyurmak.
        """
        unique_ids = list(dict.fromkeys(int(u) for u in urun_ids if u is not None))
        if not unique_ids:
            return

        stoklar = []
        for urun_id in unique_ids:
            urun = self.urun_repo.get_by_id(urun_id)
            if urun and urun.get("stok_miktari") is not None:
                stoklar.append(
                    {"urun_id": urun_id, "stok_miktari": int(urun["stok_miktari"])}
                )

        if stoklar:
            await event_bus.publish("stok_guncellendi", {"stoklar": stoklar})

    def _persist_order_items(self, siparis_id: int, priced: List[PricedOrderLine]) -> List[dict]:
        """Write the priced lines and take their quantities out of stock."""
        detaylar = []
        for line in priced:
            self.siparis_repo.create_siparis_detay(
                siparis_id,
                line["urun_id"],
                line["adet"],
                line["birim_fiyat"],
                line["urun_notu"],
                line["ara_toplam"],
            )
            self._deduct_stock_or_fail(line["urun_id"], line["adet"], line["urun_adi"])
            detaylar.append({k: v for k, v in line.items() if not k.startswith("_")})
        return detaylar

    async def _publish_order_events(
        self, data: SiparisOlusturModel, siparis_id: int, masa_no: str, order_dict: dict
    ) -> None:
        if data.odeme_yontemi == PaymentMethod.POS:
            await event_bus.publish("yeni_siparis", order_dict)

        await event_bus.publish(
            "masa_durumu_degisti",
            {"masa_id": data.masa_id, "durum": TableStatus.OCCUPIED.value},
        )
        await event_bus.publish("durum_guncellendi", order_dict)
        
        if data.odeme_yontemi == PaymentMethod.WAITER_AT_CASHIER:
            await event_bus.publish("garson_onay_talebi", {
                "siparis_id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa_no,
                "toplam_tutar": data.toplam_tutar,
                "siparis": order_dict
            })
        elif data.odeme_yontemi == PaymentMethod.CASH:
            await event_bus.publish("nakit_odeme_talebi", {
                "siparis_id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa_no,
                "toplam_tutar": data.toplam_tutar,
                "siparis": order_dict
            })

    async def create_siparis(
        self,
        data: SiparisOlusturModel,
        customer_session_id: Optional[int] = None,
    ) -> SiparisResponse:
        """Sipariş oluşturur.

        ``customer_session_id`` istek gövdesinden DEĞİL, doğrulanmış müşteri
        oturumundan gelir (controller `get_current_user_or_customer` sonucundan
        aktarır). Bu yüzden "bu siparişi kim verdi" bilgisi taklit edilemez;
        istemcinin gönderdiği ``device_id`` ise edilebilir ve bu amaçla
        kullanılmaz.
        """
        if data.device_id:
            banned = self.auth_repo.get_banned_device(data.device_id)
            if banned:
                raise HTTPException(status_code=403, detail="Erişiminiz engellendi. Cihazınız yasaklı.")

        items_key = tuple(sorted((item.urun_id, item.adet, (item.urun_notu or "").strip()) for item in data.urunler))
        # Oturum da anahtarın parçası: aynı masadaki iki kişi aynı anda aynı
        # ürünü söylediğinde bu iki ayrı siparişdir, tekrar gönderim değil.
        cache_key = (
            data.masa_id,
            data.device_id or "no-device",
            customer_session_id or 0,
            items_key,
        )
        now = time.time()
        _prune_idempotency_cache(now)
        if cache_key in _RECENT_ORDERS_CACHE:
            ts, prev_resp = _RECENT_ORDERS_CACHE[cache_key]
            if now - ts < _IDEMPOTENCY_WINDOW_SECONDS:
                return prev_resp

        with db_transaction():
            if data.masa_id in TABLE_MOVES_MAP:
                data.masa_id = TABLE_MOVES_MAP[data.masa_id]

            masa = self.masa_repo.get_by_id(data.masa_id)
            if not masa:
                raise HTTPException(status_code=404, detail="Geçersiz masa ID!")

            if masa.get('durum') == TableStatus.EMPTY.value:
                if not data.current_totp_token:
                    raise HTTPException(status_code=403, detail="Masa şu an BOŞ. İlk siparişi vermek için lütfen masadaki ekranın altında yazan 6 haneli güvenlik kodunu okutun.")

                totp_secret = masa.get("totp_secret")
                if not totp_secret or not verify_dynamic_token(data.masa_id, totp_secret, data.current_totp_token, mark_as_used=True):
                    raise HTTPException(status_code=403, detail="Geçersiz veya süresi dolmuş kod! Lütfen masadaki ekranda yazan güncel 6 haneli güvenlik kodunu girin.")

            # Ürünler tek geçişte okunur, doğrulanır ve fiyatlandırılır; toplam
            # istemciden gelen değere bakılmaksızın burada hesaplanır.
            priced_items, calculated_order_total = self._price_items_authoritatively(data.urunler)
            self._assert_stock_available(priced_items)
            data.toplam_tutar = calculated_order_total

            siparis_kodu = f"SIP-{uuid.uuid4().hex[:6].upper()}"
            odeme_durumu, siparis_durumu = self._determine_initial_status(data.odeme_yontemi)

            siparis_id = self.siparis_repo.create_siparis(
                data.masa_id,
                siparis_kodu,
                data.toplam_tutar,
                odeme_durumu,
                siparis_durumu,
                data.device_id,
                customer_session_id,
            )

            if not siparis_id:
                raise HTTPException(status_code=500, detail="Sipariş veritabanına eklenirken hata oluştu.")

            self.masa_repo.update_durum(data.masa_id, TableStatus.OCCUPIED.value)
            detaylar = self._persist_order_items(siparis_id, priced_items)
            clear_browsing_table(data.masa_id)

            full_order_dict = {
                "id": siparis_id,
                "masa_id": data.masa_id,
                "masa_no": masa['masa_no'],
                "siparis_kodu": siparis_kodu,
                "toplam_tutar": data.toplam_tutar,
                "odeme_yontemi": data.odeme_yontemi.value,
                "odeme_durumu": odeme_durumu,
                "siparis_durumu": siparis_durumu,
                "olusturma_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
                "garson_adi": None,
                "device_id": data.device_id,
                # Yanıt, siparişi veren oturuma dönüyor: kendi siparişi.
                "is_mine": customer_session_id is not None,
                "detaylar": detaylar
            }
            full_order = SiparisResponse.model_validate(full_order_dict)

        _RECENT_ORDERS_CACHE[cache_key] = (now, full_order)

        await self._publish_order_events(
            data,
            siparis_id,
            masa['masa_no'],
            full_order.model_dump(mode="json"),
        )
        await self._publish_stock_changed(line["urun_id"] for line in priced_items)
        return full_order

    def _map_to_siparis_response(
        self,
        order_row: SiparisWithMasaEntity,
        viewer_session_id: Optional[int] = None,
    ) -> SiparisResponse:
        """Veritabanı satırını dışarı verilebilir yanıt nesnesine çevirir.

        Satırın kendisi değiştirilmez: yanıt için ayrı bir sözlük kurulur.
        Entity içeri, response dışarı bakar ve ikisinin karışmaması,
        `customer_session_id` gibi alanların yanlışlıkla dışarı sızmamasını
        sağlar (`SiparisResponse` böyle bir alan tanımlamaz, pydantic de
        tanımsız alanları eler).
        """
        detaylar = self.siparis_repo.get_siparis_detaylari(order_row['id'])
        for d in detaylar:
            d['urun_notu'] = d.get('urun_notu') or ""

        olusturma_tarihi = order_row.get('olusturma_tarihi')
        if isinstance(olusturma_tarihi, datetime.datetime):
            olusturma_tarihi = olusturma_tarihi.strftime("%H:%M:%S")

        payload: dict = {
            **order_row,
            'detaylar': detaylar,
            'olusturma_tarihi': olusturma_tarihi,
        }

        # "Benim siparişim mi" kararı burada, veritabanındaki oturum kimliği ile
        # verilir. İstemci yalnızca token gönderir; hangi oturuma ait olduğu
        # sunucuda çözülür, bu yüzden bir cihaz başkasının siparişini kendi
        # siparişiymiş gibi gösteremez.
        #
        # `viewer_session_id` yoksa (personel yolları) alan None bırakılır:
        # "hayır" değil, "bu soru sorulmadı".
        if viewer_session_id is not None:
            kayitli = order_row.get('customer_session_id')
            payload['is_mine'] = (
                kayitli is not None and int(kayitli) == int(viewer_session_id)
            )

        return SiparisResponse.model_validate(payload)

    def get_siparisler(self, durum: Optional[str] = None, masa_id: Optional[int] = None) -> List[SiparisResponse]:
        siparisler = self.siparis_repo.get_all(durum, masa_id)
        return [self._map_to_siparis_response(s) for s in siparisler]

    def get_masa_aktif_siparis(
        self, masa_id: int, viewer_session_id: Optional[int] = None
    ) -> MasaAktifSiparisResponse:
        """Masanın açık adisyonu.

        Yanıt her zaman masanın TAMAMINI içerir: ödenecek tutar masanın
        tamamıdır ve müşteriye yalnızca kendi kalemlerini göstermek, hesap
        geldiğinde sürprize yol açar. Kişisel görünüm istemcide bir filtredir;
        hangi siparişin kime ait olduğu ise burada, sunucuda işaretlenir.
        """
        target_masa_id = masa_id
        is_redirected = False

        if masa_id in TABLE_MOVES_MAP:
            target_masa_id = TABLE_MOVES_MAP[masa_id]
            is_redirected = True

        siparisler = self.siparis_repo.get_all_active_by_masa_id(target_masa_id)
        alinan_tutar = self.siparis_repo.get_masa_tahsilat_toplami(target_masa_id)

        s_dtos = [
            self._map_to_siparis_response(s, viewer_session_id=viewer_session_id)
            for s in siparisler
        ]
        genel_toplam = sum(s.toplam_tutar for s in s_dtos if s.toplam_tutar)
        benim_toplamim = sum(
            s.toplam_tutar for s in s_dtos if s.is_mine and s.toplam_tutar
        )

        res = MasaAktifSiparisResponse(
            has_active=bool(s_dtos),
            siparisler=s_dtos,
            # Geriye dönük uyumluluk: eski istemciler tek siparişi bu alandan
            # okuyor. Masanın son siparişidir, listenin tamamı `siparisler`de.
            siparis=s_dtos[-1] if s_dtos else None,
            genel_toplam=genel_toplam,
            benim_toplamim=benim_toplamim if viewer_session_id is not None else None,
            alinan_tutar=alinan_tutar,
        )

        if is_redirected:
            t_table = self.masa_repo.get_by_id(target_masa_id)
            res.redirect_masa_id = target_masa_id
            res.redirect_masa_no = (
                t_table.get("masa_no", f"Masa {target_masa_id}")
                if t_table
                else f"Masa {target_masa_id}"
            )
        return res

    async def update_siparis_durumu(
        self,
        siparis_id: int,
        data: DurumGuncelleModel,
        principal: StaffPrincipal,
    ) -> SiparisDurumResponse:
        enforce_order_status_role(principal.role, data.yeni_durum)
        yeni_durum = data.yeni_durum.value
        # Denetim izi kimliği doğrulanmış personelden gelir; istekteki
        # garson_adi alanı bağlayıcı değildir.
        garson_adi = principal.username
        masa_bosaldi = False
        stok_degisen_urunler: List[int] = []

        with db_transaction():
            s_info = self.siparis_repo.get_by_id(siparis_id)
            if not s_info:
                raise HTTPException(status_code=404, detail="Sipariş bulunamadı!")

            validate_order_state_transition(s_info.get("siparis_durumu", ""), data.yeni_durum)

            if yeni_durum in [OrderAction.CASH_COLLECTED.value, OrderStatus.PAID_CLOSED.value]:
                self.siparis_repo.update_odeme_and_durum(
                    siparis_id,
                    PaymentStatus.PAID.value,
                    OrderStatus.DELIVERED.value,
                    garson_adi,
                )
                yeni_durum = OrderStatus.DELIVERED.value
            else:
                staff_name_statuses = {
                    OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
                    OrderStatus.DELIVERED.value,
                }
                self.siparis_repo.update_durum(
                    siparis_id,
                    yeni_durum,
                    garson_adi if yeni_durum in staff_name_statuses else None,
                )

            if yeni_durum == OrderStatus.CANCELLED.value:
                # İptal edilen siparişin adetleri stoğa geri döner. Bu olmadan
                # stok kalıcı olarak kayboluyordu: 20 adetlik sahte bir sipariş
                # iptal edilse bile o 20 adet bir daha satılamıyor, yani iptal
                # trol siparişin etkisini geri almıyordu.
                # İptal terminal bir durum (state machine `iptal` -> hiçbir şey),
                # bu yüzden iade en fazla bir kez çalışır.
                for detail in self.siparis_repo.get_siparis_detaylari(siparis_id):
                    adet = int(detail.get("adet") or 0)
                    if adet > 0:
                        self.urun_repo.restore_stock(detail["urun_id"], adet)
                        stok_degisen_urunler.append(detail["urun_id"])

            if yeni_durum in [OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value]:
                aktif_sayi = self.siparis_repo.get_active_count_for_masa(s_info['masa_id'])
                unpaid_sayi = self.siparis_repo.get_unpaid_count_for_masa(s_info['masa_id'])
                if aktif_sayi == 0 and unpaid_sayi == 0:
                    # Masa kendiliğinden boşalıyor: bu da bir adisyon kapanışıdır
                    # ve kasadan "Masayı Temizle" ile aynı sonucu doğurmalıdır.
                    self.masa_repo.update_durum(s_info['masa_id'], TableStatus.EMPTY.value)
                    stok_degisen_urunler.extend(
                        self._close_masa_session(s_info['masa_id'])
                    )
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
                odeme_durumu=updated_order.get("odeme_durumu", PaymentStatus.PAID.value),
                garson_adi=garson_adi,
                guncelleme_tarihi=datetime.datetime.now().strftime("%H:%M:%S"),
                siparis=s_dto
            )

        payload_dict = event_payload.model_dump(mode="json")
        s_dto_dict = s_dto.model_dump(mode="json")

        if masa_bosaldi:
            await event_bus.publish(
                "masa_durumu_degisti",
                {"masa_id": s_info['masa_id'], "durum": TableStatus.EMPTY.value},
            )

        if data.yeni_durum.value in [
            OrderAction.CASH_COLLECTED.value,
            OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
        ]:
            await event_bus.publish("yeni_siparis", s_dto_dict)
            await event_bus.publish("nakit_odendi", payload_dict)

        await event_bus.publish("durum_guncellendi", payload_dict)
        await self._publish_stock_changed(stok_degisen_urunler)
        return event_payload

    def _close_masa_session(self, masa_id: int) -> List[int]:
        """Masanın adisyonunu kapatır: siparişler, tahsilatlar, oturumlar, presence.

        Bu, iki müşteri grubu arasındaki sınırdır. Projede ayrı bir "adisyon"
        varlığı yok; masanın `bos` durumuna döndüğü an bir grubun hesabını
        diğerinden ayıran tek olay. Bu yüzden `bos` durumuna giden iki yolun da
        -- kasanın masayı temizlemesi ve her şey teslim edilip ödendiğinde
        masanın kendiliğinden boşalması -- birebir aynı işi yapması gerekir.

        Önceden yalnızca kasa yolu oturumları iptal edip siparişleri kapatıyordu.
        Kendiliğinden boşalmada önceki müşterinin oturumu ömrü bitene kadar
        geçerli kalıyor, teslim edilmiş siparişleri de masaya sonradan oturan
        gruba "aktif" olarak dönüyordu.

        Çağıran zaten `db_transaction()` içinde olmalıdır.

        Stoğu değişen ürünlerin id'lerini döner; çağıran bunları commit sonrası
        duyurur.
        """
        # Sıra önemli: `clear_active_orders_for_masa` açık siparişleri
        # `odendi_kapatildi` yaptığı an "teslim edilmemiş" bilgisi kaybolur.
        restored = self._restore_undelivered_stock(masa_id)
        self.siparis_repo.clear_active_orders_for_masa(masa_id)
        self.siparis_repo.close_tahsilatlar_for_masa(masa_id)
        self.auth_repo.revoke_all_sessions_for_masa(masa_id)
        clear_browsing_table(masa_id)
        TABLE_MOVES_MAP.pop(masa_id, None)
        for k, v in list(TABLE_MOVES_MAP.items()):
            if v == masa_id:
                TABLE_MOVES_MAP.pop(k, None)
        return restored

    async def clear_masa(self, masa_id: int) -> None:
        with db_transaction():
            self.masa_repo.update_durum(masa_id, TableStatus.EMPTY.value)
            stok_degisen_urunler = self._close_masa_session(masa_id)

        event_payload = {"masa_id": masa_id, "durum": TableStatus.EMPTY.value}
        await event_bus.publish("masa_durumu_degisti", event_payload)
        await event_bus.publish("masa_temizlendi", {"masa_id": masa_id})
        await event_bus.publish(
            "durum_guncellendi",
            {"masa_id": masa_id, "yeni_durum": TableStatus.EMPTY.value},
        )
        await self._publish_stock_changed(stok_degisen_urunler)

    async def update_siparis_items(
        self,
        siparis_id: int,
        data: SiparisDuzenleModel,
        principal: StaffPrincipal,
    ) -> SiparisResponse:
        garson_adi = principal.username

        with db_transaction():
            s_info = self.siparis_repo.get_by_id(siparis_id)
            if not s_info:
                raise HTTPException(status_code=404, detail="Sipariş bulunamadı!")

            current_status = (s_info.get("siparis_durumu") or "").strip().lower()
            if current_status in (OrderStatus.CANCELLED.value, OrderStatus.PAID_CLOSED.value):
                raise HTTPException(
                    status_code=409,
                    detail="Sonlandırılmış (iptal/kapatıldı) bir siparişin kalemleri değiştirilemez.",
                )

            # Kalemler ve toplam sunucuda yeniden hesaplanır. İstemcinin
            # gönderdiği birim_fiyat ve toplam_tutar bağlayıcı değildir.
            # İskonto/ikram akışları taban fiyatın altına inebildiği için
            # taban fiyat iddiası bu yolda reddedilmez.
            priced_items, authoritative_total = self._price_items_authoritatively(
                data.urunler, reject_underpriced_claim=False
            )

            # Siparişin hâlihazırda stoktan düşürdüğü adetler yeni talebe mahsup
            # edilir; aksi halde aynı sipariş kendi stoğuyla çakışırdı.
            previous_details = self.siparis_repo.get_siparis_detaylari(siparis_id)
            already_reserved: dict = {}
            for detail in previous_details:
                urun_id = detail["urun_id"]
                already_reserved[urun_id] = already_reserved.get(urun_id, 0) + int(detail["adet"] or 0)
            self._assert_stock_available(priced_items, already_reserved)

            self.siparis_repo.replace_siparis_items(
                siparis_id, authoritative_total, priced_items, garson_adi
            )

            # Stok yalnızca net fark kadar hareket eder.
            requested: dict = {}
            names: dict = {}
            for line in priced_items:
                requested[line["urun_id"]] = requested.get(line["urun_id"], 0) + line["adet"]
                names.setdefault(line["urun_id"], line["urun_adi"])
            for urun_id in set(already_reserved) | set(requested):
                delta = requested.get(urun_id, 0) - already_reserved.get(urun_id, 0)
                if delta > 0:
                    self._deduct_stock_or_fail(
                        urun_id, delta, names.get(urun_id, f"Ürün #{urun_id}")
                    )
                elif delta < 0:
                    self.urun_repo.restore_stock(urun_id, -delta)

            updated_order = self.siparis_repo.get_by_id(siparis_id)
            s_dto = self._map_to_siparis_response(updated_order)

            event_payload = {
                "siparis_id": siparis_id,
                "masa_id": s_info['masa_id'],
                "masa_no": s_info['masa_no'],
                "yeni_durum": s_info.get(
                    "siparis_durumu", OrderStatus.WAITER_APPROVAL_PENDING.value
                ),
                "odeme_durumu": s_info.get("odeme_durumu", PaymentStatus.PENDING.value),
                "garson_adi": garson_adi,
                "guncelleme_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
                "siparis": s_dto.model_dump(mode="json")
            }

        await event_bus.publish("durum_guncellendi", event_payload)
        await self._publish_stock_changed(set(already_reserved) | set(requested))
        return s_dto

    async def move_masa(self, from_masa_id: int, to_masa_id: int) -> None:
        with db_transaction():
            self.siparis_repo.move_orders_between_masalar(from_masa_id, to_masa_id)
            from_masa = self.masa_repo.get_by_id(from_masa_id)
            from_masa_no = from_masa.get("masa_no", f"Masa {from_masa_id}") if from_masa else f"Masa {from_masa_id}"
            to_masa = self.masa_repo.get_by_id(to_masa_id)
            to_masa_no = to_masa.get("masa_no", f"Masa {to_masa_id}") if to_masa else f"Masa {to_masa_id}"
            
            self.masa_repo.update_durum(to_masa_id, TableStatus.OCCUPIED.value)
            self.masa_repo.update_durum(from_masa_id, TableStatus.EMPTY.value)
            clear_browsing_table(from_masa_id)
            TABLE_MOVES_MAP[from_masa_id] = to_masa_id
        
        event_payload = {
            "from_masa_id": from_masa_id,
            "from_masa_no": from_masa_no,
            "to_masa_id": to_masa_id,
            "to_masa_no": to_masa_no,
            "is_move": True
        }
        await event_bus.publish("masa_tasindi", event_payload)
        await event_bus.publish(
            "masa_durumu_degisti",
            {"masa_id": to_masa_id, "durum": TableStatus.OCCUPIED.value, "is_move": True},
        )
        await event_bus.publish("durum_guncellendi", event_payload)

    async def move_masa_items(
        self, from_masa_id: int, to_masa_id: int, detay_ids: List[int]
    ) -> MasaTasimaSonucu:
        """Adisyonun seçilen kalemlerini başka bir masaya aktarır.

        Kasadaki "Seçili Ürünleri Taşı" sekmesi bugüne kadar bir yanılsamaydı:
        onay düğmesi seçimden bağımsız olarak `/api/masalar/move` çağırıyor,
        yani her zaman masanın TAMAMINI taşıyordu. Kutucuklar hiçbir yere
        gönderilmiyordu.

        Kalem taşıma iki şekilde olur:

        - Bir siparişin bütün kalemleri seçilmişse başlık olduğu gibi taşınır.
          Fiş numarası, ödeme durumu ve geçmişi korunur.
        - Bir siparişin yalnızca bir kısmı seçilmişse sipariş BÖLÜNÜR: hedef
          masada aynı ödeme/sipariş durumuna sahip yeni bir başlık açılır,
          seçilen satırlar oraya taşınır ve iki başlığın toplamı da kalemlerden
          yeniden hesaplanır.

        Stok hareket etmez; kalemler yalnızca masa değiştirir.
        """
        if from_masa_id == to_masa_id:
            raise HTTPException(status_code=400, detail="Hedef masa kaynak masayla aynı olamaz.")

        unique_ids = list(dict.fromkeys(int(i) for i in detay_ids))
        if not unique_ids:
            raise HTTPException(status_code=400, detail="Taşınacak ürün seçilmedi.")

        rows = self.siparis_repo.get_movable_detail_rows(from_masa_id)
        if not rows:
            raise HTTPException(status_code=404, detail="Bu masada taşınabilir sipariş kalemi yok.")

        by_id = {int(row["id"]): row for row in rows if row.get("id") is not None}

        # Yalnızca id bilmek yetki değildir: gönderilen her satırın gerçekten
        # kaynak masaya ait olduğu doğrulanır. Aksi halde bir kasiyer, başka bir
        # masanın kalem id'sini göndererek o masanın hesabını bölebilirdi.
        unknown = [i for i in unique_ids if i not in by_id]
        if unknown:
            raise HTTPException(
                status_code=403,
                detail="Seçilen kalemlerden bazıları bu masaya ait değil.",
            )

        # Tamamı seçilmişse bu zaten bir masa taşımadır: müşteri oturumlarının
        # ve yönlendirmenin de taşınması için tek yol kullanılır.
        if len(unique_ids) == len(by_id):
            await self.move_masa(from_masa_id, to_masa_id)
            return {"moved_detail_count": len(unique_ids), "full_move": True}

        selected_by_order: dict = {}
        for detay_id in unique_ids:
            row = by_id[detay_id]
            selected_by_order.setdefault(int(row["siparis_id"]), []).append(detay_id)

        total_by_order: dict = {}
        for row in rows:
            total_by_order[int(row["siparis_id"])] = total_by_order.get(int(row["siparis_id"]), 0) + 1

        with db_transaction():
            for siparis_id, secilen_ids in selected_by_order.items():
                if len(secilen_ids) == total_by_order.get(siparis_id, 0):
                    self.siparis_repo.move_single_order_to_masa(siparis_id, to_masa_id)
                    continue

                kaynak = self.siparis_repo.get_by_id(siparis_id)
                if not kaynak:
                    raise HTTPException(status_code=404, detail="Taşınacak sipariş bulunamadı.")

                yeni_kod = f"SIP-{uuid.uuid4().hex[:6].upper()}"
                yeni_siparis_id = self.siparis_repo.create_siparis(
                    to_masa_id,
                    yeni_kod,
                    0.0,
                    kaynak.get("odeme_durumu", PaymentStatus.PENDING.value),
                    kaynak.get("siparis_durumu", OrderStatus.WAITER_APPROVAL_PENDING.value),
                    kaynak.get("device_id"),
                )
                if not yeni_siparis_id:
                    raise HTTPException(
                        status_code=500, detail="Taşıma için yeni fiş oluşturulamadı."
                    )

                self.siparis_repo.reassign_detaylar_to_siparis(secilen_ids, yeni_siparis_id)
                self.siparis_repo.sync_siparis_total(yeni_siparis_id)
                self.siparis_repo.sync_siparis_total(siparis_id)

            self.masa_repo.update_durum(to_masa_id, TableStatus.OCCUPIED.value)

        # Kısmi taşımada kaynak masada hâlâ kalem var, bu yüzden masa `dolu`
        # kalır ve müşteri oturumları da yerinde bırakılır: taşınan hesap, orada
        # oturmaya devam eden müşterileri kapsamaz.
        await event_bus.publish(
            "masa_durumu_degisti",
            {"masa_id": to_masa_id, "durum": TableStatus.OCCUPIED.value},
        )
        await event_bus.publish("durum_guncellendi", {"masa_id": from_masa_id})
        await event_bus.publish("durum_guncellendi", {"masa_id": to_masa_id})
        return {"moved_detail_count": len(unique_ids), "full_move": False}

    def get_all_masa_tahsilatlari(self) -> Dict[str, float]:
        """Aktif tahsilat toplamlarını masa id'sine göre döner."""
        return {
            str(masa["id"]): self.siparis_repo.get_masa_tahsilat_toplami(masa["id"])
            for masa in self.masa_repo.get_all()
        }

    async def add_tahsilat(
        self, masa_id: int, tutar: float, odeme_yontemi: str
    ) -> GenelBasariliResponse:
        with db_transaction():
            self.siparis_repo.add_masa_tahsilat(masa_id, tutar, odeme_yontemi)
            
        event_payload = {"masa_id": masa_id}
        await event_bus.publish("durum_guncellendi", event_payload)
        return GenelBasariliResponse(status="success", message="Tahsilat eklendi.")
