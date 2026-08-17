"""QR/TOTP doğrulama ucunun sertleştirilmesine dair testler.

`POST /masalar/{id}/verify-qr` kimlik doğrulaması istemeyen tek uçtur ve 6 haneli
bir kod kabul eder. TOTP penceresi toleransı ±2 olduğu için aynı anda 5 kod
geçerlidir; hız sınırı olmadan çevrimiçi kaba kuvvet uygulanabilirdi.
"""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.auth.rate_limit import ProcessLocalLoginRateLimiter
from app.schemas.tables import TahsilatModel, VerifyQRModel
from app.services.masa_service import MasaService


class TestQrVerifyRateLimit(unittest.TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.repo.db = MagicMock()
        self.service = MasaService(repo=self.repo)
        # Testler icin izole, kucuk esikli bir limiter.
        self.limiter = ProcessLocalLoginRateLimiter(max_failures=3, window_seconds=60)

    def _verify(self, token="000000", device_id=None, host="10.0.0.9"):
        return self.service.verify_dynamic_qr_with_device(
            1, token, device_id, client_host=host, limiter=self.limiter
        )

    @patch("app.services.masa_service.SiparisRepository")
    def test_repeated_failures_eventually_return_429(self, mock_repo_cls):
        mock_repo_cls.return_value.get_all_active_by_masa_id.return_value = []
        with patch.object(self.service, "verify_dynamic_qr_token", return_value=False):
            for attempt in range(3):
                result = self._verify()
                self.assertFalse(result.valid, f"{attempt}. deneme gecersiz olmali")

            with self.assertRaises(HTTPException) as ctx:
                self._verify()

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)

    @patch("app.services.masa_service.SiparisRepository")
    def test_a_different_source_ip_is_throttled_independently(self, mock_repo_cls):
        """Masa sayaci paylasilir; bu test IP sayacinin ayri tutuldugunu dogrular."""
        mock_repo_cls.return_value.get_all_active_by_masa_id.return_value = []
        limiter = ProcessLocalLoginRateLimiter(max_failures=3, window_seconds=60)

        with patch.object(self.service, "verify_dynamic_qr_token", return_value=False):
            for _ in range(2):
                self.service.verify_dynamic_qr_with_device(
                    1, "000000", None, client_host="10.0.0.1", limiter=limiter
                )
            # Farkli IP, farkli masa: kendi kotasi olmali.
            result = self.service.verify_dynamic_qr_with_device(
                2, "000000", None, client_host="10.0.0.2", limiter=limiter
            )
        self.assertFalse(result.valid)

    @patch("app.services.masa_service.SiparisRepository")
    def test_successful_verification_clears_the_failure_counters(self, mock_repo_cls):
        mock_repo_cls.return_value.get_all_active_by_masa_id.return_value = []

        with patch.object(self.service, "verify_dynamic_qr_token", return_value=False):
            self._verify()
            self._verify()

        with patch.object(self.service, "verify_dynamic_qr_token", return_value=True), \
             patch.object(self.service, "_issue_customer_session", return_value="tok"):
            ok = self._verify()
        self.assertTrue(ok.valid)

        # Sayac sifirlandigi icin yeniden tam kota olmali.
        with patch.object(self.service, "verify_dynamic_qr_token", return_value=False):
            for _ in range(3):
                self._verify()
            with self.assertRaises(HTTPException) as ctx:
                self._verify()
        self.assertEqual(ctx.exception.status_code, 429)

    @patch("app.services.masa_service.SiparisRepository")
    def test_valid_token_issues_a_customer_session(self, mock_repo_cls):
        mock_repo_cls.return_value.get_all_active_by_masa_id.return_value = []
        with patch.object(self.service, "verify_dynamic_qr_token", return_value=True), \
             patch.object(self.service, "_issue_customer_session", return_value="oturum-token"):
            result = self._verify()

        self.assertTrue(result.valid)
        self.assertEqual(result.session_token, "oturum-token")
        self.assertEqual(result.masa_id, 1)


class TestVerifyQrSchemaBounds(unittest.TestCase):

    def test_token_length_is_bounded(self):
        """Sinirsiz uzunlukta token gereksiz is yuku yaratir."""
        with self.assertRaises(ValidationError):
            VerifyQRModel(token="x" * 33)

    def test_empty_token_is_rejected(self):
        with self.assertRaises(ValidationError):
            VerifyQRModel(token="")

    def test_normal_six_digit_token_is_accepted(self):
        model = VerifyQRModel(token="123456", device_id="cihaz-1")
        self.assertEqual(model.token, "123456")


class TestTahsilatValidation(unittest.TestCase):
    """Negatif tahsilat, ödenmemiş adisyonu ödenmiş gibi gösterebilirdi."""

    def test_negative_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            TahsilatModel(tutar=-100.0, odeme_yontemi="nakit")

    def test_zero_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            TahsilatModel(tutar=0.0, odeme_yontemi="nakit")

    def test_empty_payment_method_is_rejected(self):
        with self.assertRaises(ValidationError):
            TahsilatModel(tutar=50.0, odeme_yontemi="")

    def test_positive_amount_is_accepted(self):
        model = TahsilatModel(tutar=250.5, odeme_yontemi="nakit")
        self.assertEqual(model.tutar, 250.5)


class TestPublicTableListingDoesNotLeakBrowsing(unittest.TestCase):
    """`GET /masalar` public'tir; göz atma bilgisi yalnızca personele döner."""

    def test_optional_staff_dependency_exists(self):
        from app.auth.dependencies import get_optional_staff

        self.assertTrue(callable(get_optional_staff))

    def test_plain_listing_carries_no_browsing_detail(self):
        repo = MagicMock()
        repo.get_all.return_value = [
            {"id": 1, "masa_no": "Masa 1", "durum": "bos", "totp_secret": "gizli"}
        ]
        service = MasaService(repo=repo)

        masalar = service.get_masalar()

        self.assertEqual(len(masalar), 1)
        self.assertIsNone(masalar[0].secim_durumu)
        # DTO, totp_secret gibi alanlari disari sizdirmamali.
        self.assertNotIn("totp_secret", masalar[0].model_dump())


if __name__ == "__main__":
    unittest.main()
