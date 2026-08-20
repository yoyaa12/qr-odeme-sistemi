"""Tests for the table check ("adisyon") boundary and sliding session expiry.

The project has no separate check entity: the moment a table returns to `bos`
is what separates one party's bill from the next party's. There are two routes
to `bos` and only the cashier one used to close the check properly. After an
automatic empty the previous guest's session stayed valid for the rest of its
lifetime, and once a new party claimed the table that stale session could push
orders onto their bill without any physical proof.

These tests pin both routes to the same behaviour, and pin the sliding expiry
that lets a seated guest keep their session alive while a departed guest's
session runs out.
"""

import asyncio
import contextlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.enums import OrderAction, OrderStatus, PaymentStatus, TableStatus, UserRole
from app.auth.models import StaffPrincipal
from app.schemas.orders import DurumGuncelleModel
from app.services import siparis_service as siparis_service_module
from app.services.auth_service import (
    CUSTOMER_SESSION_TTL_MINUTES,
    AuthService,
    _SESSION_REFRESH_AFTER_MINUTES,
)
from app.services.siparis_service import SiparisService


@contextlib.contextmanager
def _no_transaction():
    yield None


class TableCheckClosingTests(unittest.TestCase):
    """Both routes to an empty table must close the check identically."""

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
        self.principal = StaffPrincipal(user_id=3, username="garson_ali", role=UserRole.WAITER)

        self.order_row = {
            "id": 77,
            "masa_id": 5,
            "masa_no": "Masa 5",
            "siparis_kodu": "SIP-XYZ999",
            "toplam_tutar": 250.0,
            "odeme_durumu": PaymentStatus.PAID.value,
            "siparis_durumu": OrderStatus.READY.value,
            "olusturma_tarihi": None,
            "garson_adi": None,
            "device_id": "device-eski-musteri",
        }
        self.mock_siparis_repo.get_by_id.return_value = self.order_row
        self.mock_siparis_repo.get_siparis_detaylari.return_value = []

        patcher_tx = patch("app.services.siparis_service.db_transaction", _no_transaction)
        patcher_bus = patch("app.services.siparis_service.event_bus")
        patcher_browsing = patch("app.services.siparis_service.clear_browsing_table")
        for patcher in (patcher_tx, patcher_bus, patcher_browsing):
            self.addCleanup(patcher.stop)
        patcher_tx.start()
        patcher_bus.start().publish = AsyncMock()
        self.mock_clear_browsing = patcher_browsing.start()

    def _assert_check_closed_for(self, masa_id):
        self.mock_siparis_repo.clear_active_orders_for_masa.assert_called_with(masa_id)
        self.mock_siparis_repo.close_tahsilatlar_for_masa.assert_called_with(masa_id)
        self.mock_auth_repo.revoke_all_sessions_for_masa.assert_called_with(masa_id)
        self.mock_clear_browsing.assert_called_with(masa_id)
        self.mock_masa_repo.update_durum.assert_called_with(masa_id, TableStatus.EMPTY.value)

    def _deliver_last_order(self):
        data = DurumGuncelleModel(yeni_durum=OrderStatus.DELIVERED.value)
        return asyncio.run(self.service.update_siparis_durumu(77, data, self.principal))

    def test_cashier_clearing_closes_the_check(self):
        asyncio.run(self.service.clear_masa(5))
        self._assert_check_closed_for(5)

    def test_automatic_emptying_closes_the_check_the_same_way(self):
        """The regression: this route used to skip session revocation."""
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 0

        self._deliver_last_order()

        self._assert_check_closed_for(5)

    def test_the_previous_guests_sessions_are_revoked_on_automatic_emptying(self):
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 0

        self._deliver_last_order()

        self.mock_auth_repo.revoke_all_sessions_for_masa.assert_called_once_with(5)

    def test_a_table_with_work_left_keeps_its_check_open(self):
        """Other guests are still eating: nobody's session may be revoked."""
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 2
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 0

        self._deliver_last_order()

        self.mock_auth_repo.revoke_all_sessions_for_masa.assert_not_called()
        self.mock_siparis_repo.clear_active_orders_for_masa.assert_not_called()
        self.mock_masa_repo.update_durum.assert_not_called()

    def test_an_unpaid_order_keeps_the_check_open(self):
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 1

        self._deliver_last_order()

        self.mock_auth_repo.revoke_all_sessions_for_masa.assert_not_called()
        self.mock_masa_repo.update_durum.assert_not_called()

    def test_cash_collection_also_closes_the_check(self):
        """`nakit_tahsil_edildi` marks the order delivered and paid in one step."""
        self.order_row["siparis_durumu"] = OrderStatus.CASH_PENDING.value
        self.order_row["odeme_durumu"] = PaymentStatus.PENDING.value
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 0

        data = DurumGuncelleModel(yeni_durum=OrderAction.CASH_COLLECTED.value)
        asyncio.run(self.service.update_siparis_durumu(77, data, self.principal))

        self._assert_check_closed_for(5)

    def test_closing_a_check_drops_its_table_move_redirects(self):
        siparis_service_module.TABLE_MOVES_MAP[9] = 5
        self.mock_siparis_repo.get_active_count_for_masa.return_value = 0
        self.mock_siparis_repo.get_unpaid_count_for_masa.return_value = 0

        self._deliver_last_order()

        self.assertNotIn(9, siparis_service_module.TABLE_MOVES_MAP)


