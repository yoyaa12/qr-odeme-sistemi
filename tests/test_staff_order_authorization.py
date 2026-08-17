import unittest

from fastapi import HTTPException

from app.enums import OrderAction, OrderStatus, UserRole
from app.services.order_authorization import enforce_order_status_role


class StaffOrderAuthorizationTests(unittest.TestCase):
    def assert_allowed(self, role, target):
        enforce_order_status_role(role, target)

    def assert_forbidden(self, role, target):
        with self.assertRaises(HTTPException) as raised:
            enforce_order_status_role(role, target)
        self.assertEqual(raised.exception.status_code, 403)

    def test_role_specific_status_targets(self):
        self.assert_allowed(UserRole.KITCHEN, OrderStatus.PREPARING)
        self.assert_allowed(UserRole.KITCHEN, OrderStatus.READY)
        self.assert_forbidden(UserRole.KITCHEN, OrderStatus.DELIVERED)

        self.assert_allowed(UserRole.WAITER, OrderStatus.DELIVERED)
        self.assert_allowed(UserRole.WAITER, OrderAction.CASH_COLLECTED)
        self.assert_forbidden(UserRole.WAITER, OrderStatus.PREPARING)

        self.assert_allowed(UserRole.CASHIER, OrderAction.CASH_COLLECTED)
        self.assert_forbidden(UserRole.CASHIER, OrderStatus.READY)

    def test_admin_can_use_all_legacy_status_targets(self):
        for target in (*OrderStatus, *OrderAction):
            with self.subTest(target=target):
                self.assert_allowed(UserRole.ADMIN, target)


if __name__ == "__main__":
    unittest.main()
