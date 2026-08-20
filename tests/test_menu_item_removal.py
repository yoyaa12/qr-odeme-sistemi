"""Menüden ürün/kategori kaldırma, veriyi silmeden ve hata vermeden çalışmalıdır.

İki gerçek hata vardı, ikisi de 2026-08-20'de canlı veritabanında doğrulandı:

1. `DELETE FROM Urunler` — `SiparisDetaylari.urun_id` bu satıra `NO_ACTION`
   kuralıyla bağlı. Bir kez sipariş edilmiş ürünü silmek `IntegrityError`
   fırlatıyordu; uçtan HTTP 500 dönüyordu. Yani satılmış hiçbir ürün menüden
   kaldırılamıyordu ("Künefe" ile doğrulandı).

2. `DELETE FROM Kategoriler` — `Urunler.kategori_id` bu satıra `ON DELETE
   CASCADE` ile bağlı. Kategori silmek, altındaki bütün ürünleri hiçbir uyarı
   vermeden siliyordu ("İçecekler" kategorisinde 14 ürün ile doğrulandı).
   Ürünlerden biri daha önce sipariş edilmişse cascade bu kez (1)'deki FK'ya
   çarpıyor ve işlem 500 ile düşüyordu. Aynı düğme bazen veri siliyor, bazen
   patlıyordu.

Düzeltme: her iki yol da artık `aktif_mi = 0` yazan bir UPDATE. Satır durur,
kayıt menüden çıkar, sipariş geçmişi bozulmaz. Uygulama hiçbir yerde `DELETE
FROM Urunler` / `DELETE FROM Kategoriler` çalıştırmadığı için cascade
tetiklenemez.

Testler bunu SQL düzeyinde sabitler: bir gün biri UPDATE'i tekrar DELETE
yaparsa bu dosya kırılır.
"""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.repositories.kategori_repo import KategoriRepository
from app.repositories.urun_repo import UrunRepository
from app.services.kategori_service import KategoriService
from app.services.urun_service import UrunService


class RecordingDatabase:
    """Repository'nin ürettiği SQL'i kaydeden sahte oturum."""

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

    def tum_sql(self):
        kayitlar = self.queries + self.non_queries + self.updates
        return " ".join(" ".join(k["query"].split()).lower() for k in kayitlar)


class ProductRemovalSqlTests(unittest.TestCase):
    def test_removing_a_product_updates_instead_of_deleting(self):
        db = RecordingDatabase()

        etkilenen = UrunRepository(db=db).deactivate(5)

        self.assertEqual(etkilenen, 1)
        self.assertEqual(db.non_queries, [], "hiçbir DELETE/INSERT çalışmamalı")
        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("update urunler set aktif_mi = 0", sql)
        self.assertNotIn("delete", db.tum_sql())
        self.assertEqual(db.updates[0]["params"], (5,))

    def test_an_already_removed_product_is_not_counted_twice(self):
        """`AND aktif_mi = 1` koşulu, ikinci kaldırmanın 0 satır etkilemesini sağlar.

        Bu sayede servis "zaten kaldırılmış" durumunu 404 olarak ayırt edebiliyor.
        """
        db = RecordingDatabase()
        UrunRepository(db=db).deactivate(5)

        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("and aktif_mi = 1", sql)

    def test_removing_a_category_updates_instead_of_deleting(self):
        db = RecordingDatabase()

        etkilenen = KategoriRepository(db=db).deactivate(26)

        self.assertEqual(etkilenen, 1)
        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("update kategoriler set aktif_mi = 0", sql)
        self.assertNotIn("delete", db.tum_sql())

    def test_a_categorys_products_are_closed_by_category_id(self):
        db = RecordingDatabase(update_rowcount=14)

        etkilenen = UrunRepository(db=db).deactivate_by_kategori(26)

        self.assertEqual(etkilenen, 14)
        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("update urunler set aktif_mi = 0 where kategori_id = ?", sql)
        self.assertEqual(db.updates[0]["params"], (26,))


