"""Regression tests for the stock oversell race (2026-08-17 finding 1).

`_assert_stock_available` reads stock before the write. Under READ COMMITTED
that value goes stale, so two devices ordering the last unit both pass the
pre-check. The atomic `WHERE id = ? AND stok_miktari >= ?` update then
decrements for the winner and matches **zero rows** for the loser.

Before this guard nobody inspected the affected row count, so the loser's order
was still created and confirmed to the customer while stock was never reduced.
These tests pin the corrected behaviour: zero affected rows aborts the
transaction with HTTP 409.
"""

import asyncio
import contextlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.auth.models import StaffPrincipal
from app.database import db_transaction
from app.enums import OrderStatus, PaymentMethod, TableStatus, UserRole
from app.repositories.urun_repo import UrunRepository
from app.schemas.orders import (
    SiparisDuzenleModel,
    SiparisItemModel,
    SiparisOlusturModel,
)
from app.services import siparis_service as siparis_service_module
from app.services.siparis_service import SiparisService


@contextlib.contextmanager
def _no_transaction():
    yield None


class StockRepositoryContractTests(unittest.TestCase):
    """The repository must use the atomic query and report the row count."""

    def setUp(self):
        self.db = MagicMock()
        self.repo = UrunRepository(db=self.db)

    def test_deduction_is_conditional_and_returns_the_affected_rows(self):
        self.db.execute_update.return_value = 1

        affected = self.repo.update_stock(7, 3)

        self.assertEqual(affected, 1)
        self.db.execute_update.assert_called_once()
        query, params = self.db.execute_update.call_args[0]
        self.assertIn("stok_miktari = stok_miktari - ?", query)
        self.assertIn("WHERE id = ? AND stok_miktari >= ?", query)
        self.assertEqual(params, (3, 7, 3))

    def test_deduction_does_not_use_the_rowcount_losing_writer(self):
        """`execute_non_query` reads SCOPE_IDENTITY() and discards rowcount."""
        self.db.execute_update.return_value = 1

        self.repo.update_stock(7, 1)

        self.db.execute_non_query.assert_not_called()

    def test_zero_rows_is_reported_as_zero(self):
        self.db.execute_update.return_value = 0
        self.assertEqual(self.repo.update_stock(7, 1), 0)


class TransactionRollbackTests(unittest.TestCase):
    """A rejected order must not leave its row behind."""

    def test_db_transaction_rolls_back_when_the_body_raises(self):
        conn = MagicMock()
        with patch("app.database.get_db_connection", return_value=(conn, "fake")):
            with self.assertRaises(HTTPException):
                with db_transaction():
                    raise HTTPException(status_code=409, detail="stok tükendi")

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
        conn.close.assert_called_once()

    def test_db_transaction_commits_on_success(self):
        conn = MagicMock()
        with patch("app.database.get_db_connection", return_value=(conn, "fake")):
            with db_transaction():
                pass

        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()


class OrderCreateStockGuardTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        siparis_service_module._RECENT_ORDERS_CACHE.clear()
        self.addCleanup(siparis_service_module._RECENT_ORDERS_CACHE.clear)
        siparis_service_module.TABLE_MOVES_MAP.clear()
        self.addCleanup(siparis_service_module.TABLE_MOVES_MAP.clear)

        self.mock_siparis_repo = MagicMock()
        self.mock_masa_repo = MagicMock()
        self.mock_urun_repo = MagicMock()
        self.mock_auth_repo = MagicMock()

        self.mock_auth_repo.get_banned_device.return_value = None
        self.mock_siparis_repo.create_siparis.return_value = 900
        self.mock_masa_repo.get_by_id.return_value = {
            "id": 5,
            "masa_no": "Masa 5",
            "durum": TableStatus.OCCUPIED.value,
            "totp_secret": "x" * 32,
        }
        # Ön kontrol geçsin diye stok bol görünüyor; yarışı kaybetmeyi
        # update_stock'un dönüş değeri temsil ediyor.
        self.mock_urun_repo.get_by_id.return_value = {
            "id": 1,
            "urun_adi": "Künefe",
            "fiyat": 100.0,
            "stok_miktari": 5,
            "aktif_mi": True,
        }

        self.service = SiparisService(
            siparis_repo=self.mock_siparis_repo,
            masa_repo=self.mock_masa_repo,
            urun_repo=self.mock_urun_repo,
            auth_repo=self.mock_auth_repo,
        )

        patcher_tx = patch("app.services.siparis_service.db_transaction", _no_transaction)
        patcher_bus = patch("app.services.siparis_service.event_bus")
        patcher_browsing = patch("app.services.siparis_service.clear_browsing_table")
        for patcher in (patcher_tx, patcher_bus, patcher_browsing):
            self.addCleanup(patcher.stop)
        patcher_tx.start()
        patcher_bus.start().publish = AsyncMock()
        patcher_browsing.start()

    def _order(self, adet=1, device_id="device-1"):
        return SiparisOlusturModel(
            masa_id=5,
            toplam_tutar=100.0,
            odeme_yontemi=PaymentMethod.POS,
            urunler=[
                SiparisItemModel(urun_id=1, adet=adet, birim_fiyat=100.0, urun_notu="")
            ],
            device_id=device_id,
        )

    async def test_lost_race_rejects_the_order_instead_of_overselling(self):
        self.mock_urun_repo.update_stock.return_value = 0

        with self.assertRaises(HTTPException) as ctx:
            await self.service.create_siparis(self._order())

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Künefe", ctx.exception.detail)
        self.mock_urun_repo.update_stock.assert_called_once_with(1, 1)

    async def test_a_rejected_order_is_not_cached_as_a_duplicate(self):
        """The idempotency cache must not remember a failed attempt."""
        self.mock_urun_repo.update_stock.return_value = 0
        with self.assertRaises(HTTPException):
            await self.service.create_siparis(self._order())

        self.assertEqual(len(siparis_service_module._RECENT_ORDERS_CACHE), 0)

        # Stok geri geldiğinde aynı sepet tekrar denenebilmeli.
        self.mock_urun_repo.update_stock.return_value = 1
        order = await self.service.create_siparis(self._order())
        self.assertEqual(order.id, 900)

    async def test_winning_the_race_creates_the_order(self):
        self.mock_urun_repo.update_stock.return_value = 1

        order = await self.service.create_siparis(self._order())

        self.assertEqual(order.id, 900)
        self.mock_urun_repo.update_stock.assert_called_once_with(1, 1)

    async def test_unknown_row_count_does_not_reject_the_order(self):
        """A driver that cannot report rowcount returns -1, not 0."""
        self.mock_urun_repo.update_stock.return_value = -1

        order = await self.service.create_siparis(self._order())

        self.assertEqual(order.id, 900)


