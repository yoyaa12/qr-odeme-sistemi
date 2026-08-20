"""Katmanlı model ayrımının sözleşmesi: entity içeri, response dışarı.

Proje bir ORM kullanmadığı için repository katmanı ham `dict` satırlar döner.
Bu satırlar `sifre_hash`, `totp_secret`, `customer_session_id` gibi dışarı
çıkmaması gereken kolonlar taşır. Tek koruma, HTTP ucunun bir `response_model`
deklare etmesidir: FastAPI modelde tanımlı olmayan her alanı serileştirmeden
önce eler.

Bu dosya o korumayı testle sabitler:

- her API ucu bir `response_model` deklare eder (deklare etmeyen uç, ham satırı
  olduğu gibi döndürebilir),
- yanıt modelleri hassas kolonları tanımlamaz,
- entity'ler tabloların gerçek kolon adlarını taşır ve yanıt modelleriyle
  karıştırılmaz,
- repository metotlarının tamamı dönüş tipi deklare eder,
- `GET /api/masalar/{id}/aktif-siparis` gövdesi refactor öncesiyle birebir aynı
  anahtar kümesini üretir (istemci sözleşmesi bozulmadı).
"""

import ast
import glob
import os
import unittest

from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.schemas.auth.entity import GarsonCredentialsEntity, KullaniciEntity
from app.schemas.auth.response import KullaniciResponse
from app.schemas.orders.entity import SiparisEntity, SiparisWithMasaEntity
from app.schemas.orders.response import MasaAktifSiparisResponse, SiparisResponse
from app.schemas.tables.entity import MasaEntity
from app.schemas.tables.response import DinamikQRResponse, MasaResponse


def _api_routes():
    from app.main import app

    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/")
    ]


class ResponseModelCoverageTests(unittest.TestCase):
    """Her API ucu yanıt şemasını deklare etmelidir.

    Deklare etmeyen bir uç, servisten ne dönerse onu olduğu gibi serileştirir.
    Bugün zararsız görünen bir sözlüğe yarın bir kolon eklendiğinde, o kolon
    kimse fark etmeden dışarı çıkar.
    """

    def test_every_api_route_declares_a_response_model(self):
        eksik = [
            f"{sorted(route.methods)} {route.path}"
            for route in _api_routes()
            if route.response_model is None
        ]

        self.assertEqual(eksik, [], f"response_model deklare etmeyen uçlar: {eksik}")


class SensitiveColumnsStayInsideTests(unittest.TestCase):
    """Entity'nin taşıdığı hassas kolonlar yanıt modelinde tanımlı olmamalıdır."""

    def test_the_password_hash_is_read_but_never_returned(self):
        self.assertIn("sifre_hash", KullaniciEntity.__annotations__)
        self.assertIn("sifre_hash", GarsonCredentialsEntity.__annotations__)
        self.assertNotIn("sifre_hash", KullaniciResponse.model_fields)

    def test_the_table_secret_is_read_but_never_returned(self):
        """`totp_secret` masanın QR kodunu üreten sırdır.

        Masa listesi kimliksiz de okunabildiği için sırrın yanıt modelinde hiç
        tanımlı olmaması tek başına yeterli güvencedir.
        """
        self.assertIn("totp_secret", MasaEntity.__annotations__)
        self.assertNotIn("totp_secret", MasaResponse.model_fields)
        self.assertNotIn("qr_kodu", MasaResponse.model_fields)

    def test_the_session_id_is_stored_but_never_returned(self):
        """Ham oturum kimliği yerine sunucunun hesapladığı `is_mine` gider."""
        self.assertIn("customer_session_id", SiparisEntity.__annotations__)
        self.assertNotIn("customer_session_id", SiparisResponse.model_fields)
        self.assertIn("is_mine", SiparisResponse.model_fields)


class EntityShapeTests(unittest.TestCase):
    """Entity'ler tablonun gerçek kolonlarını tarif eder, yanıtı değil."""

    def test_the_order_entity_has_no_payment_method_column(self):
        """`Siparisler` tablosunda `odeme_yontemi` kolonu yoktur.

        `SiparisResponse` böyle bir alan taşır ama o, sipariş durumundan
        türetilen sunum bilgisidir. İkisinin ayrı olması, kolon sanıp sorguya
        eklemeye çalışmayı önler.
        """
        self.assertNotIn("odeme_yontemi", SiparisEntity.__annotations__)
        self.assertIn("odeme_yontemi", SiparisResponse.model_fields)

    def test_the_joined_entity_adds_the_table_number(self):
        """`SELECT s.*, m.masa_no` satırı, tablo satırından bir alan fazladır."""
        self.assertNotIn("masa_no", SiparisEntity.__annotations__)
        self.assertIn("masa_no", SiparisWithMasaEntity.__annotations__)
        # Devraldığı kolonları da taşımaya devam eder.
        self.assertIn("siparis_kodu", SiparisWithMasaEntity.__annotations__)

    def test_entities_are_plain_dicts_at_runtime(self):
        """`TypedDict` çalışma zamanında `dict`tir: davranış değişmez.

        Repository'nin döndürdüğü nesne yine düz sözlüktür; entity katmanı
        tamamen tip düzeyinde bir belgelendirmedir ve hiçbir dönüştürme
        maliyeti eklemez.
        """
        satir: MasaEntity = {
            "id": 1,
            "masa_no": "5",
            "qr_kodu": "MASA_5",
            "durum": "bos",
            "totp_secret": "SECRET",
        }
        self.assertIsInstance(satir, dict)
        self.assertEqual(satir["masa_no"], "5")


