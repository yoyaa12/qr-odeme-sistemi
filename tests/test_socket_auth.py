import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from app.enums import UserRole
from app.core.socket_manager import (
    _coerce_masa_id,
    _extract_token_and_params,
    connect,
    on_masa_tasindi,
    on_yeni_siparis,
    on_garson_onay_talebi,
    on_durum_guncellendi,
)


class TestSocketAuthAndIsolation(unittest.TestCase):

    def test_extract_token_from_auth_dict(self):
        auth = {"token": "Bearer test-jwt-token", "masa_id": 5}
        environ = {}
        token, masa_id = _extract_token_and_params(auth, environ)
        self.assertEqual(token, "test-jwt-token")
        self.assertEqual(masa_id, 5)

    def test_extract_token_from_query_string(self):
        auth = None
        environ = {"QUERY_STRING": "token=hex-session-token&masa_id=3"}
        token, masa_id = _extract_token_and_params(auth, environ)
        self.assertEqual(token, "hex-session-token")
        self.assertEqual(masa_id, 3)

    def test_extract_token_from_query_string_variants(self):
        auth = None
        environ = {"QUERY_STRING": "access_token=jwt-token-123&masa_id=7"}
        token, masa_id = _extract_token_and_params(auth, environ)
        self.assertEqual(token, "jwt-token-123")
        self.assertEqual(masa_id, 7)

    def test_room_helpers_are_coroutines(self):
        """sio.enter_room/leave_room python-socketio 5.11+ ile coroutine oldu.

        Bu testler odaya katılımı mock'ladığı için, gerçek koddaki `await`
        eksikliğini ancak `assert_any_await` yakalayabilir. Sözleşme değişirse
        (senkron hale dönerse) burası önce kırılsın.
        """
        import inspect
        from app.core.socket_manager import sio
        self.assertTrue(inspect.iscoroutinefunction(sio.enter_room))
        self.assertTrue(inspect.iscoroutinefunction(sio.leave_room))

    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.get_session", new_callable=AsyncMock)
    def test_transport_upgrade_retains_staff_rooms(self, mock_get_session, mock_enter_room):
        mock_get_session.return_value = {
            "user_type": "STAFF",
            "role": "mutfak",
            "user_id": 2,
            "username": "User_2"
        }
        import asyncio
        asyncio.run(connect("sid-upgrade", {}, None))

        # assert_any_await: çağrının yapılmış olması yetmez, await de edilmiş olmalı.
        mock_enter_room.assert_any_await("sid-upgrade", "role_mutfak")
        mock_enter_room.assert_any_await("sid-upgrade", "staff")

    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.save_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.AuthRepository")
    @patch("app.core.socket_manager.DatabaseSession")
    @patch("app.core.socket_manager.decode_access_token")
    def test_staff_handshake_joins_staff_rooms(
        self, mock_decode, mock_db, mock_repo_cls, mock_save_session, mock_enter_room
    ):
        mock_claims = MagicMock()
        mock_claims.subject = 1
        mock_claims.role = UserRole.WAITER
        mock_decode.return_value = mock_claims

        mock_repo = MagicMock()
        mock_repo.get_staff_by_id.return_value = {"id": 1, "kullanici_adi": "garson1", "rol": "garson"}
        mock_repo_cls.return_value = mock_repo

        auth = {"token": "header.payload.signature"}
        environ = {}

        import asyncio
        asyncio.run(connect("sid-123", environ, auth))

        mock_enter_room.assert_any_await("sid-123", "role_garson")
        mock_enter_room.assert_any_await("sid-123", "staff")
        mock_save_session.assert_called_once()
        saved = mock_save_session.call_args[0][1]
        self.assertEqual(saved["user_type"], "STAFF")
        self.assertEqual(saved["role"], "garson")

    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.save_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.AuthService")
    @patch("app.core.socket_manager.AuthRepository")
    @patch("app.core.socket_manager.DatabaseSession")
    def test_customer_handshake_joins_table_room(
        self, mock_db, mock_repo_cls, mock_service_cls, mock_save_session, mock_enter_room
    ):
        mock_service = MagicMock()
        mock_service.verify_customer_session.return_value = {"id": 10, "masa_id": 2, "session_token": "hex123"}
        mock_service_cls.return_value = mock_service

        auth = {"token": "hex1234567890abcdef"}
        environ = {}

        import asyncio
        asyncio.run(connect("sid-cust", environ, auth))

        mock_enter_room.assert_awaited_once_with("sid-cust", "table_2")
        saved = mock_save_session.call_args[0][1]
        self.assertEqual(saved["user_type"], "CUSTOMER")
        self.assertEqual(saved["masa_id"], 2)

    @patch("app.core.socket_manager.sio.emit", new_callable=AsyncMock)
    def test_yeni_siparis_reaches_all_staff_exactly_once(self, mock_emit):
        payload = {"siparis_id": 99, "masa_id": 1, "toplam_tutar": 120.0}

        import asyncio
        asyncio.run(on_yeni_siparis(payload))

        # Her personel soketi hem "staff" hem "role_*" odasındadır. Aynı olayı
        # birden fazla odaya ayrı emit ile göndermek mutfakta çift zil/çift
        # veri çekmeye yol açar; tek çağrı olmalı.
        self.assertEqual(mock_emit.await_count, 1)
        self.assertEqual(mock_emit.await_args.kwargs.get("room"), "staff")

    @patch("app.core.socket_manager.sio.emit", new_callable=AsyncMock)
    def test_garson_onay_talebi_targets_service_roles_without_kitchen(self, mock_emit):
        payload = {"siparis_id": 7, "masa_id": 2, "toplam_tutar": 90.0}

        import asyncio
        asyncio.run(on_garson_onay_talebi(payload))

        self.assertEqual(mock_emit.await_count, 1)
        rooms = mock_emit.await_args.kwargs.get("room")
        self.assertCountEqual(rooms, ["role_garson", "role_kasa", "role_admin"])
        self.assertNotIn("role_mutfak", rooms)

    @patch("app.core.socket_manager.sio.emit", new_callable=AsyncMock)
    def test_events_are_never_broadcast_globally(self, mock_emit):
        """Oda filtresi olmayan emit tüm istemcilere (müşteriler dahil) gider."""
        import asyncio
        for handler in (on_yeni_siparis, on_garson_onay_talebi, on_durum_guncellendi):
            asyncio.run(handler({"siparis_id": 1, "masa_id": 3}))

        self.assertTrue(mock_emit.await_args_list)
        for call in mock_emit.await_args_list:
            self.assertIsNotNone(call.kwargs.get("room"))

    @patch("app.core.socket_manager.sio.emit", new_callable=AsyncMock)
    def test_durum_guncellendi_emits_to_table_and_staff_rooms(self, mock_emit):
        payload = {"siparis_id": 5, "masa_id": 4, "yeni_durum": "hazirlaniyor"}

        import asyncio
        asyncio.run(on_durum_guncellendi(payload))

        emitted_rooms = [call.kwargs.get("room") for call in mock_emit.call_args_list]
        self.assertIn("staff", emitted_rooms)
        self.assertIn("table_4", emitted_rooms)


