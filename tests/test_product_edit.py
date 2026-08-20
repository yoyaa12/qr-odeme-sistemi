"""Ürün düzenleme: ad, kategori, fiyat ve stok tek istekte güncellenebilmelidir.

Panelde yalnızca stok kutusu vardı; ad/kategori/fiyat düzeltmek için
veritabanına gitmek gerekiyordu. `kategori_id` istek modelinde hiç yoktu, yani
bir ürün panelden başka kategoriye taşınamıyordu.

Bu dosya üç şeyi sabitler:

1. Kısmi güncelleme anlamını korur: gönderilmeyen alana dokunulmaz. Stok kutusu
   yalnızca `stok_miktari` gönderiyor ve ürünün adını/fiyatını ezmemeli.
2. Güncelleme TEK bir UPDATE ile yazılır. Önceden her alan için ayrı sorgu
   çalışıyordu; arada bir hata ürünü yarı güncellenmiş bırakabilirdi.
3. Kolon adları SQL'e girmeden önce beyaz listeye karşı doğrulanır. SET ifadesi
   çalışma zamanında kurulduğu için kolon adı parametreleştirilemiyor; tek
   koruma bu doğrulama.

Ayrıca hedef kategori kontrolü: menüden kaldırılmış bir kategoriye taşınan ürün,
menü sorgusundaki `k.aktif_mi = 1` koşulu yüzünden hiç görünmezdi. Sessizce
kaybolmak yerine istek 409 ile reddedilir.
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.repositories.urun_repo import UrunRepository
from app.schemas.catalog import UrunGuncelleModel
from app.services.urun_service import UrunService


class RecordingDatabase:
    def __init__(self, query_result=None, update_rowcount=1):
        self.query_result = query_result
        self.update_rowcount = update_rowcount
        self.queries = []
        self.non_queries = []
        self.updates = []

    def execute_query(self, query, params=(), fetch_all=True, fetch_one=False):
        self.queries.append({"query": query, "params": params})
        return self.query_result

    def execute_non_query(self, query, params=()):
        self.non_queries.append({"query": query, "params": params})

    def execute_update(self, query, params=()):
        self.updates.append({"query": query, "params": params})
        return self.update_rowcount


class UpdateSqlTests(unittest.TestCase):
    def test_all_fields_are_written_in_a_single_statement(self):
        """Önceden alan başına bir UPDATE çalışıyordu.

        Ayrı sorgular hem gereksizdi hem de bir alan yazıldıktan sonra oluşan
        bir hata ürünü yarı güncellenmiş halde bırakabiliyordu.
        """
        db = RecordingDatabase()

        UrunRepository(db=db).update(
            5, {"urun_adi": "Yeni Ad", "fiyat": 120.0, "kategori_id": 3}
        )

        self.assertEqual(len(db.updates), 1, "tek UPDATE bekleniyor")
        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("update urunler set", sql)
        self.assertEqual(sql.count("set"), 1)
        # Ürün kimliği en sonda, SET değerlerinden sonra gelir.
        self.assertEqual(db.updates[0]["params"][-1], 5)
        self.assertEqual(len(db.updates[0]["params"]), 4)

    def test_untouched_fields_are_left_out_of_the_statement(self):
        """`None` "bu alana dokunma" demektir.

        Stok kutusu yalnızca `stok_miktari` gönderiyor; ürünün adı ve fiyatı
        sorguya hiç girmemeli.
        """
        db = RecordingDatabase()

        UrunRepository(db=db).update(
            5, {"urun_adi": None, "fiyat": None, "stok_miktari": 42}
        )

        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("stok_miktari = ?", sql)
        self.assertNotIn("urun_adi", sql)
        self.assertNotIn("fiyat", sql)
        self.assertEqual(db.updates[0]["params"], (42, 5))

    def test_an_empty_string_is_written_but_none_is_not(self):
        """Bir açıklamayı bilerek boşaltmak geçerli bir işlemdir."""
        db = RecordingDatabase()

        UrunRepository(db=db).update(5, {"aciklama": "", "urun_adi": None})

        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("aciklama = ?", sql)
        self.assertEqual(db.updates[0]["params"], ("", 5))

    def test_a_column_outside_the_allow_list_never_reaches_sql(self):
        """Kolon adı sorgu metnine gömülüyor; tek koruma bu doğrulama."""
        db = RecordingDatabase()

        with self.assertRaises(ValueError):
            UrunRepository(db=db).update(5, {"aktif_mi": 0})

        with self.assertRaises(ValueError):
            UrunRepository(db=db).update(5, {"id = 1; DROP TABLE Urunler --": "x"})

        self.assertEqual(db.updates, [], "doğrulama başarısızsa hiçbir SQL çalışmamalı")

    def test_nothing_to_update_reports_zero_rows(self):
        db = RecordingDatabase()

        self.assertEqual(UrunRepository(db=db).update(5, {"urun_adi": None}), 0)
        self.assertEqual(db.updates, [])


class UpdateRequestModelTests(unittest.TestCase):
    def test_the_category_can_be_changed_through_the_request_model(self):
        model = UrunGuncelleModel(kategori_id=3)

        self.assertEqual(model.kategori_id, 3)
        # Gönderilmeyen alanlar `None` kalır: "dokunma".
        self.assertIsNone(model.urun_adi)
        self.assertIsNone(model.fiyat)
        self.assertIsNone(model.stok_miktari)

    def test_a_non_positive_category_id_is_rejected(self):
        for gecersiz in (0, -1):
            with self.subTest(kategori_id=gecersiz):
                with self.assertRaises(Exception):
                    UrunGuncelleModel(kategori_id=gecersiz)


class UpdateServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.kategori_repo = MagicMock()
        self.service = UrunService(repo=self.repo, kategori_repo=self.kategori_repo)
        self.transaction = patch("app.services.urun_service.db_transaction")
        self.transaction.start()
        self.addCleanup(self.transaction.stop)

    def _guncelle(self, **alanlar):
        return asyncio.run(
            self.service.update_urun(5, UrunGuncelleModel(**alanlar))
        )

    def test_a_full_edit_passes_every_field_to_the_repository(self):
        self.kategori_repo.get_by_id.return_value = {
            "id": 3, "kategori_adi": "Çorbalar", "aktif_mi": True
        }
        self.repo.update.return_value = 1

        self._guncelle(urun_adi="Yeni Ad", kategori_id=3, fiyat=120.0, stok_miktari=7)

        yazilan = self.repo.update.call_args[0][1]
        self.assertEqual(yazilan["urun_adi"], "Yeni Ad")
        self.assertEqual(yazilan["kategori_id"], 3)
        self.assertEqual(yazilan["fiyat"], 120.0)
        self.assertEqual(yazilan["stok_miktari"], 7)

    def test_moving_into_a_removed_category_is_rejected(self):
        """Menü sorgusu pasif kategorinin ürününü listelemez.

        Taşımaya izin vermek, ürünün "güncellendi" denip menüden kaybolması
        demekti.
        """
        self.kategori_repo.get_by_id.return_value = {
            "id": 9, "kategori_adi": "Ana Yemekler", "aktif_mi": False
        }

        with self.assertRaises(HTTPException) as ctx:
            self._guncelle(kategori_id=9)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Ana Yemekler", ctx.exception.detail)
        self.repo.update.assert_not_called()

    def test_an_unknown_target_category_is_reported_as_404(self):
        self.kategori_repo.get_by_id.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            self._guncelle(kategori_id=999999)

        self.assertEqual(ctx.exception.status_code, 404)
        self.repo.update.assert_not_called()

    def test_an_unknown_product_is_reported_as_404(self):
        """Önceden bilinmeyen id sessizce "success" dönüyordu."""
        self.repo.update.return_value = 0
        self.repo.get_by_id.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            self._guncelle(fiyat=10.0)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_an_empty_body_is_reported_as_400_not_success(self):
        """Hiçbir alan göndermemek istemci hatasıdır.

        "Başarılı" demek, düzenlemenin kaydedildiği yanılsamasını yaratırdı.
        """
        self.repo.update.return_value = 0
        self.repo.get_by_id.return_value = {"id": 5}

        with self.assertRaises(HTTPException) as ctx:
            self._guncelle()

        self.assertEqual(ctx.exception.status_code, 400)

    def test_a_stock_only_edit_still_announces_the_new_level(self):
        """Menüdeki "Son X Adet" rozeti anında güncellenmelidir."""
        self.repo.update.return_value = 1

        with patch("app.services.urun_service.event_bus") as bus:
            bus.publish = MagicMock(return_value=asyncio.sleep(0))
            self._guncelle(stok_miktari=42)

        self.assertEqual(bus.publish.call_args[0][0], "stok_guncellendi")
        self.kategori_repo.get_by_id.assert_not_called()

    def test_an_edit_without_stock_publishes_nothing(self):
        self.repo.update.return_value = 1

        with patch("app.services.urun_service.event_bus") as bus:
            self._guncelle(urun_adi="Sadece Ad")

        bus.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
