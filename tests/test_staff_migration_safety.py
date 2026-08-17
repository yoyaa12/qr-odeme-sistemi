import sys
from pathlib import Path
import unittest
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import generate_staff_pin_delivery as delivery_tool
import migrate_staff_credentials as migration_tool


class FailingUpdateCursor:
    def __init__(self):
        self.rowcount = -1
        self.update_calls = 0
        self.closed = False

    def execute(self, query, params=()):
        if query.lstrip().upper().startswith("UPDATE"):
            self.update_calls += 1
            self.rowcount = 1 if self.update_calls == 1 else 0
        return self

    def close(self):
        self.closed = True


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = FailingUpdateCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class StaffMigrationSafetyTests(unittest.TestCase):
    def test_any_missing_update_rolls_back_the_whole_transaction(self):
        connection = RecordingConnection()
        delivery = [
            {
                "id": index,
                "username": f"Test User {index}",
                "role": "garson",
                "pin": "test-value-never-used-as-a-real-pin",
            }
            for index in range(1, 9)
        ]
        live_rows = [
            {
                "id": item["id"],
                "username": item["username"],
                "role": item["role"],
                "old_credential": "legacy-test-value",
            }
            for item in delivery
        ]

        with (
            patch.object(
                migration_tool,
                "get_strict_migration_connection",
                return_value=(connection, "test-server"),
            ),
            patch.object(migration_tool, "hash_password", return_value="encoded-test-hash"),
            patch.object(migration_tool, "get_auth_secret", return_value=b"x" * 32),
            patch.object(migration_tool, "_locked_live_rows", return_value=live_rows),
            patch.object(migration_tool, "_validate_preflight", return_value=None),
        ):
            with self.assertRaises(RuntimeError):
                migration_tool._transactional_rotation(delivery)

        self.assertEqual(connection.cursor_instance.update_calls, 2)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_update_sql_is_parameterized_and_contains_no_embedded_hash(self):
        source = migration_tool.UPDATE_SQL_PATH.read_text(encoding="utf-8")

        self.assertEqual(source.count("?"), 4)
        self.assertIn("WHERE id = ?", source)
        self.assertIn("AND sifre_hash = ?", source)
        self.assertNotIn("pbkdf2_sha256$", source)

    def test_delivery_tools_refuse_repository_paths(self):
        repository_file = REPOSITORY_ROOT / "must-not-be-created.json"

        with self.assertRaises(RuntimeError):
            delivery_tool._delivery_path(str(repository_file))
        self.assertTrue(migration_tool._is_inside_repository(repository_file))
        self.assertFalse(repository_file.exists())

    def test_migration_script_never_deletes_the_delivery_file(self):
        source = Path(migration_tool.__file__).read_text(encoding="utf-8")

        self.assertNotIn(".unlink(", source)
        self.assertNotIn("remove(", source)


if __name__ == "__main__":
    unittest.main()