class TestAnonymousSocketIsolation(unittest.TestCase):
    """Doğrulanmamış bir soket asla table_* odasına alınmamalıdır.

    table_* odaları sipariş kalemleri, toplam tutar ve ödeme durumu taşıyan
    olayları dağıtır. Daha önce `?masa_id=N` gönderen herhangi bir istemci bu
    odaya giriyordu; yani token'sız biri istediği masanın adisyonunu canlı
    izleyebiliyordu.
    """

    @patch("app.core.socket_manager.sio.save_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.get_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    def test_anonymous_client_cannot_join_a_table_room(
        self, mock_enter_room, mock_get_session, mock_save_session
    ):
        mock_get_session.return_value = {}

        import asyncio
        asyncio.run(connect("sid-anon", {"QUERY_STRING": "masa_id=5"}, None))

        joined = [call.args[1] for call in mock_enter_room.await_args_list]
        self.assertNotIn("table_5", joined)
        self.assertEqual(joined, [], "Anonim soket hicbir odaya girmemeli")

        saved = mock_save_session.call_args[0][1]
        self.assertEqual(saved["user_type"], "ANONYMOUS")
        self.assertIsNone(saved["masa_id"], "Dogrulanmamis masa_id yetki olarak saklanmamali")
        self.assertEqual(saved["claimed_masa_id"], 5)

    @patch("app.core.socket_manager.sio.save_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.get_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    def test_auth_dict_masa_id_also_grants_nothing(
        self, mock_enter_room, mock_get_session, mock_save_session
    ):
        mock_get_session.return_value = {}

        import asyncio
        asyncio.run(connect("sid-anon2", {}, {"masa_id": 9}))

        joined = [call.args[1] for call in mock_enter_room.await_args_list]
        self.assertNotIn("table_9", joined)

    @patch("app.core.socket_manager.sio.save_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.get_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    @patch("app.core.socket_manager.decode_access_token")
    def test_invalid_staff_token_does_not_fall_through_to_a_table_room(
        self, mock_decode, mock_enter_room, mock_get_session, mock_save_session
    ):
        import logging
        from app.auth.tokens import TokenValidationError

        mock_get_session.return_value = {}
        mock_decode.side_effect = TokenValidationError("bozuk imza")

        import asyncio
        # Test kasitli olarak gecersiz token gonderiyor; beklenen uyari logu
        # test ciktisini kirletmesin.
        with self.assertLogs("app.core.socket_manager", level=logging.WARNING):
            asyncio.run(connect("sid-bad", {}, {"token": "aaa.bbb.ccc", "masa_id": 4}))

        joined = [call.args[1] for call in mock_enter_room.await_args_list]
        self.assertEqual(joined, [])
        saved = mock_save_session.call_args[0][1]
        self.assertEqual(saved["user_type"], "ANONYMOUS")

    @patch("app.core.socket_manager.sio.save_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.get_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    @patch("app.core.socket_manager.AuthService")
    @patch("app.core.socket_manager.AuthRepository")
    @patch("app.core.socket_manager.DatabaseSession")
    def test_verified_customer_still_joins_its_own_table_room(
        self, mock_db, mock_repo_cls, mock_service_cls,
        mock_enter_room, mock_get_session, mock_save_session
    ):
        """Duzeltme mesru musteri akisini bozmamali."""
        mock_get_session.return_value = {}
        mock_service = MagicMock()
        mock_service.verify_customer_session.return_value = {"id": 1, "masa_id": 6}
        mock_service_cls.return_value = mock_service

        import asyncio
        asyncio.run(connect("sid-ok", {}, {"token": "hexhexhexhex", "masa_id": 6}))

        joined = [call.args[1] for call in mock_enter_room.await_args_list]
        self.assertIn("table_6", joined)


class TestTableMoveDoesNotLeakRooms(unittest.TestCase):
    """Masa taşıma, handshake'te kapatılan erişimi yan kapıdan geri vermemeli."""

    def setUp(self):
        from app.core import socket_manager
        self.sm = socket_manager
        self._orig_sessions = dict(socket_manager.MASA_SESSIONS)
        self._orig_sid_map = dict(socket_manager.SID_TO_MASA)
        self.addCleanup(self._restore)

    def _restore(self):
        self.sm.MASA_SESSIONS.clear()
        self.sm.MASA_SESSIONS.update(self._orig_sessions)
        self.sm.SID_TO_MASA.clear()
        self.sm.SID_TO_MASA.update(self._orig_sid_map)

    @patch("app.core.socket_manager.sio.emit", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.get_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.leave_room", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    def test_anonymous_socket_is_not_moved_into_the_target_table_room(
        self, mock_enter_room, mock_leave_room, mock_get_session, mock_emit
    ):
        self.sm.MASA_SESSIONS[1] = {"sid-anon"}

        async def fake_session(sid):
            return {"user_type": "ANONYMOUS", "masa_id": None, "claimed_masa_id": 1}
        mock_get_session.side_effect = fake_session

        import asyncio
        asyncio.run(on_masa_tasindi({"from_masa_id": 1, "to_masa_id": 2, "to_masa_no": "Masa 2"}))

        joined = [call.args[1] for call in mock_enter_room.await_args_list]
        self.assertNotIn("table_2", joined)
        mock_leave_room.assert_any_await("sid-anon", "table_1")

    @patch("app.core.socket_manager.sio.emit", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.get_session", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.leave_room", new_callable=AsyncMock)
    @patch("app.core.socket_manager.sio.enter_room", new_callable=AsyncMock)
    def test_verified_customer_is_moved_with_its_table(
        self, mock_enter_room, mock_leave_room, mock_get_session, mock_emit
    ):
        self.sm.MASA_SESSIONS[1] = {"sid-cust"}

        async def fake_session(sid):
            return {"user_type": "CUSTOMER", "masa_id": 1}
        mock_get_session.side_effect = fake_session

        import asyncio
        asyncio.run(on_masa_tasindi({"from_masa_id": 1, "to_masa_id": 2, "to_masa_no": "Masa 2"}))

        joined = [call.args[1] for call in mock_enter_room.await_args_list]
        self.assertIn("table_2", joined)


class TestMasaIdCoercion(unittest.TestCase):

    def test_rejects_non_positive_and_malformed_values(self):
        self.assertIsNone(_coerce_masa_id(0))
        self.assertIsNone(_coerce_masa_id(-3))
        self.assertIsNone(_coerce_masa_id("abc"))
        self.assertIsNone(_coerce_masa_id(None))
        self.assertIsNone(_coerce_masa_id({"a": 1}))

    def test_accepts_positive_integers_and_numeric_text(self):
        self.assertEqual(_coerce_masa_id(5), 5)
        self.assertEqual(_coerce_masa_id("7"), 7)


class TestSocketServerCorsPolicy(unittest.TestCase):

    def test_socket_server_is_not_open_to_every_origin(self):
        """cors_allowed_origins='*' main.py'deki kisitli CORS'u etkisiz kiliyordu."""
        from app.core.socket_manager import sio

        allowed = sio.eio.cors_allowed_origins
        self.assertNotEqual(allowed, "*")
        self.assertNotEqual(allowed, ["*"])


if __name__ == "__main__":
    unittest.main()
