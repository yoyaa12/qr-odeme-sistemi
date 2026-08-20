import hashlib
import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import (
    get_current_staff,
    get_current_user_or_customer,
    require_roles,
)
from app.auth.models import StaffPrincipal
from app.auth.tokens import create_access_token
from app.enums import (
    OrderAction,
    OrderStatus,
    TableStatus,
    UserRole,
)
from app.schemas.orders import SiparisItemModel
from app.services.auth_service import AuthService
from app.services.order_authorization import (
    enforce_order_status_role,
    validate_order_state_transition,
)
from app.services.siparis_service import SiparisService


class Milestone9SecurityAuditTests(unittest.TestCase):
    """
    Milestone 9: Comprehensive automated security audit tests.
    Covers the 15 required test scenarios from SECURITY_AUTH_REFACTOR.md (Section 19).
    """

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_auth_repo = MagicMock()
        self.mock_siparis_repo = MagicMock()
        self.mock_masa_repo = MagicMock()
        self.mock_urun_repo = MagicMock()

        self.auth_service = AuthService(repo=self.mock_auth_repo)
        self.siparis_service = SiparisService(
            siparis_repo=self.mock_siparis_repo,
            masa_repo=self.mock_masa_repo,
            urun_repo=self.mock_urun_repo,
            auth_repo=self.mock_auth_repo,
        )

    # -------------------------------------------------------------------------
    # Scenario 1: Missing token -> protected staff endpoint -> 401
    # -------------------------------------------------------------------------
    def test_01_missing_token_returns_401(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_staff(None, self.mock_auth_repo)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("WWW-Authenticate", ctx.exception.headers)

    # -------------------------------------------------------------------------
    # Scenario 2: Invalid / malformed / tampered token -> 401
    # -------------------------------------------------------------------------
    def test_02_invalid_token_returns_401(self):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.structure")
        with self.assertRaises(HTTPException) as ctx:
            get_current_staff(creds, self.mock_auth_repo)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------------------
    # Scenario 3: Expired token -> 401
    # -------------------------------------------------------------------------
    def test_03_expired_staff_token_returns_401(self):
        token = create_access_token(1, UserRole.WAITER, now=1000, expires_in=300)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with patch("app.auth.tokens.time.time", return_value=2000):
            with self.assertRaises(HTTPException) as ctx:
                get_current_staff(creds, self.mock_auth_repo)
            self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------------------
    # Scenario 4: Valid WAITER token -> ADMIN endpoint -> 403 Forbidden
    # -------------------------------------------------------------------------
    def test_04_valid_waiter_token_accessing_admin_endpoint_returns_403(self):
        waiter_principal = StaffPrincipal(user_id=2, username="garson1", role=UserRole.WAITER)
        admin_guard = require_roles(UserRole.ADMIN)

        with self.assertRaises(HTTPException) as ctx:
            admin_guard(waiter_principal)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("yetkili değil", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # Scenario 5: Valid ADMIN token -> ADMIN endpoint -> Success
    # -------------------------------------------------------------------------
    def test_05_valid_admin_token_accessing_admin_endpoint_succeeds(self):
        admin_principal = StaffPrincipal(user_id=1, username="admin1", role=UserRole.ADMIN)
        admin_guard = require_roles(UserRole.ADMIN)

        result = admin_guard(admin_principal)
        self.assertEqual(result.role, UserRole.ADMIN)
        self.assertEqual(result.user_id, 1)

    # -------------------------------------------------------------------------
    # Scenario 6: CUSTOMER_SESSION token -> Staff / Admin endpoint -> Rejected
    # -------------------------------------------------------------------------
    def test_06_customer_session_token_rejected_on_staff_decoder(self):
        customer_hex_token = "a" * 64
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=customer_hex_token)

        # get_current_staff only accepts 3-part signed JWTs
        with self.assertRaises(HTTPException) as ctx:
            get_current_staff(creds, self.mock_auth_repo)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------------------
    # Scenario 7: Customer Session Table 5 -> Table 5 active order -> Success
    # -------------------------------------------------------------------------
    def test_07_customer_session_matches_table_id_access_allowed(self):
        raw_token = "b" * 64
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        self.mock_auth_repo.get_active_customer_session.return_value = {
            "id": 10,
            "masa_id": 5,
            "device_id": "dev123",
            "expires_at": "2099-01-01",
        }

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw_token)
        actor = get_current_user_or_customer(creds, self.mock_auth_repo)

        self.assertIsInstance(actor, dict)
        self.assertEqual(actor["masa_id"], 5)
        # Checking table ownership logic for Table 5
        requested_masa_id = 5
        self.assertEqual(actor["masa_id"], requested_masa_id)

    # -------------------------------------------------------------------------
    # Scenario 8: Customer Session Table 5 -> Table 6 active order -> 403 (IDOR blocked)
    #
    # Moved to tests/test_customer_session_authorization.py. The version that
    # lived here raised the expected HTTPException itself inside assertRaises
    # instead of calling the router, so it passed even with the ownership check
    # deleted from app/api/v1/endpoints/masalar.py. The replacement drives the
    # real ASGI application and fails when the check is removed.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Scenario 9: No token -> GET /api/masalar/{id}/aktif-siparis -> 401
    # -------------------------------------------------------------------------
    def test_09_no_token_on_aktif_siparis_returns_401(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user_or_customer(None, self.mock_auth_repo)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------------------
    # Scenario 10: WAITER -> Legal order status transition -> Success
    # -------------------------------------------------------------------------
    def test_10_waiter_legal_status_transition_allowed(self):
        try:
            enforce_order_status_role(UserRole.WAITER, OrderStatus.WAITER_APPROVED_IN_KITCHEN)
            enforce_order_status_role(UserRole.WAITER, OrderAction.CASH_COLLECTED)
            enforce_order_status_role(UserRole.WAITER, OrderStatus.DELIVERED)
        except HTTPException:
            self.fail("Waiter legal order status transition raised unexpected HTTPException!")

    # -------------------------------------------------------------------------
    # Scenario 11: WAITER -> KITCHEN-only status transition -> 403
    # -------------------------------------------------------------------------
    def test_11_waiter_attempting_kitchen_transition_returns_403(self):
        with self.assertRaises(HTTPException) as ctx:
            enforce_order_status_role(UserRole.WAITER, OrderStatus.PREPARING)
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx2:
            enforce_order_status_role(UserRole.WAITER, OrderStatus.READY)
        self.assertEqual(ctx2.exception.status_code, 403)

    # -------------------------------------------------------------------------
    # Scenario 12: KITCHEN -> READY -> DELIVERED -> 403
    # -------------------------------------------------------------------------
    def test_12_kitchen_attempting_delivery_returns_403(self):
        with self.assertRaises(HTTPException) as ctx:
            enforce_order_status_role(UserRole.KITCHEN, OrderStatus.DELIVERED)
        self.assertEqual(ctx.exception.status_code, 403)

    # -------------------------------------------------------------------------
    # Scenario 13: Invalid / illegal order state transition -> 400
    # -------------------------------------------------------------------------
    def test_13_illegal_state_transition_returns_400(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_order_state_transition(OrderStatus.DELIVERED.value, OrderStatus.PREPARING)
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx2:
            validate_order_state_transition(OrderStatus.PAID_CLOSED.value, OrderStatus.PREPARING)
        self.assertEqual(ctx2.exception.status_code, 400)

    # -------------------------------------------------------------------------
    # Scenario 14: Client price manipulation -> Backend enforces DB price
    # -------------------------------------------------------------------------
    def test_14_client_underpaid_price_rejected_and_authoritative_calculated(self):
        db_product = {
            "id": 10,
            "urun_adi": "Izgara Köfte",
            "fiyat": 200.0,
            "stok_miktari": 50,
            "aktif_mi": True,
        }
        self.mock_urun_repo.get_by_id.return_value = db_product

        # Attacker tries to submit birim_fiyat = 1.0 TL
        item = SiparisItemModel(urun_id=10, adet=2, birim_fiyat=1.0, urun_notu="")

        with self.assertRaises(HTTPException) as ctx:
            self.siparis_service._calculate_item_authoritative_price(db_product, item)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("düşük olamaz", ctx.exception.detail)

        # Legitimate order with option delta: "1.5 Porsiyon" adds 40% (80 TL)
        item_with_option = SiparisItemModel(urun_id=10, adet=2, birim_fiyat=280.0, urun_notu="1.5 Porsiyon")
        unit_price, line_total = self.siparis_service._calculate_item_authoritative_price(db_product, item_with_option)
        self.assertEqual(unit_price, 280.0)
        self.assertEqual(line_total, 560.0)

    # -------------------------------------------------------------------------
    # Scenario 15: Client manipulates table_id on order submission -> 403
    #
    # Moved to tests/test_customer_session_authorization.py for the same reason
    # as scenario 8: the version here asserted that `raise HTTPException(403)`
    # raises an HTTPException, which is true regardless of the application.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Scenario 16: Table Clear -> Session Revocation and TOTP Secret Rotation
    # -------------------------------------------------------------------------
    def test_16_table_clear_revokes_sessions_and_resets_state(self):
        import asyncio

        self.mock_masa_repo.get_by_id.return_value = {"id": 4, "masa_no": "Masa 4", "durum": "dolu"}

        asyncio.run(self.siparis_service.clear_masa(4))

        self.mock_masa_repo.update_durum.assert_called_with(4, TableStatus.EMPTY.value)
        self.mock_siparis_repo.clear_active_orders_for_masa.assert_called_with(4)
        self.mock_siparis_repo.close_tahsilatlar_for_masa.assert_called_with(4)
        self.mock_auth_repo.revoke_all_sessions_for_masa.assert_called_with(4)


if __name__ == "__main__":
    unittest.main()
