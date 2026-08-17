"""Create a one-time plaintext staff PIN delivery file outside the repository.

The script never prints credential values. It performs only a read against the
live ``Kullanicilar`` table and refuses to overwrite an existing delivery file.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from datetime import datetime, timezone


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from app.enums import UserRole  # noqa: E402
from staff_migration_db import get_strict_migration_connection  # noqa: E402


EXPECTED_USER_COUNT = 8
PIN_DIGITS = 6


def _is_inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPOSITORY_ROOT)
        return True
    except ValueError:
        return False


def _delivery_path(requested: str | None) -> Path:
    if requested:
        path = Path(requested).expanduser().resolve()
    else:
        random_suffix = secrets.token_urlsafe(12)
        path = Path(tempfile.gettempdir()) / f"staff-pin-delivery-{random_suffix}.json"
    if _is_inside_repository(path):
        raise RuntimeError("Delivery file must be outside the Git repository")
    return path


def _read_live_staff() -> list[dict[str, object]]:
    conn = None
    cursor = None
    try:
        conn, _ = get_strict_migration_connection(autocommit=True)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, kullanici_adi, rol, sifre_hash
            FROM dbo.Kullanicilar
            ORDER BY id ASC
            """
        )
        rows = cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    if len(rows) != EXPECTED_USER_COUNT:
        raise RuntimeError("Expected staff count does not match")
    allowed_roles = {role.value for role in UserRole}
    users = []
    for row in rows:
        user_id, username, role, old_credential = row
        if (
            not isinstance(user_id, int)
            or user_id <= 0
            or not isinstance(username, str)
            or not username.strip()
            or role not in allowed_roles
            or not isinstance(old_credential, str)
            or len(old_credential) != PIN_DIGITS
            or not old_credential.isascii()
            or not old_credential.isdigit()
        ):
            raise RuntimeError("Live staff preflight failed")
        users.append(
            {
                "id": user_id,
                "username": username,
                "role": role,
                "old_credential": old_credential,
            }
        )
    if len({user["username"] for user in users}) != EXPECTED_USER_COUNT:
        raise RuntimeError("Live staff usernames are not unique")
    return users


def _new_unique_pins(users: list[dict[str, object]]) -> list[str]:
    old_values = {str(user["old_credential"]) for user in users}
    generated: set[str] = set()
    while len(generated) < len(users):
        candidate = str(secrets.randbelow(900_000) + 100_000)
        if candidate not in old_values:
            generated.add(candidate)
    return list(generated)


def _write_delivery(path: Path, users: list[dict[str, object]], pins: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "credentials": [
            {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "pin": pin,
            }
            for user, pin in zip(users, pins, strict=True)
        ],
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Absolute repository-external delivery path")
    args = parser.parse_args()

    path = _delivery_path(args.output)
    users = _read_live_staff()
    pins = _new_unique_pins(users)
    _write_delivery(path, users, pins)
    print(f"delivery_file={path}")
    print(f"credential_count={len(users)}")
    print("plaintext_values_printed=false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"delivery_generation_failed={type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
