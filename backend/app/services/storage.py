from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class Repository(ABC):
    @abstractmethod
    def put(self, collection: str, key: str, value: Any) -> None: ...

    @abstractmethod
    def get(self, collection: str, key: str) -> Any | None: ...

    @abstractmethod
    def list_items(self, collection: str, *, limit: int = 100) -> list[Any]: ...

    @abstractmethod
    def put_audit(self, case_id: str, event_id: str, value: Any) -> None: ...

    @abstractmethod
    def case_audit(self, case_id: str) -> list[Any]: ...


class SQLiteRepository(Repository):
    """Small durable JSON document store with searchable THREADLINE metadata."""

    def __init__(self, database_path: str) -> None:
        self.database_path = str(Path(database_path).resolve())
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    collection TEXT NOT NULL,
                    key TEXT NOT NULL,
                    case_id TEXT,
                    provider_mode TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (collection, key)
                );
                CREATE INDEX IF NOT EXISTS artifacts_case_id
                    ON artifacts (case_id, created_at);
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS audit_case_id
                    ON audit_events (case_id, created_at);
                """
            )

    def put(self, collection: str, key: str, value: Any) -> None:
        payload = _json_value(value)
        if not isinstance(payload, dict):
            payload = {"value": payload}
        created_at = str(payload.get("created_at") or datetime.now(UTC).isoformat())
        case_id = payload.get("case_id")
        provider_mode = payload.get("provider_mode") or payload.get("mode")
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO artifacts(collection, key, case_id, provider_mode, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection, key) DO UPDATE SET
                    case_id=excluded.case_id,
                    provider_mode=excluded.provider_mode,
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (collection, key, case_id, provider_mode, created_at, encoded),
            )

    def get(self, collection: str, key: str) -> Any | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM artifacts WHERE collection=? AND key=?",
                (collection, key),
            ).fetchone()
        return None if row is None else json.loads(str(row["payload_json"]))

    def list_items(self, collection: str, *, limit: int = 100) -> list[Any]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM artifacts
                WHERE collection=? ORDER BY created_at DESC LIMIT ?
                """,
                (collection, max(1, min(limit, 1_000))),
            ).fetchall()
        return [json.loads(str(row["payload_json"])) for row in rows]

    def put_audit(self, case_id: str, event_id: str, value: Any) -> None:
        payload = _json_value(value)
        if not isinstance(payload, dict):
            raise TypeError("audit event must serialize to an object")
        created_at = str(payload.get("timestamp") or datetime.now(UTC).isoformat())
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_events(event_id, case_id, created_at, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    case_id=excluded.case_id,
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (
                    event_id,
                    case_id,
                    created_at,
                    json.dumps(payload, sort_keys=True, ensure_ascii=False),
                ),
            )

    def case_audit(self, case_id: str) -> list[Any]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM audit_events
                WHERE case_id=? ORDER BY created_at ASC, event_id ASC
                """,
                (case_id,),
            ).fetchall()
        return [json.loads(str(row["payload_json"])) for row in rows]
