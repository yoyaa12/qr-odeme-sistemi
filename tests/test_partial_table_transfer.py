"""Kasadaki "Seçili Ürünleri Taşı" gerçekten seçileni taşımalıdır.

Bu sekme bir yanılsamaydı: onay düğmesi seçimden bağımsız olarak
`/api/masalar/move` çağırıyordu, yani kutucuklar ne olursa olsun masanın
TAMAMI taşınıyordu. Kutucukların değeri hiçbir isteğe konmuyordu ve
`SiparisDetayResponse` satır kimliğini hiç döndürmediği için zaten
konulamazdı.

Testler düzeltilmiş davranışı sabitler:

- bir siparişin bütün kalemleri seçilmişse başlık olduğu gibi taşınır
  (fiş numarası ve ödeme geçmişi korunur),
- bir kısmı seçilmişse sipariş bölünür ve toplamlar kalemlerden yeniden
  hesaplanır,
- masanın tamamı seçilmişse normal masa taşıma yolu kullanılır,
- başka masaya ait bir kalem kimliği gönderilemez,
- taşıma stoğu hareket ettirmez.
"""

import asyncio
import contextlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.enums import OrderStatus, PaymentStatus, TableStatus
from app.schemas.orders import SiparisDetayResponse
from app.schemas.tables import MoveMasaItemsModel
from app.services import siparis_service as siparis_service_module
from app.services.siparis_service import SiparisService


@contextlib.contextmanager
def _no_transaction():
    yield None


def _row(detay_id, siparis_id, urun_id, adet, fiyat):
    return {
        "id": detay_id,
        "siparis_id": siparis_id,
        "urun_id": urun_id,
        "adet": adet,
        "birim_fiyat": fiyat,
        "urun_notu": "",
        "ara_toplam": adet * fiyat,
        "urun_adi": f"Ürün {urun_id}",
    }


class DetailIdIsExposedTests(unittest.TestCase):
    """İstemci kalemi adresleyemezse seçim gönderilemez."""

    def test_the_response_model_carries_the_detail_row_id(self):
        dto = SiparisDetayResponse(
            id=41, urun_id=3, urun_adi="Yayla Çorbası", adet=2,
            birim_fiyat=85.0, urun_notu="", ara_toplam=170.0,
        )
        self.assertEqual(dto.id, 41)

    def test_the_id_stays_optional_for_older_payloads(self):
        dto = SiparisDetayResponse(
            urun_id=3, urun_adi="Yayla Çorbası", adet=2,
            birim_fiyat=85.0, urun_notu="", ara_toplam=170.0,
        )
        self.assertIsNone(dto.id)


class MoveItemsRequestValidationTests(unittest.TestCase):
    def test_an_empty_selection_is_rejected_by_the_schema(self):
        with self.assertRaises(ValidationError):
            MoveMasaItemsModel(from_masa_id=1, to_masa_id=2, detay_ids=[])

    def test_an_absurdly_long_selection_is_rejected(self):
        with self.assertRaises(ValidationError):
            MoveMasaItemsModel(from_masa_id=1, to_masa_id=2, detay_ids=list(range(1, 500)))


