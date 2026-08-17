import unittest

from app.enums import OrderStatus, PaymentMethod, PaymentStatus
from app.services.siparis_service import SiparisService


class OrderStatusMappingTests(unittest.TestCase):
    def setUp(self):
        self.service = SiparisService(
            siparis_repo=None,
            masa_repo=None,
            urun_repo=None,
            auth_repo=None,
        )

    def test_pos_initial_state_is_unchanged(self):
        payment, order = self.service._determine_initial_status(PaymentMethod.POS)
        self.assertEqual(payment, PaymentStatus.PAID.value)
        self.assertEqual(order, OrderStatus.PAID_IN_KITCHEN.value)

    def test_cash_initial_state_is_unchanged(self):
        payment, order = self.service._determine_initial_status(PaymentMethod.CASH)
        self.assertEqual(payment, PaymentStatus.PENDING.value)
        self.assertEqual(order, OrderStatus.CASH_PENDING.value)

    def test_waiter_at_cashier_initial_state_is_unchanged(self):
        payment, order = self.service._determine_initial_status(
            PaymentMethod.WAITER_AT_CASHIER
        )
        self.assertEqual(payment, PaymentStatus.PENDING.value)
        self.assertEqual(order, OrderStatus.WAITER_APPROVAL_PENDING.value)


if __name__ == "__main__":
    unittest.main()
