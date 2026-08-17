import os
import json
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_staff, require_roles
from app.auth.models import StaffPrincipal
from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.rate_limit import ProcessLocalLoginRateLimiter
from app.auth.tokens import (
    ExpiredTokenError,
    TokenValidationError,
    WrongTokenTypeError,
    create_access_token,
    decode_access_token,
)
from app.enums import TokenType, UserRole
from app.repositories.auth_repo import AuthRepository
from app.schemas.auth import LoginModel
from app.services.auth_service import AuthService
from app.services.urun_service import UrunService


TEST_SECRET = "test-only-secret-material-with-at-least-thirty-two-bytes"


class FakeClock:
    def __init__(self, value: float = 1_000.0):
        self.value = value

    def __call__(self) -> float:
        return self.value


class FakeAuthRepository:
    def __init__(self, user=None):
        self.user = user
        self.calls = 0

    def get_staff_by_id(self, user_id):
        self.calls += 1
        if self.user and self.user["id"] == user_id:
            return self.user
        return None


class FakeCredentialRepository:
    def __init__(self, users=None):
        self.users = users or {}

    def get_user_by_username(self, username):
        return self.users.get(username)

    def get_garson_credentials(self):
        return []


class FakeProductService:
    def add_urun(self, data):
        return 321


class PasswordHashTests(unittest.TestCase):
    def test_hash_is_salted_and_verifies_without_storing_plaintext(self):
        password = "unit-test-password-not-a-production-pin"
        first = hash_password(password)
        second = hash_password(password)

        self.assertNotEqual(first, second)
        self.assertNotIn(password, first)
        self.assertTrue(verify_password(password, first))
        self.assertFalse(verify_password("wrong-password", first))
        self.assertFalse(needs_rehash(first))

    def test_legacy_plaintext_is_never_accepted_as_an_encoded_hash(self):
        self.assertFalse(verify_password("legacy-value", "legacy-value"))
        self.assertTrue(needs_rehash("legacy-value"))


class StaffTokenTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"AUTH_SECRET_KEY": TEST_SECRET})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def _token(self, **kwargs):
        return create_access_token(
            7,
            UserRole.ADMIN,
            now=10_000,
            expires_in=300,
            **kwargs,
        )

    def test_valid_staff_token_round_trip(self):
        claims = decode_access_token(self._token(), now=10_001)

        self.assertEqual(claims.subject, 7)
        self.assertIs(claims.role, UserRole.ADMIN)
        self.assertIs(claims.token_type, TokenType.STAFF)
        self.assertEqual(claims.expires_at, 10_300)

    def test_invalid_signature_is_rejected(self):
        token = self._token()
        replacement = "A" if token[-1] != "A" else "B"
        tampered = token[:-1] + replacement

        with self.assertRaises(TokenValidationError):
            decode_access_token(tampered, now=10_001)

    def test_expired_token_is_rejected(self):
        with self.assertRaises(ExpiredTokenError):
            decode_access_token(self._token(), now=10_300)

    def test_customer_token_is_rejected_by_staff_decoder(self):
        customer_token = self._token(token_type=TokenType.CUSTOMER_SESSION)

        with self.assertRaises(WrongTokenTypeError):
            decode_access_token(customer_token, now=10_001)


class StaffDependencyTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"AUTH_SECRET_KEY": TEST_SECRET})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def test_missing_token_returns_401_without_database_lookup(self):
        repo = FakeAuthRepository()

        with self.assertRaises(HTTPException) as caught:
            get_current_staff(None, repo)

        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(repo.calls, 0)

    def test_invalid_token_returns_401_without_database_lookup(self):
        repo = FakeAuthRepository()
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="not-a-valid-token",
        )

        with self.assertRaises(HTTPException) as caught:
            get_current_staff(credentials, repo)

        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(repo.calls, 0)

    def test_expired_token_returns_401(self):
        token = create_access_token(
            7,
            UserRole.ADMIN,
            now=1,
            expires_in=60,
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.auth.tokens.time.time", return_value=61):
            with self.assertRaises(HTTPException) as caught:
                get_current_staff(credentials, FakeAuthRepository())

        self.assertEqual(caught.exception.status_code, 401)

    def test_wrong_token_type_returns_401_without_database_lookup(self):
        repo = FakeAuthRepository()
        token = create_access_token(
            7,
            UserRole.ADMIN,
            token_type=TokenType.CUSTOMER_SESSION,
            now=1,
            expires_in=300,
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.auth.tokens.time.time", return_value=2):
            with self.assertRaises(HTTPException) as caught:
                get_current_staff(credentials, repo)

        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(repo.calls, 0)

    def test_database_role_must_still_match_signed_role(self):
        repo = FakeAuthRepository(
            {"id": 7, "kullanici_adi": "Test User", "rol": UserRole.WAITER.value}
        )
        token = create_access_token(
            7,
            UserRole.ADMIN,
            now=1,
            expires_in=300,
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.auth.tokens.time.time", return_value=2):
            with self.assertRaises(HTTPException) as caught:
                get_current_staff(credentials, repo)

        self.assertEqual(caught.exception.status_code, 401)

    def test_wrong_role_returns_403_after_authentication(self):
        guard = require_roles(UserRole.ADMIN)
        waiter = StaffPrincipal(1, "Test Waiter", UserRole.WAITER)

        with self.assertRaises(HTTPException) as caught:
            guard(waiter)

        self.assertEqual(caught.exception.status_code, 403)

    def test_allowed_role_returns_same_principal(self):
        guard = require_roles(UserRole.ADMIN, UserRole.WAITER)
        waiter = StaffPrincipal(1, "Test Waiter", UserRole.WAITER)

        self.assertIs(guard(waiter), waiter)


class StaffLoginServiceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"AUTH_SECRET_KEY": TEST_SECRET})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def test_encoded_password_login_issues_staff_token(self):
        password = "service-test-password-not-a-production-pin"
        repo = FakeCredentialRepository(
            {
                "Test Admin": {
                    "id": 7,
                    "kullanici_adi": "Test Admin",
                    "rol": UserRole.ADMIN.value,
                    "sifre_hash": hash_password(password),
                }
            }
        )
        service = AuthService(repo)
        limiter = ProcessLocalLoginRateLimiter(max_failures=5, window_seconds=60)

        result = service.login(
            LoginModel(kullanici_adi="Test Admin", sifre=password),
            "test-client",
            limiter=limiter,
        )

        self.assertIs(result.principal.role, UserRole.ADMIN)
        self.assertIs(decode_access_token(result.access_token).token_type, TokenType.STAFF)

    def test_plaintext_database_value_and_unknown_user_are_rejected(self):
        repo = FakeCredentialRepository(
            {
                "Legacy User": {
                    "id": 1,
                    "kullanici_adi": "Legacy User",
                    "rol": UserRole.WAITER.value,
                    "sifre_hash": "legacy-plaintext-value",
                }
            }
        )
        service = AuthService(repo)
        limiter = ProcessLocalLoginRateLimiter(max_failures=10, window_seconds=60)

        for username, password in (
            ("Legacy User", "legacy-plaintext-value"),
            ("Missing User", "unrelated-password"),
        ):
            with self.assertRaises(HTTPException) as caught:
                service.login(
                    LoginModel(kullanici_adi=username, sifre=password),
                    "test-client",
                    limiter=limiter,
                )
            self.assertEqual(caught.exception.status_code, 401)

    def test_success_does_not_clear_source_ip_failures(self):
        password = "rate-limit-test-password"
        repo = FakeCredentialRepository(
            {
                "Test Admin": {
                    "id": 7,
                    "kullanici_adi": "Test Admin",
                    "rol": UserRole.ADMIN.value,
                    "sifre_hash": hash_password(password),
                }
            }
        )
        service = AuthService(repo)
        limiter = ProcessLocalLoginRateLimiter(max_failures=2, window_seconds=60)
        ip_key = service._rate_key("staff-login-ip", "test-client")
        account_key = service._rate_key("staff-login-account", "test admin")
        limiter.record_failure((ip_key, account_key))

        service.login(
            LoginModel(kullanici_adi="Test Admin", sifre=password),
            "test-client",
            limiter=limiter,
        )
        limiter.record_failure((ip_key,))

        self.assertFalse(limiter.check((ip_key,)).allowed)
        self.assertTrue(limiter.check((account_key,)).allowed)


class LoginRateLimitTests(unittest.TestCase):
    def test_limit_blocks_after_configured_failures_and_recovers_after_window(self):
        clock = FakeClock()
        limiter = ProcessLocalLoginRateLimiter(
            max_failures=3,
            window_seconds=60,
            clock=clock,
        )
        key = ("test-client",)

        for _ in range(3):
            self.assertTrue(limiter.check(key).allowed)
            limiter.record_failure(key)

        blocked = limiter.check(key)
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.retry_after_seconds, 60)

        clock.value += 61
        self.assertTrue(limiter.check(key).allowed)

    def test_success_clears_only_the_supplied_keys(self):
        limiter = ProcessLocalLoginRateLimiter(max_failures=1, window_seconds=60)
        limiter.record_failure(("account-a", "client-a"))
        limiter.record_success(("account-a",))

        self.assertTrue(limiter.check(("account-a",)).allowed)
        self.assertFalse(limiter.check(("client-a",)).allowed)

    def test_active_bucket_count_has_a_hard_cap(self):
        limiter = ProcessLocalLoginRateLimiter(
            max_failures=5,
            window_seconds=60,
            max_buckets=3,
        )
        for index in range(10):
            limiter.record_failure((f"client-{index}",))

        self.assertLessEqual(len(limiter._failures), 3)


