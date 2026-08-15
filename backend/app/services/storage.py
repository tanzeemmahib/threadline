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

from app.schemas.models import AnalyzeRequest, AnalyzeResponse, AuditChainEvent
from app.services.audit_chain import append_audit_event, verify_audit_chain


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

    @abstractmethod
    def audit_chain(self, workflow_run_id: str) -> list[AuditChainEvent]: ...

    @abstractmethod
    def append_chain_event(
        self,
        *,
        workflow_run_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: datetime,
        **scope: Any,
    ) -> AuditChainEvent: ...

    @abstractmethod
    def persist_analysis_bundle(
        self,
        *,
        request: AnalyzeRequest,
        response: AnalyzeResponse,
        result: dict[str, Any],
    ) -> None: ...

    @abstractmethod
    def refresh_workflow_audit(self, workflow_run_id: str) -> AnalyzeResponse | None: ...


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
                CREATE TABLE IF NOT EXISTS audit_chain_events (
                    event_id TEXT PRIMARY KEY,
                    workflow_run_id TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(workflow_run_id, sequence_number)
                );
                CREATE INDEX IF NOT EXISTS audit_chain_run
                    ON audit_chain_events (workflow_run_id, sequence_number);
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

    def audit_chain(self, workflow_run_id: str) -> list[AuditChainEvent]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM audit_chain_events
                WHERE workflow_run_id=? ORDER BY sequence_number ASC
                """,
                (workflow_run_id,),
            ).fetchall()
        return [
            AuditChainEvent.model_validate(json.loads(str(row["payload_json"])))
            for row in rows
        ]

    def _replace_audit_chain(
        self, workflow_run_id: str, events: list[AuditChainEvent]
    ) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                "DELETE FROM audit_chain_events WHERE workflow_run_id=?",
                (workflow_run_id,),
            )
            connection.executemany(
                """
                INSERT INTO audit_chain_events(
                    event_id, workflow_run_id, sequence_number, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.event_id,
                        event.workflow_run_id,
                        event.sequence_number,
                        event.created_at.isoformat(),
                        json.dumps(event.model_dump(mode="json"), sort_keys=True, ensure_ascii=False),
                    )
                    for event in events
                ],
            )

    def append_chain_event(
        self,
        *,
        workflow_run_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: datetime,
        **scope: Any,
    ) -> AuditChainEvent:
        # Keep sequence allocation and insertion under one process-local lock.
        # RLock allows audit_chain() to reuse the same guard safely.
        with self._lock:
            if self.get("workflow_runs", workflow_run_id) is None:
                raise KeyError(f"Workflow run not found: {workflow_run_id}")
            events = self.audit_chain(workflow_run_id)
            event = append_audit_event(
                events,
                workflow_run_id=workflow_run_id,
                event_type=event_type,
                payload=payload,
                created_at=created_at,
                **scope,
            )
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO audit_chain_events(
                        event_id, workflow_run_id, sequence_number, created_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.workflow_run_id,
                        event.sequence_number,
                        event.created_at.isoformat(),
                        json.dumps(
                            event.model_dump(mode="json"),
                            sort_keys=True,
                            ensure_ascii=False,
                        ),
                    ),
                )
            return event

    def persist_analysis_bundle(
        self,
        *,
        request: AnalyzeRequest,
        response: AnalyzeResponse,
        result: dict[str, Any],
    ) -> None:
        workflow_run_id = response.workflow_run_id
        existing_response = self.get("workflow_runs", workflow_run_id)
        if existing_response is not None:
            existing_input = self.get("analysis_inputs", workflow_run_id)
            if existing_input is not None and AnalyzeRequest.model_validate(
                existing_input
            ).model_dump(mode="json") == request.model_dump(mode="json"):
                return
            raise ValueError(f"Workflow run already exists: {workflow_run_id}")
        self.put("analysis_inputs", workflow_run_id, request)
        self.put("workflow_runs", workflow_run_id, response)
        self.put("results", workflow_run_id, result)
        for contract in response.evidence_contracts:
            self.put("evidence_contracts", contract.contract_id, contract)
        if response.replay_manifest is not None:
            self.put("replay_manifests", workflow_run_id, response.replay_manifest)
        self._replace_audit_chain(workflow_run_id, response.audit_chain_events)

    def refresh_workflow_audit(self, workflow_run_id: str) -> AnalyzeResponse | None:
        value = self.get("workflow_runs", workflow_run_id)
        if value is None:
            return None
        response = AnalyzeResponse.model_validate(value)
        events = self.audit_chain(workflow_run_id)
        response.audit_chain_events = events
        response.audit_integrity = verify_audit_chain(workflow_run_id, events)
        self.put("workflow_runs", workflow_run_id, response)
        result = self.get("results", workflow_run_id)
        if isinstance(result, dict):
            result["payload"] = response.model_dump(mode="json")
            self.put("results", workflow_run_id, result)
        return response