class MoveMasaItemsTests(unittest.TestCase):
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

        # Masa 4: iki fiş. #10'da iki kalem, #11'de bir kalem.
        self.rows = [
            _row(101, 10, 3, 2, 85.0),
            _row(102, 10, 9, 1, 40.0),
            _row(103, 11, 7, 3, 60.0),
        ]
        self.mock_siparis_repo.get_movable_detail_rows.return_value = self.rows
        self.mock_siparis_repo.get_by_id.return_value = {
            "id": 10,
            "masa_id": 4,
            "masa_no": "Masa 4",
            "odeme_durumu": PaymentStatus.PENDING.value,
            "siparis_durumu": OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
            "device_id": "device-a",
        }
        self.mock_siparis_repo.create_siparis.return_value = 77

        patcher_tx = patch("app.services.siparis_service.db_transaction", _no_transaction)
        patcher_bus = patch("app.services.siparis_service.event_bus")
        patcher_browsing = patch("app.services.siparis_service.clear_browsing_table")
        for patcher in (patcher_tx, patcher_bus, patcher_browsing):
            self.addCleanup(patcher.stop)
        patcher_tx.start()
        self.mock_bus = patcher_bus.start()
        self.mock_bus.publish = AsyncMock()
        patcher_browsing.start()

    def _move(self, detay_ids, from_masa_id=4, to_masa_id=6):
        return asyncio.run(self.service.move_masa_items(from_masa_id, to_masa_id, detay_ids))

    def test_a_partial_selection_splits_the_order(self):
        """Fiş #10'un iki kaleminden biri seçildi: fiş bölünmeli."""
        result = self._move([101])

        self.assertFalse(result["full_move"])
        self.mock_siparis_repo.create_siparis.assert_called_once()
        args = self.mock_siparis_repo.create_siparis.call_args[0]
        self.assertEqual(args[0], 6, "yeni fiş hedef masada açılmalı")
        self.assertEqual(args[3], PaymentStatus.PENDING.value, "ödeme durumu korunmalı")
        self.assertEqual(args[4], OrderStatus.WAITER_APPROVED_IN_KITCHEN.value)
        self.assertEqual(args[5], "device-a", "cihaz kimliği korunmalı")

        self.mock_siparis_repo.reassign_detaylar_to_siparis.assert_called_once_with([101], 77)
        self.mock_siparis_repo.move_single_order_to_masa.assert_not_called()

    def test_both_totals_are_recomputed_from_the_remaining_lines(self):
        """Tutar istemciden alınmaz; iki başlık da kalemlerinden türetilir."""
        self._move([101])

        synced = [c.args[0] for c in self.mock_siparis_repo.sync_siparis_total.call_args_list]
        self.assertIn(77, synced, "yeni fişin toplamı hesaplanmalı")
        self.assertIn(10, synced, "kaynak fişin toplamı düşmeli")

    def test_selecting_every_line_of_one_order_moves_the_header(self):
        """Fiş #11'in tek kalemi seçildi: bölmeye gerek yok, başlık taşınır.

        Başlığın taşınması fiş numarasını, ödeme durumunu ve geçmişini korur;
        bölme gereksiz yere yeni bir fiş numarası üretirdi.
        """
        self._move([103])

        self.mock_siparis_repo.move_single_order_to_masa.assert_called_once_with(11, 6)
        self.mock_siparis_repo.create_siparis.assert_not_called()

    def test_selecting_the_whole_table_uses_the_normal_table_move(self):
        """Hepsi seçilmişse bu bir masa taşımadır.

        Tek tek kalem taşımak müşteri oturumlarını ve `TABLE_MOVES_MAP`
        yönlendirmesini geride bırakırdı; müşterinin telefonu eski masada
        kalırdı.
        """
        with patch.object(self.service, "move_masa", AsyncMock()) as mock_move:
            result = self._move([101, 102, 103])

        mock_move.assert_awaited_once_with(4, 6)
        self.assertTrue(result["full_move"])
        self.mock_siparis_repo.create_siparis.assert_not_called()

    def test_a_detail_id_from_another_table_is_refused(self):
        """Kimlik bilmek yetki değildir (AGENTS.md §19)."""
        with self.assertRaises(HTTPException) as ctx:
            self._move([101, 999])

        self.assertEqual(ctx.exception.status_code, 403)
        self.mock_siparis_repo.create_siparis.assert_not_called()
        self.mock_siparis_repo.reassign_detaylar_to_siparis.assert_not_called()

    def test_moving_a_table_onto_itself_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            self._move([101], from_masa_id=4, to_masa_id=4)

        self.assertEqual(ctx.exception.status_code, 400)

    def test_an_empty_selection_is_refused_at_the_service_too(self):
        with self.assertRaises(HTTPException) as ctx:
            self._move([])

        self.assertEqual(ctx.exception.status_code, 400)

    def test_a_table_with_nothing_movable_is_refused(self):
        self.mock_siparis_repo.get_movable_detail_rows.return_value = []

        with self.assertRaises(HTTPException) as ctx:
            self._move([101])

        self.assertEqual(ctx.exception.status_code, 404)

    def test_duplicate_ids_are_counted_once(self):
        """Aynı kalem iki kez gönderilirse iki kez taşınmış sayılmamalı."""
        result = self._move([101, 101, 101])

        self.assertEqual(result["moved_detail_count"], 1)
        self.mock_siparis_repo.reassign_detaylar_to_siparis.assert_called_once_with([101], 77)

    def test_the_transfer_never_touches_stock(self):
        """Kalemler masa değiştirdi, tüketilmedi veya iptal edilmedi."""
        self._move([101])

        self.mock_urun_repo.restore_stock.assert_not_called()
        self.mock_urun_repo.update_stock.assert_not_called()

    def test_the_target_table_becomes_occupied(self):
        self._move([101])

        self.mock_masa_repo.update_durum.assert_called_once_with(6, TableStatus.OCCUPIED.value)

    def test_the_source_table_keeps_its_customer_sessions(self):
        """Kısmi taşımada kaynak masada müşteri oturmaya devam ediyor.

        Oturumları iptal etmek, orada oturan grubun telefonlarını sebepsiz
        yere kilitlerdi.
        """
        self._move([101])

        self.mock_auth_repo.revoke_all_sessions_for_masa.assert_not_called()
        self.assertEqual(siparis_service_module.TABLE_MOVES_MAP, {})

    def test_both_tables_are_announced(self):
        self._move([101])

        events = [c.args[0] for c in self.mock_bus.publish.call_args_list]
        self.assertIn("masa_durumu_degisti", events)
        self.assertEqual(events.count("durum_guncellendi"), 2)


if __name__ == "__main__":
    unittest.main()
