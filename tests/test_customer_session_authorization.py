"""End-to-end authorization tests for the customer-session (QR) routes.

These drive the real ASGI application, so they exercise the actual FastAPI
dependency chain and the router-level ownership checks.

Why this file exists: `test_milestone9_security_audit.py` scenarios 8 and 15
`raise` the expected `HTTPException` themselves inside `assertRaises`, so they
pass regardless of what the routers do. The two confirmed IDOR paths
(`GET /api/masalar/{id}/aktif-siparis` and `POST /api/siparisler`) therefore had
no test that fails when the ownership check is removed. These tests do fail in
that case.
"""

import hashlib
import json
import unittest

from app.repositories.auth_repo import AuthRepository
from app.services.siparis_service import SiparisService


CUSTOMER_TOKEN_TABLE_5 = "a" * 64
SESSION_TABLE_ID = 5
OTHER_TABLE_ID = 6


async def asgi_request(app, method, path, *, token=None, payload=None):
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("test-client", 12345),
        "server": ("test-server", 80),
    }
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    status_code = next(
        message["status"] for message in messages if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status_code, json.loads(response_body or b"{}")


class FakeAuthRepository:
    """Returns an active session for one known token hash only."""

    def __init__(self):
        self.expected_hash = hashlib.sha256(
            CUSTOMER_TOKEN_TABLE_5.encode("utf-8")
        ).hexdigest()

    def get_active_customer_session(self, session_token_hash):
        if session_token_hash != self.expected_hash:
            return None
        return {
            "id": 1,
            "masa_id": SESSION_TABLE_ID,
            "device_id": "device-1",
            "expires_at": "2099-01-01",
        }

    def get_staff_by_id(self, user_id):  # pragma: no cover - staff path unused here
        return None


class RecordingOrderService:
    """Fails the test if business logic is reached after a rejected request."""

    def __init__(self):
        self.calls = []
        # Controller'in servise hangi oturum kimligini gecirdigi. "Benim
        # Siparislerim" gorunumunun dogru kisiye ait olmasi buna bagli.
        self.viewer_session_ids = []

    def get_masa_aktif_siparis(self, masa_id, viewer_session_id=None):
        self.calls.append(("get_masa_aktif_siparis", masa_id))
        self.viewer_session_ids.append(viewer_session_id)
        return {
            "has_active": False,
            "siparisler": [],
            "siparis": None,
            "genel_toplam": 0.0,
            "benim_toplamim": 0.0,
            "alinan_tutar": 0.0,
        }

    async def create_siparis(self, data, customer_session_id=None):  # pragma: no cover
        self.calls.append(("create_siparis", data.masa_id))
        raise AssertionError("create_siparis must not run for a rejected request")


ORDER_PAYLOAD = {
    "masa_id": OTHER_TABLE_ID,
    "toplam_tutar": 100.0,
    "odeme_yontemi": "pos",
    "urunler": [
        {"urun_id": 1, "adet": 1, "birim_fiyat": 100.0, "urun_notu": ""}
    ],
}


class CustomerSessionRouteAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from app.main import app

        self.app = app
        self.order_service = RecordingOrderService()
        app.dependency_overrides[AuthRepository] = lambda: FakeAuthRepository()
        app.dependency_overrides[SiparisService] = lambda: self.order_service

    def tearDown(self):
        self.app.dependency_overrides.clear()

    async def test_active_order_requires_a_token(self):
        status, _ = await asgi_request(
            self.app, "GET", f"/api/masalar/{SESSION_TABLE_ID}/aktif-siparis"
        )
        self.assertEqual(status, 401)
        self.assertEqual(self.order_service.calls, [])

    async def test_active_order_rejects_an_unknown_session_token(self):
        status, _ = await asgi_request(
            self.app,
            "GET",
            f"/api/masalar/{SESSION_TABLE_ID}/aktif-siparis",
            token="b" * 64,
        )
        self.assertEqual(status, 401)
        self.assertEqual(self.order_service.calls, [])

    async def test_active_order_allows_the_session_own_table(self):
        status, body = await asgi_request(
            self.app,
            "GET",
            f"/api/masalar/{SESSION_TABLE_ID}/aktif-siparis",
            token=CUSTOMER_TOKEN_TABLE_5,
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["has_active"])
        self.assertEqual(
            self.order_service.calls, [("get_masa_aktif_siparis", SESSION_TABLE_ID)]
        )

    async def test_the_verified_session_id_reaches_the_service(self):
        """"Benim Siparislerim" kimligi dogrulanmis oturumdan gelmelidir.

        Istek govdesinde boyle bir alan yok ve olmamali: istemci "bu siparisler
        benim" diye bir iddiada bulunamaz (AGENTS.md §10). Controller kimligi
        `get_current_user_or_customer` sonucundan alir.
        """
        status, _ = await asgi_request(
            self.app,
            "GET",
            f"/api/masalar/{SESSION_TABLE_ID}/aktif-siparis",
            token=CUSTOMER_TOKEN_TABLE_5,
        )

        self.assertEqual(status, 200)
        self.assertEqual(self.order_service.viewer_session_ids, [1])

    async def test_a_rejected_request_never_leaks_a_session_id(self):
        status, _ = await asgi_request(
            self.app, "GET", f"/api/masalar/{OTHER_TABLE_ID}/aktif-siparis",
            token=CUSTOMER_TOKEN_TABLE_5,
        )

        self.assertEqual(status, 403)
        self.assertEqual(self.order_service.viewer_session_ids, [])

    async def test_active_order_of_another_table_is_forbidden(self):
        """The confirmed IDOR: table 5's session must not read table 6."""
        status, body = await asgi_request(
            self.app,
            "GET",
            f"/api/masalar/{OTHER_TABLE_ID}/aktif-siparis",
            token=CUSTOMER_TOKEN_TABLE_5,
        )
        self.assertEqual(status, 403)
        self.assertIn("yetkiniz yok", body.get("detail", ""))
        self.assertEqual(self.order_service.calls, [])

    async def test_order_creation_requires_a_token(self):
        status, _ = await asgi_request(
            self.app, "POST", "/api/siparisler", payload=ORDER_PAYLOAD
        )
        self.assertEqual(status, 401)
        self.assertEqual(self.order_service.calls, [])

    async def test_order_creation_for_another_table_is_forbidden(self):
        """A table 5 session must not push an order onto table 6."""
        status, body = await asgi_request(
            self.app,
            "POST",
            "/api/siparisler",
            token=CUSTOMER_TOKEN_TABLE_5,
            payload=ORDER_PAYLOAD,
        )
        self.assertEqual(status, 403)
        self.assertIn("yetkili olduğunuz masaya", body.get("detail", ""))
        self.assertEqual(self.order_service.calls, [])


if __name__ == "__main__":
    unittest.main()
