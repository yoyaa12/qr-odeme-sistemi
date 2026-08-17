"""Regression tests for the staff order-edit path (PUT /siparisler/{id}).

This path previously wrote the client's ``toplam_tutar`` and ``birim_fiyat``
straight to the database and never touched stock, while the create path priced
everything server-side. These tests pin the corrected behaviour.
"""

import asyncio
import contextlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.auth.models import StaffPrincipal
from app.enums import OrderStatus, UserRole
from app.schemas.orders import SiparisDuzenleModel, SiparisItemModel
from app.services.siparis_service import SiparisService


@contextlib.contextmanager
def _no_transaction():
    yield None


class OrderEditTestBase(unittest.TestCase):

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
        self.principal = StaffPrincipal(user_id=7, username="garson_ayse", role=UserRole.WAITER)

        # 100 TL taban fiyatli, 50 adet stoklu tek urun.
        self.product = {
            "id": 1,
            "urun_adi": "Köfte",
            "fiyat": 100.0,
            "stok_miktari": 50,
            "aktif_mi": True,
        }
        self.mock_urun_repo.get_by_id.return_value = self.product

        self.order_row = {
            "id": 42,
            "masa_id": 3,
            "masa_no": "Masa 3",
            "siparis_kodu": "SIP-ABC123",
            "toplam_tutar": 200.0,
            "odeme_durumu": "bekliyor",
            "siparis_durumu": OrderStatus.PAID_IN_KITCHEN.value,
            "olusturma_tarihi": None,
            "garson_adi": None,
            "device_id": None,
        }
        self.mock_siparis_repo.get_by_id.return_value = self.order_row
        # Siparis hali hazirda 2 adet tutuyor.
        self.mock_siparis_repo.get_siparis_detaylari.return_value = [
            {"urun_id": 1, "urun_adi": "Köfte", "adet": 2, "birim_fiyat": 100.0,
             "urun_notu": "", "ara_toplam": 200.0}
        ]

        patcher_tx = patch("app.services.siparis_service.db_transaction", _no_transaction)
        patcher_bus = patch("app.services.siparis_service.event_bus")
        self.addCleanup(patcher_tx.stop)
        self.addCleanup(patcher_bus.stop)
        patcher_tx.start()
        mock_bus = patcher_bus.start()
        mock_bus.publish = AsyncMock()

    def _edit(self, data: SiparisDuzenleModel):
        return asyncio.run(self.service.update_siparis_items(42, data, self.principal))


class TestOrderEditPricing(OrderEditTestBase):

    def test_client_supplied_total_is_ignored(self):
        """Saldirgan 0.01 TL toplam gonderse bile DB'ye katalog fiyati yazilir."""
        data = SiparisDuzenleModel(
            toplam_tutar=0.01,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=0.01, urun_notu="")],
        )
        self._edit(data)

        self.mock_siparis_repo.replace_siparis_items.assert_called_once()
        args = self.mock_siparis_repo.replace_siparis_items.call_args[0]
        written_total = args[1]
        self.assertEqual(written_total, 200.0, "Toplam katalog fiyatindan hesaplanmali")
        self.assertNotEqual(written_total, 0.01)

    def test_client_supplied_unit_price_is_ignored(self):
        data = SiparisDuzenleModel(
            toplam_tutar=0.01,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=0.01, urun_notu="")],
        )
        self._edit(data)

        priced = self.mock_siparis_repo.replace_siparis_items.call_args[0][2]
        self.assertEqual(len(priced), 1)
        self.assertEqual(priced[0]["birim_fiyat"], 100.0)
        self.assertEqual(priced[0]["ara_toplam"], 200.0)

    def test_note_option_surcharge_is_applied_server_side(self):
        data = SiparisDuzenleModel(
            toplam_tutar=1.0,
            urunler=[SiparisItemModel(urun_id=1, adet=1, birim_fiyat=1.0, urun_notu="Orta Boy")],
        )
        self._edit(data)

        priced = self.mock_siparis_repo.replace_siparis_items.call_args[0][2]
        self.assertEqual(priced[0]["birim_fiyat"], 140.0)  # 100 + 40

    def test_audit_name_comes_from_principal_not_request(self):
        data = SiparisDuzenleModel(
            toplam_tutar=200.0,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=100.0, urun_notu="")],
        )
        self._edit(data)

        garson_adi = self.mock_siparis_repo.replace_siparis_items.call_args[0][3]
        self.assertEqual(garson_adi, "garson_ayse")

    def test_edit_schema_has_no_forgeable_staff_name_field(self):
        self.assertNotIn("garson_adi", SiparisDuzenleModel.model_fields)


