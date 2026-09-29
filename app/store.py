from __future__ import annotations

import csv
import io
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class NormalizedRecord:
    external_id: str
    name: str
    status: str


class RecordStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    external_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def upsert_many(self, records: Iterable[NormalizedRecord]) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        with sqlite3.connect(self.db_path) as connection:
            for record in records:
                existing = connection.execute(
                    "SELECT name, status FROM records WHERE external_id = ?",
                    (record.external_id,),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO records (external_id, name, status) VALUES (?, ?, ?)",
                        (record.external_id, record.name, record.status),
                    )
                    counts["inserted"] += 1
                elif existing == (record.name, record.status):
                    counts["unchanged"] += 1
                else:
                    connection.execute(
                        """
                        UPDATE records
                        SET name = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE external_id = ?
                        """,
                        (record.name, record.status, record.external_id),
                    )
                    counts["updated"] += 1
        return counts

    def list_all(self) -> list[dict[str, str]]:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT external_id, name, status FROM records ORDER BY external_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def as_csv(self) -> str:
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=["external_id", "name", "status"])
        writer.writeheader()
        writer.writerows(self.list_all())
        return output.getvalue()