class OrderEditStockGuardTests(unittest.TestCase):

    def setUp(self):
        self.mock_siparis_repo = MagicMock()
        self.mock_masa_repo = MagicMock()
        self.mock_urun_repo = MagicMock()
        self.mock_auth_repo = MagicMock()

        self.mock_urun_repo.get_by_id.return_value = {
            "id": 1,
            "urun_adi": "Künefe",
            "fiyat": 100.0,
            "stok_miktari": 5,
            "aktif_mi": True,
        }
        self.mock_siparis_repo.get_by_id.return_value = {
            "id": 42,
            "masa_id": 3,
            "masa_no": "Masa 3",
            "siparis_kodu": "SIP-ABC123",
            "toplam_tutar": 100.0,
            "odeme_durumu": "bekliyor",
            "siparis_durumu": OrderStatus.PAID_IN_KITCHEN.value,
            "olusturma_tarihi": None,
            "garson_adi": None,
            "device_id": None,
        }
        # Sipariş şu an 1 adet tutuyor; 3 adete çıkarmak 2 adetlik yeni düşüm ister.
        self.mock_siparis_repo.get_siparis_detaylari.return_value = [
            {"urun_id": 1, "urun_adi": "Künefe", "adet": 1, "birim_fiyat": 100.0,
             "urun_notu": "", "ara_toplam": 100.0}
        ]

        self.service = SiparisService(
            siparis_repo=self.mock_siparis_repo,
            masa_repo=self.mock_masa_repo,
            urun_repo=self.mock_urun_repo,
            auth_repo=self.mock_auth_repo,
        )
        self.principal = StaffPrincipal(user_id=7, username="garson_ayse", role=UserRole.WAITER)

        patcher_tx = patch("app.services.siparis_service.db_transaction", _no_transaction)
        patcher_bus = patch("app.services.siparis_service.event_bus")
        for patcher in (patcher_tx, patcher_bus):
            self.addCleanup(patcher.stop)
        patcher_tx.start()
        patcher_bus.start().publish = AsyncMock()

    def _edit(self, adet):
        data = SiparisDuzenleModel(
            toplam_tutar=100.0,
            urunler=[SiparisItemModel(urun_id=1, adet=adet, birim_fiyat=100.0, urun_notu="")],
        )
        return asyncio.run(self.service.update_siparis_items(42, data, self.principal))

    def test_lost_race_on_an_increase_rejects_the_edit(self):
        self.mock_urun_repo.update_stock.return_value = 0

        with self.assertRaises(HTTPException) as ctx:
            self._edit(adet=3)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Künefe", ctx.exception.detail)
        self.mock_urun_repo.update_stock.assert_called_once_with(1, 2)

    def test_a_decrease_still_returns_stock_without_the_guard(self):
        self._edit(adet=1)  # değişiklik yok, stok hareketi olmamalı
        self.mock_urun_repo.update_stock.assert_not_called()
        self.mock_urun_repo.restore_stock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