class TestOrderEditStock(OrderEditTestBase):

    def test_increasing_quantity_takes_the_difference_from_stock(self):
        """2 -> 5 adet: yalnizca 3 adet dusulmeli, 5 degil."""
        data = SiparisDuzenleModel(
            toplam_tutar=500.0,
            urunler=[SiparisItemModel(urun_id=1, adet=5, birim_fiyat=100.0, urun_notu="")],
        )
        self._edit(data)

        self.mock_urun_repo.update_stock.assert_called_once_with(1, 3)
        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_decreasing_quantity_returns_the_difference_to_stock(self):
        """2 -> 1 adet: 1 adet stoga geri verilmeli."""
        data = SiparisDuzenleModel(
            toplam_tutar=100.0,
            urunler=[SiparisItemModel(urun_id=1, adet=1, birim_fiyat=100.0, urun_notu="")],
        )
        self._edit(data)

        self.mock_urun_repo.restore_stock.assert_called_once_with(1, 1)
        self.mock_urun_repo.update_stock.assert_not_called()

    def test_unchanged_quantity_does_not_move_stock(self):
        data = SiparisDuzenleModel(
            toplam_tutar=200.0,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=100.0, urun_notu="")],
        )
        self._edit(data)

        self.mock_urun_repo.update_stock.assert_not_called()
        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_quantities_already_held_by_this_order_count_as_available(self):
        """Stok 0 olsa bile siparisin kendi tuttugu 2 adet yeniden yazilabilmeli."""
        self.product["stok_miktari"] = 0
        data = SiparisDuzenleModel(
            toplam_tutar=200.0,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=100.0, urun_notu="")],
        )
        self._edit(data)  # yetersiz stok hatasi vermemeli
        self.mock_siparis_repo.replace_siparis_items.assert_called_once()

    def test_stock_beyond_what_the_order_holds_is_rejected(self):
        self.product["stok_miktari"] = 1  # +1 musait, siparis 2 tutuyor => tavan 3
        data = SiparisDuzenleModel(
            toplam_tutar=400.0,
            urunler=[SiparisItemModel(urun_id=1, adet=4, birim_fiyat=100.0, urun_notu="")],
        )
        with self.assertRaises(HTTPException) as ctx:
            self._edit(data)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("yetersiz stok", ctx.exception.detail)
        self.mock_siparis_repo.replace_siparis_items.assert_not_called()


class TestOrderEditStateGuard(OrderEditTestBase):

    def test_cancelled_order_cannot_be_edited(self):
        self.order_row["siparis_durumu"] = OrderStatus.CANCELLED.value
        data = SiparisDuzenleModel(
            toplam_tutar=200.0,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=100.0, urun_notu="")],
        )
        with self.assertRaises(HTTPException) as ctx:
            self._edit(data)

        self.assertEqual(ctx.exception.status_code, 409)
        self.mock_siparis_repo.replace_siparis_items.assert_not_called()

    def test_closed_order_cannot_be_edited(self):
        self.order_row["siparis_durumu"] = OrderStatus.PAID_CLOSED.value
        data = SiparisDuzenleModel(
            toplam_tutar=200.0,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=100.0, urun_notu="")],
        )
        with self.assertRaises(HTTPException) as ctx:
            self._edit(data)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_missing_order_is_rejected(self):
        self.mock_siparis_repo.get_by_id.return_value = None
        data = SiparisDuzenleModel(
            toplam_tutar=200.0,
            urunler=[SiparisItemModel(urun_id=1, adet=2, birim_fiyat=100.0, urun_notu="")],
        )
        with self.assertRaises(HTTPException) as ctx:
            self._edit(data)

        self.assertEqual(ctx.exception.status_code, 404)


class TestRepositoryTakesNoClientModel(unittest.TestCase):

    def test_replace_siparis_items_writes_only_server_priced_values(self):
        """Repo katmani istek modeli degil, sunucuda fiyatlanmis dict alir."""
        from app.repositories.siparis_repo import SiparisRepository

        db = MagicMock()
        repo = SiparisRepository(db=db)
        repo.replace_siparis_items(
            5,
            250.0,
            [{"urun_id": 9, "adet": 2, "birim_fiyat": 125.0, "urun_notu": "", "ara_toplam": 250.0}],
            "garson_ayse",
        )

        detay_calls = [
            c for c in db.execute_non_query.call_args_list
            if "INSERT INTO SiparisDetaylari" in c[0][0]
        ]
        self.assertEqual(len(detay_calls), 1)
        self.assertEqual(detay_calls[0][0][1], (5, 9, 2, 125.0, "", 250.0))

    def test_legacy_client_priced_writer_is_gone(self):
        from app.repositories.siparis_repo import SiparisRepository

        self.assertFalse(
            hasattr(SiparisRepository, "update_siparis_items"),
            "Istemci fiyatini yazan eski metot geri gelmemeli",
        )


if __name__ == "__main__":
    unittest.main()
