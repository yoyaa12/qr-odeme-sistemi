"""Stok sipariş anında rezerve edilir, teslimatta tüketilir.

Stok `create_siparis` içinde düşülür. Bu bilinçlidir: aynı anda menüye bakan
başka bir masa, henüz mutfağa gitmemiş bir siparişin adetlerini müsait
sanmamalıdır. Ama düşme işlemi bir *rezervasyondur*, tüketim değil.

Eksik olan taraf iadeydi: müşteri çorbası gelmeden kalkarsa ya da kasa masayı
zorla kapatırsa o çorba hiç servis edilmediği hâlde stoktan kalıcı olarak
düşmüş kalıyordu. `clear_active_orders_for_masa` siparişleri
`odendi_kapatildi` yapıyor, `iptal` yapmıyor; iade yalnızca `iptal` yolunda
vardı. Yani gerçek envanter olduğundan az görünüyor ve o adetler bir daha
satılamıyordu.

Bu testler düzeltilmiş davranışı sabitler:

- adisyon kapanırken teslim EDİLMEMİŞ kalemler stoğa geri döner,
- `teslim_edildi` kalemler geri dönmez (gerçekten tüketilmiştir),
- iade, siparişlerin durumu ezilmeden ÖNCE yapılır,
- aynı masa iki kez kapatılsa da stok iki kez geri verilmez,
- stok her değiştiğinde canlı `stok_guncellendi` yayını yapılır.
"""

import asyncio
import contextlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.auth.models import StaffPrincipal
from app.enums import OrderStatus, PaymentMethod, PaymentStatus, TableStatus, UserRole
from app.repositories.siparis_repo import SiparisRepository
from app.schemas.orders import DurumGuncelleModel, SiparisItemModel, SiparisOlusturModel
from app.services import siparis_service as siparis_service_module
from app.services.siparis_service import SiparisService


@contextlib.contextmanager
def _no_transaction():
    yield None


class UndeliveredDetailQueryTests(unittest.TestCase):
    """Sorgu tam olarak "teslim edilmemiş ve hâlâ açık" kalemleri seçmelidir."""

    def setUp(self):
        self.db = MagicMock()
        self.repo = SiparisRepository(db=self.db)
        self.db.execute_query.return_value = [{"urun_id": 3, "adet": 4}]

    def test_it_sums_quantities_per_product_for_one_table(self):
        rows = self.repo.get_undelivered_details_for_masa(7)

        self.assertEqual(rows, [{"urun_id": 3, "adet": 4}])
        query, params = self.db.execute_query.call_args[0]
        self.assertIn("SUM(sd.adet)", query)
        self.assertIn("GROUP BY sd.urun_id", query)
        self.assertEqual(params[0], 7)

    def test_delivered_cancelled_and_closed_orders_are_excluded(self):
        """Üçü de iade edilmemelidir, her biri farklı nedenle.

        `teslim_edildi` gerçekten tüketilmiştir. `iptal` iadesini kendi yolunda
        zaten yapmıştır. `odendi_kapatildi` ise bu iadenin daha önce çalıştığı
        anlamına gelir; tekrar sayılırsa stok yoktan var edilir.
        """
        self.repo.get_undelivered_details_for_masa(7)

        query, params = self.db.execute_query.call_args[0]
        self.assertIn("s.siparis_durumu NOT IN (?, ?, ?)", query)
        self.assertEqual(
            set(params[1:]),
            {
                OrderStatus.DELIVERED.value,
                OrderStatus.CANCELLED.value,
                OrderStatus.PAID_CLOSED.value,
            },
        )

    def test_an_empty_result_is_a_list_not_none(self):
        self.db.execute_query.return_value = None
        self.assertEqual(self.repo.get_undelivered_details_for_masa(7), [])


class _ServiceTestBase(unittest.TestCase):
    def setUp(self):
        siparis_service_module.TABLE_MOVES_MAP.clear()
        siparis_service_module._RECENT_ORDERS_CACHE.clear()
        self.addCleanup(siparis_service_module.TABLE_MOVES_MAP.clear)
        self.addCleanup(siparis_service_module._RECENT_ORDERS_CACHE.clear)

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

        patcher_tx = patch("app.services.siparis_service.db_transaction", _no_transaction)
        patcher_bus = patch("app.services.siparis_service.event_bus")
        patcher_browsing = patch("app.services.siparis_service.clear_browsing_table")
        for patcher in (patcher_tx, patcher_bus, patcher_browsing):
            self.addCleanup(patcher.stop)
        patcher_tx.start()
        self.mock_bus = patcher_bus.start()
        self.mock_bus.publish = AsyncMock()
        patcher_browsing.start()

    def published(self, event_name):
        return [
            call.args[1]
            for call in self.mock_bus.publish.call_args_list
            if call.args and call.args[0] == event_name
        ]

    def restored_quantities(self):
        return {
            call.args[0]: call.args[1]
            for call in self.mock_urun_repo.restore_stock.call_args_list
        }


