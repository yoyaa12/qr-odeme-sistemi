"""Bir siparişin sahibi, doğrulanmış oturumdan belirlenir.

Sipariş bugüne kadar yalnızca `device_id` taşıyordu ve bu alan istek gövdesinden
geliyor. Yani bir cihaz başkasının `device_id` değerini gönderip siparişi ona
yazdırabilirdi; "bu siparişi kim verdi" sorusunun cevabı olarak
güvenilemezdi (AGENTS.md §10).

`Siparisler.customer_session_id` ise `CustomerSessions` satırının kimliğidir ve
controller bunu istek gövdesinden değil, `get_current_user_or_customer`
sonucundan alır. İstemci yalnızca token gönderir; token hash'lenip veritabanında
aranır ve oturum oradan çözülür.

Testler şunu sabitler:

- oturum kimliği yazılır ve `device_id` ile karıştırılmaz,
- `is_mine` yalnızca kimlik eşleşiyorsa `True` olur,
- oturumu bilinmeyen (eski) kayıtlar asla "benim" görünmez,
- personel yollarında alan `None` kalır ("bu soru sorulmadı"),
- `benim_toplamim` yalnızca kendi siparişlerini toplar,
- ham oturum kimliği istemciye sızmaz.
"""

import asyncio
import contextlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.enums import OrderStatus, PaymentMethod, PaymentStatus, TableStatus
from app.schemas.orders import SiparisItemModel, SiparisOlusturModel, SiparisResponse
from app.services import siparis_service as siparis_service_module
from app.services.siparis_service import SiparisService


@contextlib.contextmanager
def _no_transaction():
    yield None


def _order_row(order_id, session_id, tutar=100.0):
    return {
        "id": order_id,
        "masa_id": 5,
        "masa_no": "Masa 5",
        "siparis_kodu": f"SIP-{order_id}",
        "toplam_tutar": tutar,
        "odeme_durumu": PaymentStatus.PENDING.value,
        "siparis_durumu": OrderStatus.WAITER_APPROVAL_PENDING.value,
        "olusturma_tarihi": None,
        "garson_adi": None,
        "device_id": "device-x",
        "customer_session_id": session_id,
    }


class _Base(unittest.TestCase):
    def setUp(self):
        siparis_service_module.TABLE_MOVES_MAP.clear()
        siparis_service_module._RECENT_ORDERS_CACHE.clear()
        self.addCleanup(siparis_service_module.TABLE_MOVES_MAP.clear)
        self.addCleanup(siparis_service_module._RECENT_ORDERS_CACHE.clear)

        self.mock_siparis_repo = MagicMock()
        self.mock_masa_repo = MagicMock()
        self.mock_urun_repo = MagicMock()
        self.mock_auth_repo = MagicMock()
        self.mock_siparis_repo.get_siparis_detaylari.return_value = []

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


class OwnershipIsWrittenFromTheSessionTests(_Base):
    def setUp(self):
        super().setUp()
        self.mock_auth_repo.get_banned_device.return_value = None
        self.mock_masa_repo.get_by_id.return_value = {
            "id": 5, "masa_no": "Masa 5",
            "durum": TableStatus.OCCUPIED.value, "totp_secret": "secret",
        }
        self.mock_urun_repo.get_by_id.return_value = {
            "id": 3, "urun_adi": "Yayla Çorbası", "fiyat": 85.0,
            "aktif_mi": True, "stok_miktari": 20,
        }
        self.mock_urun_repo.update_stock.return_value = 1
        self.mock_siparis_repo.create_siparis.return_value = 101

    def _create(self, session_id, adet=1, device_id="device-a"):
        return asyncio.run(
            self.service.create_siparis(
                SiparisOlusturModel(
                    masa_id=5,
                    toplam_tutar=85.0 * adet,
                    odeme_yontemi=PaymentMethod.POS,
                    device_id=device_id,
                    urunler=[SiparisItemModel(urun_id=3, adet=adet, birim_fiyat=85.0)],
                ),
                customer_session_id=session_id,
            )
        )

    def test_the_session_id_is_persisted_on_the_order(self):
        self._create(session_id=42)

        args = self.mock_siparis_repo.create_siparis.call_args[0]
        self.assertEqual(args[6], 42, "customer_session_id yazılmalı")

    def test_the_session_id_is_separate_from_the_client_supplied_device_id(self):
        """İkisi aynı alana yazılırsa taklit edilebilir kimlik geri gelirdi."""
        self._create(session_id=42, device_id="device-a")

        args = self.mock_siparis_repo.create_siparis.call_args[0]
        self.assertEqual(args[5], "device-a")
        self.assertEqual(args[6], 42)

    def test_a_staff_created_order_stores_no_session(self):
        self._create(session_id=None)

        args = self.mock_siparis_repo.create_siparis.call_args[0]
        self.assertIsNone(args[6])

    def test_the_creator_gets_its_own_order_back_as_mine(self):
        response = self._create(session_id=42)
        self.assertTrue(response.is_mine)

    def test_an_order_without_a_session_is_not_marked_mine(self):
        response = self._create(session_id=None)
        self.assertFalse(response.is_mine)

    def test_two_sessions_at_one_table_are_not_deduplicated(self):
        """Aynı masada iki kişi aynı anda aynı ürünü söyleyebilir.

        Tekrarlı istek penceresi (`_RECENT_ORDERS_CACHE`) yalnızca masa + cihaz
        + sepet ile anahtarlanıyordu; iki farklı oturumun aynı siparişi tek
        siparişe düşerdi.
        """
        first = self._create(session_id=42, device_id="shared-device")
        self.mock_siparis_repo.create_siparis.return_value = 102
        second = self._create(session_id=43, device_id="shared-device")

        self.assertEqual(self.mock_siparis_repo.create_siparis.call_count, 2)
        self.assertIsNot(first, second)

    def test_the_same_session_resending_the_same_cart_is_deduplicated(self):
        """Tekrarlı gönderim koruması olduğu gibi çalışmaya devam etmeli."""
        first = self._create(session_id=42, device_id="device-a")
        second = self._create(session_id=42, device_id="device-a")

        self.assertEqual(self.mock_siparis_repo.create_siparis.call_count, 1)
        self.assertIs(first, second)


