"""Catalog request limits must match the live column widths.

Without them an over-long product name or image URL travelled all the way to
SQL Server and failed there, so the caller got an HTTP 500 instead of a 422 and
the server logged a database error for what is really a bad request.

The limits are asserted against the values recorded from the live schema on
2026-08-17. If a column is widened or narrowed, `test_limits_match_the_recorded_
live_schema` is the reminder to move the constant with it.
"""

import unittest

from pydantic import ValidationError

from app.schemas.catalog import (
    ACIKLAMA_MAX,
    GORSEL_URL_MAX,
    KATEGORI_ADI_MAX,
    PARA_MAX,
    STOK_MAX,
    URUN_ADI_MAX,
    KategoriEkleModel,
    UrunEkleModel,
    UrunGuncelleModel,
)


def _urun(**overrides):
    payload = {
        "kategori_id": 1,
        "urun_adi": "Künefe",
        "aciklama": "Antep fıstıklı",
        "fiyat": 180.0,
        "gorsel_url": "/static/img/urunler/tatlilar/kunefe.jpg",
        "stok_miktari": 40,
    }
    payload.update(overrides)
    return payload


class CatalogLengthLimitTests(unittest.TestCase):

    def test_limits_match_the_recorded_live_schema(self):
        self.assertEqual(URUN_ADI_MAX, 100)        # Urunler.urun_adi nvarchar(100)
        self.assertEqual(ACIKLAMA_MAX, 500)        # Urunler.aciklama nvarchar(500)
        self.assertEqual(GORSEL_URL_MAX, 255)      # Urunler.gorsel_url nvarchar(255)
        self.assertEqual(KATEGORI_ADI_MAX, 50)     # Kategoriler.kategori_adi nvarchar(50)
        self.assertEqual(PARA_MAX, 99_999_999.99)  # decimal(10,2)
        self.assertEqual(STOK_MAX, 2_147_483_647)  # int

    def test_a_name_at_the_column_width_is_accepted(self):
        model = UrunEkleModel(**_urun(urun_adi="a" * URUN_ADI_MAX))
        self.assertEqual(len(model.urun_adi), URUN_ADI_MAX)

    def test_a_name_one_character_past_the_column_is_rejected(self):
        with self.assertRaises(ValidationError):
            UrunEkleModel(**_urun(urun_adi="a" * (URUN_ADI_MAX + 1)))

    def test_an_over_long_description_is_rejected(self):
        with self.assertRaises(ValidationError):
            UrunEkleModel(**_urun(aciklama="a" * (ACIKLAMA_MAX + 1)))

    def test_an_over_long_image_url_is_rejected(self):
        with self.assertRaises(ValidationError):
            UrunEkleModel(**_urun(gorsel_url="/x/" + "a" * GORSEL_URL_MAX))

    def test_an_over_long_category_name_is_rejected(self):
        KategoriEkleModel(kategori_adi="a" * KATEGORI_ADI_MAX)
        with self.assertRaises(ValidationError):
            KategoriEkleModel(kategori_adi="a" * (KATEGORI_ADI_MAX + 1))

    def test_the_update_model_carries_the_same_limits(self):
        UrunGuncelleModel(urun_adi="a" * URUN_ADI_MAX)
        with self.assertRaises(ValidationError):
            UrunGuncelleModel(urun_adi="a" * (URUN_ADI_MAX + 1))
        with self.assertRaises(ValidationError):
            UrunGuncelleModel(aciklama="a" * (ACIKLAMA_MAX + 1))


class CatalogNumericLimitTests(unittest.TestCase):

    def test_a_price_beyond_the_decimal_column_is_rejected(self):
        UrunEkleModel(**_urun(fiyat=PARA_MAX))
        with self.assertRaises(ValidationError):
            UrunEkleModel(**_urun(fiyat=PARA_MAX + 1))

    def test_a_stock_level_beyond_the_int_column_is_rejected(self):
        UrunEkleModel(**_urun(stok_miktari=STOK_MAX))
        with self.assertRaises(ValidationError):
            UrunEkleModel(**_urun(stok_miktari=STOK_MAX + 1))

    def test_negative_price_and_stock_are_still_rejected(self):
        with self.assertRaises(ValidationError):
            UrunEkleModel(**_urun(fiyat=-1))
        with self.assertRaises(ValidationError):
            UrunEkleModel(**_urun(stok_miktari=-1))

    def test_the_update_model_bounds_price_and_stock_too(self):
        with self.assertRaises(ValidationError):
            UrunGuncelleModel(fiyat=PARA_MAX + 1)
        with self.assertRaises(ValidationError):
            UrunGuncelleModel(stok_miktari=STOK_MAX + 1)


class CatalogCompatibilityTests(unittest.TestCase):
    """Real catalogue values must still validate."""

    def test_the_longest_values_currently_in_the_database_still_fit(self):
        # Ölçülen en uzun canlı değerler: urun_adi 30, aciklama 74,
        # gorsel_url 53, kategori_adi 12 karakter.
        UrunEkleModel(**_urun(
            urun_adi="a" * 30,
            aciklama="a" * 74,
            gorsel_url="a" * 53,
        ))
        KategoriEkleModel(kategori_adi="a" * 12)

    def test_optional_fields_may_still_be_omitted(self):
        model = UrunEkleModel(kategori_id=1, urun_adi="Çay", fiyat=25.0)
        self.assertEqual(model.aciklama, "")
        self.assertEqual(model.gorsel_url, "")
        self.assertEqual(model.stok_miktari, 100)


if __name__ == "__main__":
    unittest.main()