class TableCloseReleasesReservedStockTests(_ServiceTestBase):
    """Kasa masayı zorla kapattığında servis edilmemiş adetler geri döner."""

    def setUp(self):
        super().setUp()
        self.mock_siparis_repo.get_undelivered_details_for_masa.return_value = [
            {"urun_id": 3, "adet": 4},
            {"urun_id": 9, "adet": 2},
        ]
        self.mock_urun_repo.get_by_id.side_effect = lambda urun_id: {
            3: {"id": 3, "urun_adi": "Yayla Çorbası", "stok_miktari": 9},
            9: {"id": 9, "urun_adi": "Ayran", "stok_miktari": 12},
        }[urun_id]

    def test_clearing_a_table_returns_the_undelivered_quantities(self):
        asyncio.run(self.service.clear_masa(4))

        self.assertEqual(self.restored_quantities(), {3: 4, 9: 2})

    def test_the_release_happens_before_the_orders_are_marked_closed(self):
        """Sıra kritik: kapatma yazılırsa "teslim edilmemiş" bilgisi kaybolur.

        `clear_active_orders_for_masa` açık siparişleri `odendi_kapatildi`
        yapar ve bu durum sorgunun dışında kalır. Önce yazılırsa sorgu boş
        döner ve hiçbir şey iade edilmez - hata sessizdir.
        """
        order = []
        self.mock_siparis_repo.get_undelivered_details_for_masa.side_effect = (
            lambda masa_id: order.append("read") or [{"urun_id": 3, "adet": 4}]
        )
        self.mock_siparis_repo.clear_active_orders_for_masa.side_effect = (
            lambda masa_id: order.append("close")
        )

        asyncio.run(self.service.clear_masa(4))

        self.assertEqual(order, ["read", "close"])

    def test_closing_a_table_twice_does_not_create_stock(self):
        """İkinci kapatmada sorgu boş döner; iade tekrarlanmaz."""
        asyncio.run(self.service.clear_masa(4))
        self.mock_urun_repo.restore_stock.reset_mock()
        self.mock_siparis_repo.get_undelivered_details_for_masa.return_value = []

        asyncio.run(self.service.clear_masa(4))

        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_a_delivered_only_table_returns_nothing(self):
        """Teslim edilmiş ürün tüketilmiştir; stoğa geri dönmemelidir."""
        self.mock_siparis_repo.get_undelivered_details_for_masa.return_value = []

        asyncio.run(self.service.clear_masa(4))

        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_a_zero_quantity_row_is_skipped(self):
        self.mock_siparis_repo.get_undelivered_details_for_masa.return_value = [
            {"urun_id": 3, "adet": 0},
        ]

        asyncio.run(self.service.clear_masa(4))

        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_the_release_is_announced_with_the_new_stock_levels(self):
        asyncio.run(self.service.clear_masa(4))

        payloads = self.published("stok_guncellendi")
        self.assertEqual(len(payloads), 1)
        self.assertEqual(
            payloads[0]["stoklar"],
            [
                {"urun_id": 3, "stok_miktari": 9},
                {"urun_id": 9, "stok_miktari": 12},
            ],
        )


