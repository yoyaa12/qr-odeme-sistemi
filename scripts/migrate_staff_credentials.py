"""Rotate exactly eight live staff credentials in one SQL transaction.

The plaintext input must be the one-time, repository-external JSON file created
by ``generate_staff_pin_delivery.py``. Credential values and hashes are never
printed. The delivery file is intentionally not deleted by this script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from fastapi import HTTPException  # noqa: E402

from app.auth.passwords import hash_password, verify_password  # noqa: E402
from app.auth.rate_limit import ProcessLocalLoginRateLimiter  # noqa: E402
from app.auth.tokens import decode_access_token, get_auth_secret  # noqa: E402
from app.enums import TokenType, UserRole  # noqa: E402
from app.repositories.auth_repo import AuthRepository  # noqa: E402
from app.schemas.auth import GarsonPinVerifyModel, LoginModel  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from staff_migration_db import get_strict_migration_connection  # noqa: E402


EXPECTED_USER_COUNT = 8
PIN_DIGITS = 6
UPDATE_SQL_PATH = Path(__file__).with_name("update_staff_credential.sql")


class ConnectionDatabaseSession:
    """Minimal repository adapter bound to the migration transaction."""

    def __init__(self, connection):
        self.connection = connection

    def execute_query(self, query, params=(), fetch_all=True, fetch_one=False):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description]
            if fetch_one:
                row = cursor.fetchone()
                return dict(zip(columns, row)) if row else None
            rows = cursor.fetchall() if fetch_all else []
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cursor.close()


def _is_inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPOSITORY_ROOT)
        return True
    except ValueError:
        return False


def _load_delivery(path: Path) -> list[dict[str, object]]:
    if _is_inside_repository(path):
        raise RuntimeError("Delivery file must be outside the Git repository")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise RuntimeError("Unsupported delivery format")
    credentials = payload.get("credentials")
    if not isinstance(credentials, list) or len(credentials) != EXPECTED_USER_COUNT:
        raise RuntimeError("Expected credential count does not match")

    allowed_roles = {role.value for role in UserRole}
    normalized = []
    for item in credentials:
        if not isinstance(item, dict):
            raise RuntimeError("Invalid delivery record")
        user_id = item.get("id")
        username = item.get("username")
        role = item.get("role")
        pin = item.get("pin")
        if (
            not isinstance(user_id, int)
            or isinstance(user_id, bool)
            or user_id <= 0
            or not isinstance(username, str)
            or not username.strip()
            or role not in allowed_roles
            or not isinstance(pin, str)
            or len(pin) != PIN_DIGITS
            or not pin.isascii()
            or not pin.isdigit()
        ):
            raise RuntimeError("Invalid delivery record")
        normalized.append(
            {"id": user_id, "username": username, "role": role, "pin": pin}
        )

    if len({item["id"] for item in normalized}) != EXPECTED_USER_COUNT:
        raise RuntimeError("Delivery user IDs are not unique")
    if len({item["username"] for item in normalized}) != EXPECTED_USER_COUNT:
        raise RuntimeError("Delivery usernames are not unique")
    if len({item["pin"] for item in normalized}) != EXPECTED_USER_COUNT:
        raise RuntimeError("Delivery PINs are not unique")
    return sorted(normalized, key=lambda item: int(item["id"]))


def _locked_live_rows(cursor) -> list[dict[str, object]]:
    cursor.execute(
        """
        SELECT id, kullanici_adi, rol, sifre_hash
        FROM dbo.Kullanicilar WITH (UPDLOCK, HOLDLOCK)
        ORDER BY id ASC
        """
    )
    return [
        {
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "old_credential": row[3],
        }
        for row in cursor.fetchall()
    ]


def _validate_preflight(
    live_rows: list[dict[str, object]],
    delivery: list[dict[str, object]],
) -> None:
    if len(live_rows) != EXPECTED_USER_COUNT:
        raise RuntimeError("Expected live staff count does not match")
    expected_identity = [
        (item["id"], item["username"], item["role"])
        for item in delivery
    ]
    live_identity = [
        (item["id"], item["username"], item["role"])
        for item in live_rows
    ]
    if live_identity != expected_identity:
        raise RuntimeError("Live staff identity changed after delivery generation")

    old_values = set()
    for row in live_rows:
        old_value = row["old_credential"]
        if (
            not isinstance(old_value, str)
            or len(old_value) != PIN_DIGITS
            or not old_value.isascii()
            or not old_value.isdigit()
        ):
            raise RuntimeError("Live credentials are not in the expected legacy format")
        old_values.add(old_value)
    if old_values.intersection({str(item["pin"]) for item in delivery}):
        raise RuntimeError("A replacement PIN collides with a legacy credential")


def _verify_service_flows(
    connection,
    delivery: list[dict[str, object]],
    old_values: list[str],
) -> tuple[int, int, int, int, int]:
    service = AuthService(AuthRepository(ConnectionDatabaseSession(connection)))
    limiter = ProcessLocalLoginRateLimiter(max_failures=100, window_seconds=300)
    old_rejected = 0
    new_accepted = 0
    staff_tokens = 0
    waiter_old_rejected = 0
    waiter_new_accepted = 0

    for item, old_value in zip(delivery, old_values, strict=True):
        client_host = f"migration-verification-{item['id']}"
        try:
            service.login(
                LoginModel(kullanici_adi=str(item["username"]), sifre=old_value),
                client_host,
                limiter=limiter,
            )
        except HTTPException as exc:
            if exc.status_code != 401:
                raise RuntimeError("Legacy login failed with an unexpected status") from exc
            old_rejected += 1
        else:
            raise RuntimeError("A legacy credential still authenticates")

        result = service.login(
            LoginModel(kullanici_adi=str(item["username"]), sifre=str(item["pin"])),
            client_host,
            limiter=limiter,
        )
        claims = decode_access_token(result.access_token)
        if (
            claims.subject != item["id"]
            or claims.role.value != item["role"]
            or claims.token_type is not TokenType.STAFF
        ):
            raise RuntimeError("Issued STAFF token claims do not match the live user")
        new_accepted += 1
        staff_tokens += 1

        if item["role"] == UserRole.WAITER.value:
            try:
                service.verify_garson_pin(
                    GarsonPinVerifyModel(pin_code=old_value),
                    f"migration-waiter-old-{item['id']}",
                    limiter=limiter,
                )
            except HTTPException as exc:
                if exc.status_code != 401:
                    raise RuntimeError("Legacy waiter PIN failed unexpectedly") from exc
                waiter_old_rejected += 1
            else:
                raise RuntimeError("A legacy waiter PIN still authenticates")

            waiter_result = service.verify_garson_pin(
                GarsonPinVerifyModel(pin_code=str(item["pin"])),
                f"migration-waiter-new-{item['id']}",
                limiter=limiter,
            )
            waiter_claims = decode_access_token(waiter_result.access_token)
            if waiter_claims.subject != item["id"] or waiter_claims.role is not UserRole.WAITER:
                raise RuntimeError("Waiter PIN flow returned the wrong principal")
            waiter_new_accepted += 1

    return (
        old_rejected,
        new_accepted,
        staff_tokens,
        waiter_old_rejected,
        waiter_new_accepted,
    )


def _transactional_rotation(
    delivery: list[dict[str, object]],
) -> tuple[list[str], tuple[int, int, int, int, int], str]:
    update_sql = UPDATE_SQL_PATH.read_text(encoding="utf-8").strip()
    encoded_hashes = [hash_password(str(item["pin"])) for item in delivery]
    get_auth_secret()

    conn = None
    cursor = None
    old_values: list[str] = []
    try:
        conn, server_identity = get_strict_migration_connection(autocommit=False)
        cursor = conn.cursor()
        cursor.execute("SET XACT_ABORT ON")
        live_rows = _locked_live_rows(cursor)
        _validate_preflight(live_rows, delivery)
        old_values = [str(row["old_credential"]) for row in live_rows]

        updated_rows = 0
        for item, encoded_hash, old_value in zip(
            delivery,
            encoded_hashes,
            old_values,
            strict=True,
        ):
            cursor.execute(
                update_sql,
                (
                    encoded_hash,
                    item["id"],
                    item["username"],
                    old_value,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("A credential update did not affect exactly one row")
            updated_rows += cursor.rowcount
        if updated_rows != EXPECTED_USER_COUNT:
            raise RuntimeError("Credential update count mismatch")

        cursor.execute(
            """
            SELECT id, kullanici_adi, rol, sifre_hash
            FROM dbo.Kullanicilar
            ORDER BY id ASC
            """
        )
        updated = cursor.fetchall()
        if len(updated) != EXPECTED_USER_COUNT:
            raise RuntimeError("Post-update staff count mismatch")
        for row, item, old_value in zip(updated, delivery, old_values, strict=True):
            if (row[0], row[1], row[2]) != (item["id"], item["username"], item["role"]):
                raise RuntimeError("Post-update identity mismatch")
            if not verify_password(str(item["pin"]), row[3]):
                raise RuntimeError("Replacement credential verification failed")
            if verify_password(old_value, row[3]):
                raise RuntimeError("Legacy credential unexpectedly verifies")

        service_results = _verify_service_flows(conn, delivery, old_values)
        conn.commit()
        return old_values, service_results, server_identity
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def _post_commit_login_smoke(
    delivery: list[dict[str, object]],
) -> int:
    conn = None
    try:
        conn, _ = get_strict_migration_connection(autocommit=True)
        service = AuthService(AuthRepository(ConnectionDatabaseSession(conn)))
        limiter = ProcessLocalLoginRateLimiter(max_failures=100, window_seconds=300)
        accepted = 0
        for item in delivery:
            result = service.login(
                LoginModel(
                    kullanici_adi=str(item["username"]),
                    sifre=str(item["pin"]),
                ),
                f"post-commit-verification-{item['id']}",
                limiter=limiter,
            )
            claims = decode_access_token(result.access_token)
            if claims.subject != item["id"] or claims.role.value != item["role"]:
                raise RuntimeError("Post-commit login returned the wrong principal")
            accepted += 1
        return accepted
    finally:
        if conn is not None:
            conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-file", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Required acknowledgement for the transactional live update",
    )
    args = parser.parse_args()
    if not args.apply:
        raise RuntimeError("Refusing to update without --apply")

    delivery_path = Path(args.delivery_file).expanduser().resolve()
    delivery = _load_delivery(delivery_path)
    _old_values, verification, server_identity = _transactional_rotation(delivery)
    (
        old_rejected,
        new_accepted,
        staff_tokens,
        waiter_old_rejected,
        waiter_new_accepted,
    ) = verification
    print("transaction_committed=true")
    print(f"updated_rows={len(delivery)}")
    print(f"database_server={server_identity}")
    print(f"legacy_logins_rejected={old_rejected}")
    print(f"replacement_logins_accepted={new_accepted}")
    print(f"staff_tokens_verified={staff_tokens}")
    print(f"legacy_waiter_pin_logins_rejected={waiter_old_rejected}")
    print(f"replacement_waiter_pin_logins_accepted={waiter_new_accepted}")
    try:
        post_commit_accepted = _post_commit_login_smoke(delivery)
    except Exception as exc:
        print("post_commit_verification_passed=false", file=sys.stderr)
        print(f"post_commit_verification_failed={type(exc).__name__}", file=sys.stderr)
        return 2
    print("post_commit_verification_passed=true")
    print(f"post_commit_logins_accepted={post_commit_accepted}")
    print("plaintext_values_printed=false")
    print(f"delivery_file_retained={delivery_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"credential_migration_failed={type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
