import unittest

from pydantic import ValidationError

from app.enums import (
    OrderAction,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    TableStatus,
    UserRole,
)
from app.schemas.auth import GarsonPinResponse, GarsonResponse, KullaniciResponse, LoginResponse
from app.schemas.orders import (
    DurumGuncelleModel,
    SiparisOlusturModel,
    SiparisResponse,
)
from app.schemas.schemas import SiparisOlusturModel as CompatibilityOrderModel
from app.schemas.schemas import GarsonResponse as CompatibilityWaiterResponse
from app.schemas.tables import MasaResponse


class EnumAndSchemaTests(unittest.TestCase):
    def test_verified_live_role_values_are_supported(self):
        for value in ("admin", "garson", "kasa", "mutfak"):
            user = KullaniciResponse(id=1, rol=value)
            self.assertIsInstance(user.rol, UserRole)
            self.assertEqual(user.model_dump(mode="json")["rol"], value)

    def test_legacy_waiter_response_export_is_preserved(self):
        self.assertIs(CompatibilityWaiterResponse, GarsonResponse)

    def test_login_and_pin_response_supports_extended_ttl(self):
        user = KullaniciResponse(id=1, kullanici_adi="kasa1", rol=UserRole.CASHIER)
        login_resp = LoginResponse(
            status="success",
            user=user,
            access_token="test_token",
            expires_in=2592000,
        )
        self.assertEqual(login_resp.expires_in, 2592000)

        garson = KullaniciResponse(id=1, garson_adi="garson1", rol=UserRole.WAITER)
        garson_resp = GarsonPinResponse(
            status="success",
            garson=garson,
            access_token="test_token",
            expires_in=2592000,
        )
        self.assertEqual(garson_resp.expires_in, 2592000)

    def test_current_frontend_order_payload_remains_compatible(self):
        payload = {
            "masa_id": 5,
            "toplam_tutar": 125.5,
            "odeme_yontemi": "garson_kasada",
            "device_id": "device-1",
            "current_totp_token": "123456",
            "urunler": [
                {
                    "urun_id": 10,
                    "adet": 2,
                    "birim_fiyat": 62.75,
                    "urun_notu": "Soğansız",
                }
            ],
        }

        order = SiparisOlusturModel.model_validate(payload)

        self.assertEqual(order.odeme_yontemi, PaymentMethod.WAITER_AT_CASHIER)
        self.assertEqual(order.model_dump(mode="json"), payload)
        self.assertIs(CompatibilityOrderModel, SiparisOlusturModel)

    def test_arbitrary_order_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            DurumGuncelleModel(yeni_durum="attacker_defined_status")

    def test_legacy_cash_collection_command_is_still_accepted(self):
        update = DurumGuncelleModel(yeni_durum="nakit_tahsil_edildi")
        self.assertEqual(update.yeni_durum, OrderAction.CASH_COLLECTED)

    def test_status_input_keeps_legacy_case_normalization(self):
        update = DurumGuncelleModel(yeni_durum="  HAZIR  ")
        self.assertEqual(update.yeni_durum, OrderStatus.READY)

    def test_non_positive_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            SiparisOlusturModel(
                masa_id=1,
                toplam_tutar=1,
                urunler=[{"urun_id": 1, "adet": 0, "birim_fiyat": 1}],
            )

        with self.assertRaises(ValidationError):
            SiparisOlusturModel(
                masa_id=1,
                toplam_tutar=1,
                urunler=[{"urun_id": 1, "adet": -1, "birim_fiyat": 1}],
            )

    def test_negative_price_and_total_are_rejected(self):
        with self.assertRaises(ValidationError):
            SiparisOlusturModel(
                masa_id=1,
                toplam_tutar=-1,
                urunler=[{"urun_id": 1, "adet": 1, "birim_fiyat": 1}],
            )

        with self.assertRaises(ValidationError):
            SiparisOlusturModel(
                masa_id=1,
                toplam_tutar=1,
                urunler=[{"urun_id": 1, "adet": 1, "birim_fiyat": -1}],
            )

    def test_empty_order_is_rejected(self):
        with self.assertRaises(ValidationError):
            SiparisOlusturModel(masa_id=1, toplam_tutar=0, urunler=[])

    def test_current_database_response_values_serialize_as_plain_strings(self):
        response = SiparisResponse(
            id=1,
            masa_id=5,
            masa_no="Masa 5",
            siparis_kodu="SIP-ABC123",
            toplam_tutar=100,
            odeme_durumu="odendi",
            siparis_durumu="teslim_edildi",
        )
        table = MasaResponse(id=5, masa_no="Masa 5", durum="bos")

        dumped = response.model_dump(mode="json")
        self.assertEqual(dumped["odeme_durumu"], PaymentStatus.PAID.value)
        self.assertEqual(dumped["siparis_durumu"], OrderStatus.DELIVERED.value)
        self.assertEqual(table.model_dump(mode="json")["durum"], TableStatus.EMPTY.value)


if __name__ == "__main__":
    unittest.main()
