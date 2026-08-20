"""Cancelling an order must return its quantities to stock.

`restore_stock` was only ever called on the staff edit path, so a cancelled
order kept its stock deduction forever. That turned the "order the maximum of
everything" nuisance into permanent damage: even after the waiter cancelled the
fake order, the stock it consumed could never be sold again.
"""

import asyncio
import contextlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.auth.models import StaffPrincipal
from app.enums import OrderAction, OrderStatus, PaymentStatus, UserRole
from app.schemas.orders import MAX_LINE_QUANTITY, DurumGuncelleModel, SiparisItemModel
from app.services import siparis_service as siparis_service_module
from app.services.siparis_service import SiparisService


@contextlib.contextmanager
def _no_transaction():
    yield None


class CancelRestoresStockTests(unittest.TestCase):

    def setUp(self):
        siparis_service_module.TABLE_MOVES_MAP.clear()
        self.addCleanup(siparis_service_module.TABLE_MOVES_MAP.clear)

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
        self.principal = StaffPrincipal(user_id=1, username="admin", role=UserRole.ADMIN)

        self.mock_siparis_repo.get_by_id.return_value = {
            "id": 55,
            "masa_id": 7,
            "masa_no": "Masa 7",
            "siparis_kodu": "SIP-TROLL1",
            "toplam_tutar": 1000.0,
            "odeme_durumu": PaymentStatus.PENDING.value,
            "siparis_durumu": OrderStatus.WAITER_APPROVAL_PENDING.value,
            "olusturma_tarihi": None,
            "garson_adi": None,
            "device_id": "device-troll",
        }
        self.mock_siparis_repo.get_siparis_detaylari.return_value = [
            {"urun_id": 3, "urun_adi": "Ezogelin Çorbası", "adet": 20,
             "birim_fiyat": 40.0, "urun_notu": "", "ara_toplam": 800.0},
            {"urun_id": 9, "urun_adi": "Ayran", "adet": 5,
             "birim_fiyat": 40.0, "urun_notu": "", "ara_toplam": 200.0},
        ]
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 0

        patcher_tx = patch("app.services.siparis_service.db_transaction", _no_transaction)
        patcher_bus = patch("app.services.siparis_service.event_bus")
        patcher_browsing = patch("app.services.siparis_service.clear_browsing_table")
        for patcher in (patcher_tx, patcher_bus, patcher_browsing):
            self.addCleanup(patcher.stop)
        patcher_tx.start()
        patcher_bus.start().publish = AsyncMock()
        patcher_browsing.start()

    def _transition(self, target):
        data = DurumGuncelleModel(yeni_durum=target)
        return asyncio.run(self.service.update_siparis_durumu(55, data, self.principal))

    def test_cancelling_returns_every_line_to_stock(self):
        self._transition(OrderStatus.CANCELLED.value)

        restored = {
            call.args[0]: call.args[1]
            for call in self.mock_urun_repo.restore_stock.call_args_list
        }
        self.assertEqual(restored, {3: 20, 9: 5})

    def test_delivering_does_not_return_stock(self):
        """A delivered order was actually consumed; its stock stays deducted."""
        self.mock_siparis_repo.get_by_id.return_value["siparis_durumu"] = (
            OrderStatus.READY.value
        )

        self._transition(OrderStatus.DELIVERED.value)

        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_cash_collection_does_not_return_stock(self):
        self.mock_siparis_repo.get_by_id.return_value["siparis_durumu"] = (
            OrderStatus.CASH_PENDING.value
        )

        self._transition(OrderAction.CASH_COLLECTED.value)

        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_an_already_cancelled_order_cannot_be_cancelled_again(self):
        """The state machine makes double restoration impossible."""
        self.mock_siparis_repo.get_by_id.return_value["siparis_durumu"] = (
            OrderStatus.CANCELLED.value
        )

        with self.assertRaises(HTTPException) as ctx:
            self._transition(OrderStatus.CANCELLED.value)

        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_a_zero_quantity_line_is_skipped(self):
        self.mock_siparis_repo.get_siparis_detaylari.return_value = [
            {"urun_id": 3, "urun_adi": "Çorba", "adet": 0,
             "birim_fiyat": 40.0, "urun_notu": "", "ara_toplam": 0.0},
        ]

        self._transition(OrderStatus.CANCELLED.value)

        self.mock_urun_repo.restore_stock.assert_not_called()


class LineQuantityLimitTests(unittest.TestCase):
    """One request must not be able to drain the whole inventory."""

    def test_the_cap_is_above_any_realistic_table_order(self):
        self.assertGreaterEqual(MAX_LINE_QUANTITY, 20)

    def test_a_quantity_at_the_cap_is_accepted(self):
        item = SiparisItemModel(urun_id=1, adet=MAX_LINE_QUANTITY, birim_fiyat=10.0)
        self.assertEqual(item.adet, MAX_LINE_QUANTITY)

    def test_a_quantity_past_the_cap_is_rejected(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            SiparisItemModel(urun_id=1, adet=MAX_LINE_QUANTITY + 1, birim_fiyat=10.0)

    def test_an_absurd_quantity_is_rejected(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            SiparisItemModel(urun_id=1, adet=2_000_000_000, birim_fiyat=10.0)

    def test_zero_and_negative_are_still_rejected(self):
        from pydantic import ValidationError

        for bad in (0, -1):
            with self.subTest(adet=bad):
                with self.assertRaises(ValidationError):
                    SiparisItemModel(urun_id=1, adet=bad, birim_fiyat=10.0)


if __name__ == "__main__":
    unittest.main()
