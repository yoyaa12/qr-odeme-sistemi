import unittest

from app.enums import OrderStatus, PaymentStatus, UserRole
from app.repositories.auth_repo import AuthRepository
from app.repositories.siparis_repo import SiparisRepository


class RecordingDatabase:
    def __init__(self, query_result=None):
        self.query_result = query_result
        self.queries = []
        self.non_queries = []

    def execute_query(self, query, params=(), fetch_all=True, fetch_one=False):
        self.queries.append(
            {
                "query": query,
                "params": params,
                "fetch_all": fetch_all,
                "fetch_one": fetch_one,
            }
        )
        return self.query_result

    def execute_non_query(self, query, params=()):
        self.non_queries.append({"query": query, "params": params})


class RepositoryEnumQueryTests(unittest.TestCase):
    def test_staff_login_loads_hash_by_username_for_application_verification(self):
        db = RecordingDatabase(query_result=None)
        AuthRepository(db=db).get_user_by_username("Test User")

        recorded = db.queries[0]
        normalized_sql = " ".join(recorded["query"].split()).lower()
        self.assertEqual(recorded["params"], ("Test User",))
        self.assertIn("sifre_hash", normalized_sql)
        self.assertIn("where kullanici_adi = ?", normalized_sql)
        self.assertNotIn("and sifre_hash = ?", normalized_sql)

    def test_waiter_pin_login_loads_only_verified_waiter_role_candidates(self):
        db = RecordingDatabase(query_result=[])
        AuthRepository(db=db).get_garson_credentials()

        recorded = db.queries[0]
        self.assertEqual(recorded["params"], (UserRole.WAITER.value,))
        self.assertIn("sifre_hash", recorded["query"])

    def test_waiter_filter_uses_verified_role_parameter(self):
        db = RecordingDatabase(query_result=[])
        AuthRepository(db=db).get_all_garsonlar()

        self.assertEqual(db.queries[0]["params"], (UserRole.WAITER.value,))

    def test_active_order_query_uses_terminal_status_parameters(self):
        db = RecordingDatabase(query_result=[])
        SiparisRepository(db=db).get_all_active_by_masa_id(7)

        self.assertEqual(
            db.queries[0]["params"],
            (7, OrderStatus.CANCELLED.value, OrderStatus.PAID_CLOSED.value),
        )

    def test_active_count_query_preserves_all_operational_statuses(self):
        db = RecordingDatabase(query_result={"cnt": 3})
        count = SiparisRepository(db=db).get_active_count_for_masa(7)

        self.assertEqual(count, 3)
        self.assertEqual(db.queries[0]["params"][0], 7)
        self.assertEqual(
            db.queries[0]["params"][1:],
            (
                OrderStatus.CASH_PENDING.value,
                OrderStatus.PAID_IN_KITCHEN.value,
                OrderStatus.PREPARING.value,
                OrderStatus.READY.value,
                OrderStatus.WAITER_APPROVAL_PENDING.value,
                OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
            ),
        )

    def test_clear_query_preserves_closed_and_paid_values(self):
        db = RecordingDatabase()
        SiparisRepository(db=db).clear_active_orders_for_masa(7)

        self.assertEqual(
            db.non_queries[0]["params"],
            (
                OrderStatus.PAID_CLOSED.value,
                PaymentStatus.PAID.value,
                7,
                OrderStatus.CANCELLED.value,
                OrderStatus.PAID_CLOSED.value,
            ),
        )


if __name__ == "__main__":
    unittest.main()