class IsMineIsComputedOnTheServerTests(_Base):
    def test_only_a_matching_session_is_mine(self):
        dto = self.service._map_to_siparis_response(_order_row(1, 42), viewer_session_id=42)
        self.assertTrue(dto.is_mine)

    def test_another_session_at_the_same_table_is_not_mine(self):
        dto = self.service._map_to_siparis_response(_order_row(1, 43), viewer_session_id=42)
        self.assertFalse(dto.is_mine)

    def test_a_legacy_order_without_a_session_is_never_mine(self):
        """Bu değişiklikten önceki kayıtlarda kolon NULL; veri uydurulmaz."""
        dto = self.service._map_to_siparis_response(_order_row(1, None), viewer_session_id=42)
        self.assertFalse(dto.is_mine)

    def test_staff_reads_leave_the_question_unanswered(self):
        """`None`, "hayır" değil "bu soru sorulmadı" demektir."""
        dto = self.service._map_to_siparis_response(_order_row(1, 42))
        self.assertIsNone(dto.is_mine)

    def test_the_raw_session_id_is_not_exposed_to_clients(self):
        """Masadaki bir müşteri diğerlerinin oturum kimliğini görmemeli."""
        dto = self.service._map_to_siparis_response(_order_row(1, 42), viewer_session_id=42)
        payload = dto.model_dump(mode="json")

        self.assertNotIn("customer_session_id", payload)
        self.assertIn("is_mine", payload)

    def test_the_response_model_ignores_a_client_supplied_ownership_claim(self):
        """İstemci "bu benim" diye bir alan gönderemez; sunucu hesaplar."""
        row = _order_row(1, 43)
        row["is_mine"] = True  # sahte iddia
        dto = self.service._map_to_siparis_response(row, viewer_session_id=42)

        self.assertFalse(dto.is_mine, "sunucu hesabı iddiayı ezmeli")


class ActiveTableViewTests(_Base):
    def setUp(self):
        super().setUp()
        self.mock_siparis_repo.get_all_active_by_masa_id.return_value = [
            _order_row(1, 42, 100.0),
            _order_row(2, 43, 250.0),
            _order_row(3, 42, 50.0),
        ]
        self.mock_siparis_repo.get_masa_tahsilat_toplami.return_value = 0.0

    def test_the_table_total_covers_everyone(self):
        res = self.service.get_masa_aktif_siparis(5, viewer_session_id=42)
        self.assertEqual(res.genel_toplam, 400.0)

    def test_the_personal_total_covers_only_my_orders(self):
        res = self.service.get_masa_aktif_siparis(5, viewer_session_id=42)
        self.assertEqual(res.benim_toplamim, 150.0)

    def test_every_order_is_still_returned(self):
        """Kişisel görünüm bir filtredir; sunucu masanın tamamını döner.

        Müşteriye yalnızca kendi kalemlerini göndermek, hesap geldiğinde
        sürprize yol açar ve kasadaki rakamla uyuşmaz.
        """
        res = self.service.get_masa_aktif_siparis(5, viewer_session_id=42)

        self.assertEqual(len(res.siparisler), 3)
        self.assertEqual([o.is_mine for o in res.siparisler], [True, False, True])

    def test_a_staff_read_gets_no_personal_total(self):
        res = self.service.get_masa_aktif_siparis(5)

        self.assertIsNone(res.benim_toplamim)
        self.assertTrue(all(o.is_mine is None for o in res.siparisler))

    def test_an_empty_table_reports_a_zero_personal_total(self):
        self.mock_siparis_repo.get_all_active_by_masa_id.return_value = []

        res = self.service.get_masa_aktif_siparis(5, viewer_session_id=42)

        self.assertFalse(res.has_active)
        self.assertEqual(res.benim_toplamim, 0.0)


class ResponseContractTests(unittest.TestCase):
    def test_is_mine_defaults_to_unknown(self):
        dto = SiparisResponse(
            id=1, masa_id=5, masa_no="Masa 5", siparis_kodu="SIP-1",
            toplam_tutar=100.0, odeme_durumu=PaymentStatus.PENDING,
            siparis_durumu=OrderStatus.WAITER_APPROVAL_PENDING,
        )
        self.assertIsNone(dto.is_mine)


if __name__ == "__main__":
    unittest.main()
