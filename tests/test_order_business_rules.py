import unittest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.enums import OrderAction, OrderStatus, PaymentMethod
from app.schemas.orders import SiparisItemModel, SiparisOlusturModel
from app.services.order_authorization import validate_order_state_transition
from app.services.siparis_service import SiparisService


class TestOrderBusinessRules(unittest.TestCase):

    def setUp(self):
        self.mock_siparis_repo = MagicMock()
        self.mock_masa_repo = MagicMock()
        self.mock_urun_repo = MagicMock()
        self.mock_auth_repo = MagicMock()
        self.service = SiparisService(
            siparis_repo=self.mock_siparis_repo,
            masa_repo=self.mock_masa_repo,
            urun_repo=self.mock_urun_repo,
            auth_repo=self.mock_auth_repo,
        )

    def test_price_recalculation_and_underpay_rejection(self):
        db_product = {"id": 1, "urun_adi": "Köfte", "fiyat": 100.0, "stok_miktari": 50, "aktif_mi": True}
        self.mock_urun_repo.get_by_id.return_value = db_product

        item = SiparisItemModel(urun_id=1, adet=2, birim_fiyat=10.0, urun_notu="")

        with self.assertRaises(HTTPException) as ctx:
            self.service._calculate_item_authoritative_price(db_product, item)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("düşük olamaz", ctx.exception.detail)

    def test_authoritative_price_with_option_deltas(self):
        db_product = {"id": 2, "urun_adi": "Karışık Pizza", "fiyat": 150.0, "stok_miktari": 20, "aktif_mi": True}
        self.mock_urun_repo.get_by_id.return_value = db_product

        item = SiparisItemModel(urun_id=2, adet=1, birim_fiyat=190.0, urun_notu="Orta Boy, 🥤 Pipetli Olsun")
        unit_price, line_total = self.service._calculate_item_authoritative_price(db_product, item)

        self.assertEqual(unit_price, 190.0) # 150 + 40
        self.assertEqual(line_total, 190.0)

    def test_inactive_product_rejection(self):
        db_product = {"id": 3, "urun_adi": "Eski Çorba", "fiyat": 50.0, "stok_miktari": 10, "aktif_mi": False}
        self.mock_urun_repo.get_by_id.return_value = db_product

        data = SiparisOlusturModel(
            masa_id=1,
            toplam_tutar=50.0,
            odeme_yontemi=PaymentMethod.POS,
            urunler=[SiparisItemModel(urun_id=3, adet=1, birim_fiyat=50.0, urun_notu="")],
        )

        with self.assertRaises(HTTPException) as ctx:
            self.service._price_items_authoritatively(data.urunler)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("satışa kapalıdır", ctx.exception.detail)

    def test_insufficient_stock_rejection(self):
        db_product = {"id": 4, "urun_adi": "Kızarmış Patates", "fiyat": 40.0, "stok_miktari": 2, "aktif_mi": True}
        self.mock_urun_repo.get_by_id.return_value = db_product

        data = SiparisOlusturModel(
            masa_id=1,
            toplam_tutar=200.0,
            odeme_yontemi=PaymentMethod.POS,
            urunler=[SiparisItemModel(urun_id=4, adet=5, birim_fiyat=40.0, urun_notu="")],
        )

        with self.assertRaises(HTTPException) as ctx:
            priced, _total = self.service._price_items_authoritatively(data.urunler)
            self.service._assert_stock_available(priced)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("yetersiz stok", ctx.exception.detail)

    def test_legal_state_transitions(self):
        try:
            validate_order_state_transition(OrderStatus.PAID_IN_KITCHEN.value, OrderStatus.PREPARING)
            validate_order_state_transition(OrderStatus.PREPARING.value, OrderStatus.READY)
            validate_order_state_transition(OrderStatus.READY.value, OrderStatus.DELIVERED)
            validate_order_state_transition(OrderStatus.DELIVERED.value, OrderStatus.PAID_CLOSED)
        except HTTPException:
            self.fail("Legal state transitions raised unexpected HTTPException!")

    def test_illegal_state_transitions(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_order_state_transition(OrderStatus.DELIVERED.value, OrderStatus.PREPARING)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("durumuna geçirilemez", ctx.exception.detail)

        with self.assertRaises(HTTPException) as ctx2:
            validate_order_state_transition(OrderStatus.CANCELLED.value, OrderStatus.READY)
        self.assertEqual(ctx2.exception.status_code, 400)
        self.assertIn("sonlandırılmış durumdadır", ctx2.exception.detail)


class TestStateMachineFailsClosed(unittest.TestCase):
    """Haritada olmayan bir durum tüm geçişlere izin vermemelidir.

    Önceki kod `allowed is not None` kontrolü yaptığı için eşlenmemiş tek bir
    durum değeri o sipariş adına durum makinesini tamamen devre dışı bırakıyordu.
    """

    def test_unknown_status_is_rejected_instead_of_allowing_everything(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_order_state_transition("bilinmeyen_durum", OrderStatus.DELIVERED)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("bilinmeyen bir durumda", ctx.exception.detail)

    def test_empty_status_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_order_state_transition("", OrderStatus.PREPARING)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_every_order_status_is_mapped(self):
        """Drift koruması: enum'a yeni durum eklenirse harita da güncellenmeli."""
        from app.services.order_authorization import _ALLOWED_STATE_TRANSITIONS

        unmapped = [s.value for s in OrderStatus if s.value not in _ALLOWED_STATE_TRANSITIONS]
        self.assertEqual(unmapped, [], f"Geçiş haritasında eksik durum(lar): {unmapped}")

    def test_legacy_payment_pending_status_has_legal_transitions(self):
        try:
            validate_order_state_transition(
                OrderStatus.PAYMENT_PENDING.value, OrderStatus.CANCELLED
            )
        except HTTPException:
            self.fail("Legacy 'odeme_bekliyor' durumu iptal edilebilmeli")


class TestIdempotencyCacheEviction(unittest.TestCase):
    """Tekrarlı sipariş önbelleği süresiz büyümemelidir."""

    def setUp(self):
        from app.services import siparis_service
        self.mod = siparis_service
        self._original = dict(siparis_service._RECENT_ORDERS_CACHE)
        self.addCleanup(self._restore)
        siparis_service._RECENT_ORDERS_CACHE.clear()

    def _restore(self):
        self.mod._RECENT_ORDERS_CACHE.clear()
        self.mod._RECENT_ORDERS_CACHE.update(self._original)

    def test_expired_entries_are_dropped(self):
        now = 1_000.0
        window = self.mod._IDEMPOTENCY_WINDOW_SECONDS
        self.mod._RECENT_ORDERS_CACHE["eski"] = (now - window - 1, "yanit")
        self.mod._RECENT_ORDERS_CACHE["yeni"] = (now, "yanit")

        self.mod._prune_idempotency_cache(now)

        self.assertNotIn("eski", self.mod._RECENT_ORDERS_CACHE)
        self.assertIn("yeni", self.mod._RECENT_ORDERS_CACHE)

    def test_cache_is_capped_even_inside_one_window(self):
        now = 1_000.0
        limit = self.mod._IDEMPOTENCY_MAX_ENTRIES
        for i in range(limit + 50):
            # Hepsi taze; yalnizca tavan kurali devreye girmeli.
            self.mod._RECENT_ORDERS_CACHE[f"k{i}"] = (now + i * 0.001, "yanit")

        self.mod._prune_idempotency_cache(now)

        self.assertLessEqual(len(self.mod._RECENT_ORDERS_CACHE), limit)


if __name__ == "__main__":
    unittest.main()