class SlidingSessionExpiryTests(unittest.TestCase):
    """A session in use is renewed; an abandoned one is left to expire."""

    def setUp(self):
        self.repo = MagicMock()
        self.service = AuthService(repo=self.repo)
        self.raw_token = "c" * 64

    def _session(self, minutes_remaining):
        return {
            "id": 1,
            "masa_id": 5,
            "device_id": "device-1",
            "expires_at": datetime.now() + timedelta(minutes=minutes_remaining),
        }

    def test_a_stale_session_is_pushed_back_to_the_full_lifetime(self):
        session = self._session(minutes_remaining=20)
        self.repo.get_active_customer_session.return_value = session

        result = self.service.verify_customer_session(self.raw_token)

        self.assertIsNotNone(result)
        self.repo.touch_customer_session.assert_called_once()
        _token_hash, new_expiry = self.repo.touch_customer_session.call_args[0]
        remaining = new_expiry - datetime.now()
        self.assertGreater(remaining, timedelta(minutes=CUSTOMER_SESSION_TTL_MINUTES - 1))
        self.assertLessEqual(remaining, timedelta(minutes=CUSTOMER_SESSION_TTL_MINUTES))

    def test_a_fresh_session_is_not_rewritten_on_every_request(self):
        self.repo.get_active_customer_session.return_value = self._session(
            minutes_remaining=CUSTOMER_SESSION_TTL_MINUTES - 1
        )

        self.service.verify_customer_session(self.raw_token)

        self.repo.touch_customer_session.assert_not_called()

    def test_the_refresh_threshold_is_the_documented_one(self):
        just_inside = CUSTOMER_SESSION_TTL_MINUTES - _SESSION_REFRESH_AFTER_MINUTES + 1
        self.repo.get_active_customer_session.return_value = self._session(just_inside)
        self.service.verify_customer_session(self.raw_token)
        self.repo.touch_customer_session.assert_not_called()

        just_outside = CUSTOMER_SESSION_TTL_MINUTES - _SESSION_REFRESH_AFTER_MINUTES - 1
        self.repo.get_active_customer_session.return_value = self._session(just_outside)
        self.service.verify_customer_session(self.raw_token)
        self.repo.touch_customer_session.assert_called_once()

    def test_a_revoked_session_is_never_renewed(self):
        """Revocation wins: the repository returns nothing, so nothing is touched."""
        self.repo.get_active_customer_session.return_value = None

        self.assertIsNone(self.service.verify_customer_session(self.raw_token))
        self.repo.touch_customer_session.assert_not_called()

    def test_a_non_datetime_expiry_is_tolerated(self):
        self.repo.get_active_customer_session.return_value = {
            "id": 1,
            "masa_id": 5,
            "device_id": "device-1",
            "expires_at": "2099-01-01",
        }

        result = self.service.verify_customer_session(self.raw_token)

        self.assertEqual(result["masa_id"], 5)
        self.repo.touch_customer_session.assert_not_called()

    def test_an_empty_token_never_reaches_the_database(self):
        self.assertIsNone(self.service.verify_customer_session(""))
        self.repo.get_active_customer_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