class AutomaticTableCloseTests(_ServiceTestBase):
    """Masa kendiliğinden boşaldığında da aynı iade yolu çalışmalıdır."""

    def setUp(self):
        super().setUp()
        # İptal yetkisi rol bazlıdır; ADMIN her iki geçişi de yapabilir.
        self.principal = StaffPrincipal(user_id=1, username="admin", role=UserRole.ADMIN)
        self.mock_siparis_repo.get_by_id.return_value = {
            "id": 55,
            "masa_id": 7,
            "masa_no": "Masa 7",
            "siparis_kodu": "SIP-A",
            "toplam_tutar": 85.0,
            "odeme_durumu": PaymentStatus.PAID.value,
            "siparis_durumu": OrderStatus.READY.value,
            "olusturma_tarihi": None,
            "garson_adi": None,
            "device_id": None,
        }
        self.mock_siparis_repo.get_siparis_detaylari.return_value = []
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_undelivered_details_for_masa.return_value = []

    def test_delivering_the_last_order_does_not_return_its_own_stock(self):
        """Son sipariş teslim edildi: masa boşalır ama ürün tüketilmiştir."""
        asyncio.run(
            self.service.update_siparis_durumu(
                55, DurumGuncelleModel(yeni_durum=OrderStatus.DELIVERED.value), self.principal
            )
        )

        self.mock_siparis_repo.get_undelivered_details_for_masa.assert_called_once_with(7)
        self.mock_urun_repo.restore_stock.assert_not_called()

    def test_a_cancellation_that_empties_the_table_announces_the_new_stock(self):
        self.mock_siparis_repo.get_by_id.return_value["siparis_durumu"] = (
            OrderStatus.WAITER_APPROVAL_PENDING.value
        )
        self.mock_siparis_repo.get_siparis_detaylari.return_value = [
            {"urun_id": 3, "urun_adi": "Yayla Çorbası", "adet": 2,
             "birim_fiyat": 85.0, "urun_notu": "", "ara_toplam": 170.0},
        ]
        self.mock_urun_repo.get_by_id.return_value = {
            "id": 3, "urun_adi": "Yayla Çorbası", "stok_miktari": 7
        }

        asyncio.run(
            self.service.update_siparis_durumu(
                55, DurumGuncelleModel(yeni_durum=OrderStatus.CANCELLED.value), self.principal
            )
        )

        self.assertEqual(self.restored_quantities(), {3: 2})
        self.assertEqual(
            self.published("stok_guncellendi")[0]["stoklar"],
            [{"urun_id": 3, "stok_miktari": 7}],
        )


class OrderCreationAnnouncesStockTests(_ServiceTestBase):
    """Sipariş verildiği anda diğer masaların menüsü de güncellenmelidir."""

    def setUp(self):
        super().setUp()
        self.mock_auth_repo.get_banned_device.return_value = None
        self.mock_masa_repo.get_by_id.return_value = {
            "id": 4,
            "masa_no": "Masa 4",
            "durum": TableStatus.OCCUPIED.value,
            "totp_secret": "secret",
        }
        self.mock_urun_repo.get_by_id.return_value = {
            "id": 3,
            "urun_adi": "Yayla Çorbası",
            "fiyat": 85.0,
            "aktif_mi": True,
            "stok_miktari": 5,
        }
        self.mock_urun_repo.update_stock.return_value = 1
        self.mock_siparis_repo.create_siparis.return_value = 101

    def test_the_new_stock_level_is_broadcast_after_the_order_is_committed(self):
        """Yayın commit sonrası okunan gerçek değeri taşımalıdır.

        Sipariş 2 adet düşürür; `get_by_id` yayın sırasında yeniden okunduğu
        için 5 değil 3 duyurulmalıdır. Aksi halde yan masanın ekranında
        "Son 5 Adet" yazmaya devam ederdi.
        """
        stock_reads = {"count": 0}

        def get_by_id(_urun_id):
            stock_reads["count"] += 1
            level = 5 if stock_reads["count"] == 1 else 3
            return {
                "id": 3,
                "urun_adi": "Yayla Çorbası",
                "fiyat": 85.0,
                "aktif_mi": True,
                "stok_miktari": level,
            }

        self.mock_urun_repo.get_by_id.side_effect = get_by_id

        asyncio.run(
            self.service.create_siparis(
                SiparisOlusturModel(
                    masa_id=4,
                    toplam_tutar=170.0,
                    odeme_yontemi=PaymentMethod.POS,
                    urunler=[SiparisItemModel(urun_id=3, adet=2, birim_fiyat=85.0)],
                )
            )
        )

        self.assertEqual(
            self.published("stok_guncellendi")[0]["stoklar"],
            [{"urun_id": 3, "stok_miktari": 3}],
        )

    def test_a_product_without_stock_tracking_is_not_announced(self):
        self.mock_urun_repo.get_by_id.return_value = {
            "id": 3,
            "urun_adi": "Servis Ücreti",
            "fiyat": 10.0,
            "aktif_mi": True,
            "stok_miktari": None,
        }

        asyncio.run(
            self.service.create_siparis(
                SiparisOlusturModel(
                    masa_id=4,
                    toplam_tutar=10.0,
                    odeme_yontemi=PaymentMethod.POS,
                    urunler=[SiparisItemModel(urun_id=3, adet=1, birim_fiyat=10.0)],
                )
            )
        )

        self.assertEqual(self.published("stok_guncellendi"), [])


if __name__ == "__main__":
    unittest.main()