class RepositoryTypingTests(unittest.TestCase):
    """Repository metotlarının tamamı dönüş tipi deklare etmelidir.

    Mentor geri bildiriminin çıkış noktası buydu: `get_garson_credentials`
    okunurken hangi kolonların döndüğünü görmek için SQL metnini okumak
    gerekiyordu. Dönüş tipi entity'ye işaret ettiği sürece gerekmiyor.
    """

    def test_every_repository_method_declares_its_return_type(self):
        eksik = []
        for path in glob.glob("app/repositories/*.py"):
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name == "__init__":
                    continue
                if node.returns is None:
                    eksik.append(f"{os.path.basename(path)}:{node.name}")

        self.assertEqual(eksik, [], f"dönüş tipi eksik repository metotları: {eksik}")


class ActiveTableResponseContractTests(unittest.TestCase):
    """Adisyon yanıtının gövdesi refactor öncesiyle aynı kalmalıdır.

    Servis artık sözlük yerine `MasaAktifSiparisResponse` dönüyor. Bu bir iç
    değişikliktir: telefondaki istemci aynı alanları okumaya devam eder
    (`static/js/app.js` -> `has_active`, `siparisler`, `siparis`,
    `genel_toplam`, `benim_toplamim`, `redirect_masa_id`, `redirect_masa_no`).
    """

    ONCEKI_ANAHTARLAR = {
        "has_active",
        "siparisler",
        "siparis",
        "genel_toplam",
        "benim_toplamim",
        "alinan_tutar",
        "redirect_masa_id",
        "redirect_masa_no",
    }

    def test_the_json_body_keeps_exactly_the_previous_keys(self):
        payload = MasaAktifSiparisResponse(
            has_active=False,
            genel_toplam=0.0,
            alinan_tutar=0.0,
        ).model_dump(mode="json")

        self.assertEqual(set(payload), self.ONCEKI_ANAHTARLAR)

    def test_the_redirect_fields_default_to_absent(self):
        """Adisyon taşınmadıysa yönlendirme alanları `None` kalır.

        İstemci `data.redirect_masa_id` doğruysa masayı değiştiriyor; alanın
        boş yere dolması müşteriyi yanlış masaya taşırdı.
        """
        payload = MasaAktifSiparisResponse(
            has_active=False, genel_toplam=0.0, alinan_tutar=0.0
        )

        self.assertIsNone(payload.redirect_masa_id)
        self.assertIsNone(payload.redirect_masa_no)


class MissingTableQrTests(unittest.IsolatedAsyncioTestCase):
    """Olmayan masanın QR isteği 404 dönmelidir.

    Uç eskiden boş bir sözlük ile HTTP 200 dönüyordu; kasa ekranı da bunu
    modale "undefined" olarak basıyordu (`static/js/kasa.js` -> `data.token`,
    `data.qr_url`). Yanıt şeması deklare edildikten sonra boş sözlük zaten
    geçerli bir gövde değil: doğru cevap "bulunamadı".
    """

    async def test_a_missing_table_is_reported_as_404(self):
        from app.api.v1.endpoints.masalar import get_dynamic_qr

        class _MissingTableService:
            def get_dynamic_qr_info(self, masa_id):
                return None

        with self.assertRaises(HTTPException) as ctx:
            await get_dynamic_qr(999, _MissingTableService())

        self.assertEqual(ctx.exception.status_code, 404)

    async def test_an_existing_table_returns_its_live_token(self):
        from app.api.v1.endpoints.masalar import get_dynamic_qr

        beklenen = DinamikQRResponse(
            masa_id=5,
            masa_no="5",
            token="123456",
            remaining_seconds=21,
            qr_url="/m/5?token=123456",
        )

        class _PresentTableService:
            def get_dynamic_qr_info(self, masa_id):
                return beklenen

        sonuc = await get_dynamic_qr(5, _PresentTableService())

        self.assertIs(sonuc, beklenen)
        # Sır hiçbir koşulda yanıta girmez.
        self.assertNotIn("totp_secret", sonuc.model_dump())


if __name__ == "__main__":
    unittest.main()
