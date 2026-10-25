import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import database


class DataSyncTests(unittest.TestCase):
    def test_records_and_formats_sync_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "fantasy.db"
            with patch.object(database, "DB_FILE", db_path):
                database.record_data_sync(
                    "ESPN",
                    "Kick-Butt Football",
                    "2026-10-22T02:00:00+00:00",
                )

                self.assertEqual(
                    database.get_last_data_sync("ESPN", "Kick-Butt Football"),
                    "2026-10-22T02:00:00+00:00",
                )
                self.assertEqual(
                    database.format_last_data_sync(
                        "ESPN",
                        "Kick-Butt Football",
                    ),
                    "Last data sync: Oct 22, 2026 at 02:00 UTC",
                )

    def test_uses_existing_cbs_roster_timestamp_without_sync_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "fantasy.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE cbs_rosters (
                        provider_player_id TEXT,
                        updated_at TEXT
                    )
                """)
                conn.execute(
                    "INSERT INTO cbs_rosters VALUES (?, ?)",
                    ("101", "2026-10-20 08:25:40"),
                )

            with patch.object(database, "DB_FILE", db_path):
                self.assertEqual(
                    database.format_last_data_sync("CBS", "CBS"),
                    "Last data sync: Oct 20, 2026 at 08:25 UTC",
                )


if __name__ == "__main__":
    unittest.main()