class MenuVisibilityTests(unittest.TestCase):
    """Kaldırılan kayıt menüde görünmemelidir."""

    def test_the_menu_query_hides_inactive_products_and_categories(self):
        db = RecordingDatabase(query_result=[])

        UrunRepository(db=db).get_all()

        sql = " ".join(db.queries[0]["query"].split()).lower()
        self.assertIn("u.aktif_mi = 1", sql)
        self.assertIn(
            "k.aktif_mi = 1",
            sql,
            "pasif kategorinin ürünü menüde asılı kalmamalı",
        )

    def test_the_filtered_menu_query_also_hides_inactive_categories(self):
        db = RecordingDatabase(query_result=[])

        UrunRepository(db=db).get_all(kategori_id=26)

        sql = " ".join(db.queries[0]["query"].split()).lower()
        self.assertIn("u.aktif_mi = 1", sql)
        self.assertIn("k.aktif_mi = 1", sql)

    def test_the_category_list_hides_inactive_categories(self):
        db = RecordingDatabase(query_result=[])

        KategoriRepository(db=db).get_all_active()

        sql = " ".join(db.queries[0]["query"].split()).lower()
        self.assertIn("where aktif_mi = 1", sql)


class ProductRemovalServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.service = UrunService(repo=self.repo)
        self.transaction = patch("app.services.urun_service.db_transaction")
        self.transaction.start()
        self.addCleanup(self.transaction.stop)

    def test_a_sold_product_is_removed_without_an_integrity_error(self):
        """Regresyon: sipariş geçmişi olan ürün artık kaldırılabiliyor."""
        self.repo.deactivate.return_value = 1

        self.service.delete_urun(5)

        self.repo.deactivate.assert_called_once_with(5)
        self.repo.delete.assert_not_called()

    def test_an_unknown_product_is_reported_as_404(self):
        """Önceden bilinmeyen id sessizce "success" dönüyordu."""
        self.repo.deactivate.return_value = 0

        with self.assertRaises(HTTPException) as ctx:
            self.service.delete_urun(999999)

        self.assertEqual(ctx.exception.status_code, 404)


class CategoryRemovalServiceTests(unittest.TestCase):
    def setUp(self):
        self.kategori_repo = MagicMock()
        self.urun_repo = MagicMock()
        self.service = KategoriService(
            repo=self.kategori_repo, urun_repo=self.urun_repo
        )
        self.transaction = patch("app.services.kategori_service.db_transaction")
        self.transaction.start()
        self.addCleanup(self.transaction.stop)

    def test_removing_a_category_also_closes_its_products(self):
        """Cascade'in güvenli karşılığı: silmek yerine kapatmak."""
        self.kategori_repo.deactivate.return_value = 1
        self.urun_repo.deactivate_by_kategori.return_value = 14

        etkilenen = self.service.delete_kategori(26)

        self.assertEqual(etkilenen, 14, "kaç ürünün etkilendiği çağırana bildirilmeli")
        self.kategori_repo.deactivate.assert_called_once_with(26)
        self.urun_repo.deactivate_by_kategori.assert_called_once_with(26)

    def test_an_unknown_category_is_reported_as_404_and_touches_no_product(self):
        """Kategori yoksa ürünlere hiç dokunulmamalı.

        Sıra kritik: önce kategori kapatılır, tutmazsa ürün güncellemesi hiç
        çalışmaz. Ters sırada, olmayan bir kategori id'si ile gönderilen istek
        ürünleri boşuna tarardı.
        """
        self.kategori_repo.deactivate.return_value = 0

        with self.assertRaises(HTTPException) as ctx:
            self.service.delete_kategori(999999)

        self.assertEqual(ctx.exception.status_code, 404)
        self.urun_repo.deactivate_by_kategori.assert_not_called()


class RestoreSqlTests(unittest.TestCase):
    """Geri getirme de UPDATE'tir; hiçbir satır yeniden oluşturulmaz."""

    def test_restoring_a_product_flips_the_flag_back(self):
        db = RecordingDatabase()

        etkilenen = UrunRepository(db=db).activate(5)

        self.assertEqual(etkilenen, 1)
        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("update urunler set aktif_mi = 1", sql)
        self.assertIn(
            "and aktif_mi = 0",
            sql,
            "zaten menüde olan ürün 0 satır etkilemeli ki çağıran ayırt edebilsin",
        )

    def test_restoring_a_category_flips_the_flag_back(self):
        db = RecordingDatabase()

        KategoriRepository(db=db).activate(26)

        sql = " ".join(db.updates[0]["query"].split()).lower()
        self.assertIn("update kategoriler set aktif_mi = 1", sql)
        self.assertIn("and aktif_mi = 0", sql)

    def test_the_removed_product_list_ignores_the_category_state(self):
        """Kategorisi de kaldırılmış ürün listede görünmeli.

        Aksi halde o ürünü geri getirmenin arayüzden hiçbir yolu kalmazdı.
        """
        db = RecordingDatabase(query_result=[])

        UrunRepository(db=db).get_inactive()

        sql = " ".join(db.queries[0]["query"].split()).lower()
        self.assertIn("where u.aktif_mi = 0", sql)
        self.assertNotIn("k.aktif_mi", sql)


class ProductRestoreServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.kategori_repo = MagicMock()
        self.service = UrunService(repo=self.repo, kategori_repo=self.kategori_repo)
        self.transaction = patch("app.services.urun_service.db_transaction")
        self.transaction.start()
        self.addCleanup(self.transaction.stop)

    def test_a_product_is_restored_when_its_category_is_live(self):
        self.repo.get_by_id.return_value = {"id": 5, "kategori_id": 26, "aktif_mi": False}
        self.kategori_repo.get_by_id.return_value = {
            "id": 26,
            "kategori_adi": "İçecekler",
            "aktif_mi": True,
        }
        self.repo.activate.return_value = 1

        self.service.restore_urun(5)

        self.repo.activate.assert_called_once_with(5)

    def test_a_product_whose_category_is_removed_is_rejected(self):
        """Menüde görünemeyecek bir ürünü "geri getirdim" demek yanıltıcı olurdu.

        Menü sorgusu `k.aktif_mi = 1` koşulunu da uyguluyor: pasif kategorinin
        ürünü aktif olsa bile listelenmez. Sunucu bu yüzden 409 döner ve önce
        kategorinin geri getirilmesi gerektiğini söyler.
        """
        self.repo.get_by_id.return_value = {"id": 5, "kategori_id": 26, "aktif_mi": False}
        self.kategori_repo.get_by_id.return_value = {
            "id": 26,
            "kategori_adi": "İçecekler",
            "aktif_mi": False,
        }

        with self.assertRaises(HTTPException) as ctx:
            self.service.restore_urun(5)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("İçecekler", ctx.exception.detail)
        self.repo.activate.assert_not_called()

    def test_an_unknown_product_is_reported_as_404(self):
        self.repo.get_by_id.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            self.service.restore_urun(999999)

        self.assertEqual(ctx.exception.status_code, 404)
        self.repo.activate.assert_not_called()

    def test_a_product_that_is_already_live_is_reported_as_409(self):
        self.repo.get_by_id.return_value = {"id": 5, "kategori_id": 26, "aktif_mi": True}
        self.kategori_repo.get_by_id.return_value = {
            "id": 26,
            "kategori_adi": "İçecekler",
            "aktif_mi": True,
        }
        self.repo.activate.return_value = 0

        with self.assertRaises(HTTPException) as ctx:
            self.service.restore_urun(5)

        self.assertEqual(ctx.exception.status_code, 409)


class CategoryRestoreServiceTests(unittest.TestCase):
    def setUp(self):
        self.kategori_repo = MagicMock()
        self.urun_repo = MagicMock()
        self.service = KategoriService(
            repo=self.kategori_repo, urun_repo=self.urun_repo
        )
        self.transaction = patch("app.services.kategori_service.db_transaction")
        self.transaction.start()
        self.addCleanup(self.transaction.stop)

    def test_restoring_a_category_reports_its_still_removed_products(self):
        """Ürünler otomatik geri gelmez; kaç tanesinin beklediği bildirilir.

        Toplu açmak, yöneticinin kategoriden bağımsız olarak bilerek menüden
        çıkardığı ürünleri de geri diriltirdi.
        """
        self.kategori_repo.activate.return_value = 1
        self.urun_repo.count_inactive_by_kategori.return_value = 14

        kalan = self.service.restore_kategori(26)

        self.assertEqual(kalan, 14)
        self.urun_repo.activate.assert_not_called()

    def test_a_category_that_is_already_live_is_reported_as_404(self):
        self.kategori_repo.activate.return_value = 0

        with self.assertRaises(HTTPException) as ctx:
            self.service.restore_kategori(26)

        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