class StaffAuthOpenApiTests(unittest.TestCase):
    def test_auth_me_publishes_bearer_security_requirement(self):
        from app.main import app

        schema = app.openapi()
        schemes = schema["components"]["securitySchemes"]
        operation = schema["paths"]["/api/auth/me"]["get"]

        self.assertEqual(schemes["StaffBearer"]["scheme"], "bearer")
        self.assertEqual(schemes["StaffBearer"]["bearerFormat"], "JWT")
        self.assertIn({"StaffBearer": []}, operation["security"])

    def test_current_operational_routes_publish_staff_security(self):
        from app.main import app

        schema = app.openapi()
        protected_operations = (
            ("/api/auth/me", "get"),
            ("/api/garsonlar", "get"),
            ("/api/garson/ban-device", "post"),
            ("/api/siparisler", "get"),
            ("/api/siparisler/{siparis_id}/durum", "patch"),
            ("/api/siparisler/{siparis_id}", "put"),
            ("/api/masalar/move", "post"),
            ("/api/masalar/{masa_id}/clear", "post"),
            ("/api/masalar/all-dynamic-qrs", "get"),
            ("/api/masalar/{masa_id}/dynamic-qr", "get"),
            ("/api/admin/urunler", "post"),
            ("/api/admin/urunler/{urun_id}", "put"),
            ("/api/admin/urunler/{urun_id}", "delete"),
            ("/api/admin/kategoriler", "post"),
            ("/api/admin/kategoriler/{kategori_id}", "delete"),
            ("/api/admin/masalar", "post"),
            ("/api/admin/masalar/{masa_id}", "delete"),
        )
        for path, method in protected_operations:
            with self.subTest(path=path, method=method):
                self.assertIn(
                    {"StaffBearer": []},
                    schema["paths"][path][method]["security"],
                )

        self.assertNotIn("security", schema["paths"]["/api/auth/login"]["post"])
        self.assertIn("security", schema["paths"]["/api/siparisler"]["post"])


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


class StaffProtectedRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"AUTH_SECRET_KEY": TEST_SECRET})
        self.environment.start()

    def tearDown(self):
        from app.main import app

        app.dependency_overrides.clear()
        self.environment.stop()

    async def test_real_admin_route_enforces_401_403_and_allows_admin(self):
        from app.main import app

        users = {
            1: {"id": 1, "kullanici_adi": "Test Waiter", "rol": UserRole.WAITER.value},
            7: {"id": 7, "kullanici_adi": "Test Admin", "rol": UserRole.ADMIN.value},
        }
        def auth_repo_override():
            class MultiUserRepo:
                def get_staff_by_id(self, user_id):
                    return users.get(user_id)

            return MultiUserRepo()

        app.dependency_overrides[AuthRepository] = auth_repo_override
        app.dependency_overrides[UrunService] = lambda: FakeProductService()
        payload = {
            "kategori_id": 1,
            "urun_adi": "Test Product",
            "aciklama": "",
            "fiyat": 1,
            "gorsel_url": "",
            "stok_miktari": 1,
        }

        missing_status, _ = await asgi_request(
            app,
            "POST",
            "/api/admin/urunler",
            payload=payload,
        )
        invalid_status, _ = await asgi_request(
            app,
            "POST",
            "/api/admin/urunler",
            token="invalid-token",
            payload=payload,
        )
        waiter_token = create_access_token(1, UserRole.WAITER, expires_in=300)
        waiter_status, _ = await asgi_request(
            app,
            "POST",
            "/api/admin/urunler",
            token=waiter_token,
            payload=payload,
        )
        admin_token = create_access_token(7, UserRole.ADMIN, expires_in=300)
        admin_status, admin_body = await asgi_request(
            app,
            "POST",
            "/api/admin/urunler",
            token=admin_token,
            payload=payload,
        )

        self.assertEqual(missing_status, 401)
        self.assertEqual(invalid_status, 401)
        self.assertEqual(waiter_status, 403)
        self.assertEqual(admin_status, 200)
        self.assertEqual(admin_body["id"], 321)

    async def test_customer_and_expired_tokens_are_401_on_real_staff_route(self):
        from app.main import app

        app.dependency_overrides[AuthRepository] = lambda: FakeAuthRepository()
        customer_token = create_access_token(
            7,
            UserRole.ADMIN,
            token_type=TokenType.CUSTOMER_SESSION,
            expires_in=300,
        )
        expired_token = create_access_token(
            7,
            UserRole.ADMIN,
            now=int(time.time()) - 301,
            expires_in=300,
        )

        customer_status, _ = await asgi_request(
            app,
            "GET",
            "/api/garsonlar",
            token=customer_token,
        )
        expired_status, _ = await asgi_request(
            app,
            "GET",
            "/api/garsonlar",
            token=expired_token,
        )

        self.assertEqual(customer_status, 401)
        self.assertEqual(expired_status, 401)


if __name__ == "__main__":
    unittest.main()
