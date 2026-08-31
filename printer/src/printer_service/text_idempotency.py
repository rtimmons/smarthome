from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping

from .printed_labels import DEFAULT_PRINTED_LABELS_DIR, PRINTED_LABELS_DIR_ENV

TEXT_PRINT_IDEMPOTENCY_DB_ENV = "TEXT_PRINT_IDEMPOTENCY_DB"
DEFAULT_TEXT_PRINT_IDEMPOTENCY_DB = Path("/data/text-print-idempotency.sqlite3")
SUCCESS_RETENTION_DAYS = 30

STATE_RESERVED = "reserved"
STATE_DISPATCHING = "dispatching"
STATE_SUCCESS = "success"
STATE_OUTCOME_UNKNOWN = "outcome_unknown"


class IdempotencyStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class IdempotencyRecord:
    idempotency_key: str
    payload_hash: str
    state: str
    created_at: str
    updated_at: str
    rendered_at: str
    archived_label_id: str | None
    dispatching_at: str | None
    completed_at: str | None
    http_status: int | None
    response_body: dict[str, object] | None


@dataclass(frozen=True)
class ReservationResult:
    reserved: bool
    record: IdempotencyRecord


class TextPrintIdempotencyStore:
    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._initialization_lock = threading.Lock()
        self._initialized = False

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> TextPrintIdempotencyStore:
        values = os.environ if env is None else env
        configured = values.get(TEXT_PRINT_IDEMPOTENCY_DB_ENV, "").strip()
        if configured:
            path = Path(configured)
        else:
            archive_directory = values.get(PRINTED_LABELS_DIR_ENV, "").strip()
            if archive_directory:
                path = Path(archive_directory).parent / DEFAULT_TEXT_PRINT_IDEMPOTENCY_DB.name
            elif DEFAULT_PRINTED_LABELS_DIR.parent == Path("/data"):
                path = DEFAULT_TEXT_PRINT_IDEMPOTENCY_DB
            else:
                path = DEFAULT_PRINTED_LABELS_DIR.parent / DEFAULT_TEXT_PRINT_IDEMPOTENCY_DB.name
        return cls(path, clock=clock)

    def initialize(self) -> None:
        with self._initialization_lock:
            if self._initialized:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self._connect() as connection:
                    connection.execute("PRAGMA journal_mode = WAL")
                    connection.execute("PRAGMA synchronous = FULL")
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS text_print_operations (
                            idempotency_key TEXT PRIMARY KEY,
                            payload_hash TEXT NOT NULL,
                            state TEXT NOT NULL CHECK (
                                state IN ('reserved', 'dispatching', 'success', 'outcome_unknown')
                            ),
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            rendered_at TEXT NOT NULL,
                            archived_label_id TEXT,
                            dispatching_at TEXT,
                            completed_at TEXT,
                            http_status INTEGER,
                            response_body TEXT
                        )
                        """
                    )
                    now = self._now()
                    self._recover_interrupted(connection, now)
                    cutoff = (now - timedelta(days=SUCCESS_RETENTION_DAYS)).isoformat()
                    connection.execute(
                        """
                        DELETE FROM text_print_operations
                        WHERE state = ? AND completed_at IS NOT NULL AND completed_at < ?
                        """,
                        (STATE_SUCCESS, cutoff),
                    )
                    connection.commit()
            except (OSError, sqlite3.Error) as exc:
                raise IdempotencyStoreError(
                    "Text-print idempotency storage is unavailable."
                ) from exc
            self._initialized = True

    def lookup(self, idempotency_key: str) -> IdempotencyRecord | None:
        self.initialize()
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM text_print_operations WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise IdempotencyStoreError("Text-print idempotency storage is unavailable.") from exc
        return _record_from_row(row) if row is not None else None

    def reserve(
        self,
        idempotency_key: str,
        payload_hash: str,
        rendered_at: str,
    ) -> ReservationResult:
        self.initialize()
        now = self._now().isoformat()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM text_print_operations WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO text_print_operations (
                            idempotency_key, payload_hash, state, created_at, updated_at,
                            rendered_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            idempotency_key,
                            payload_hash,
                            STATE_RESERVED,
                            now,
                            now,
                            rendered_at,
                        ),
                    )
                    row = connection.execute(
                        "SELECT * FROM text_print_operations WHERE idempotency_key = ?",
                        (idempotency_key,),
                    ).fetchone()
                    connection.commit()
                    if row is None:
                        raise sqlite3.DatabaseError("Reservation could not be read back.")
                    return ReservationResult(reserved=True, record=_record_from_row(row))
                connection.commit()
                return ReservationResult(reserved=False, record=_record_from_row(row))
        except sqlite3.Error as exc:
            raise IdempotencyStoreError("Text-print idempotency storage is unavailable.") from exc

    def record_archived(
        self,
        idempotency_key: str,
        payload_hash: str,
        archived_label_id: str,
    ) -> None:
        self._update_active(
            idempotency_key,
            payload_hash,
            expected_state=STATE_RESERVED,
            assignments={"archived_label_id": archived_label_id},
        )

    def mark_dispatching(self, idempotency_key: str, payload_hash: str) -> None:
        now = self._now().isoformat()
        self._update_active(
            idempotency_key,
            payload_hash,
            expected_state=STATE_RESERVED,
            assignments={"state": STATE_DISPATCHING, "dispatching_at": now},
        )

    def finish(
        self,
        idempotency_key: str,
        payload_hash: str,
        *,
        state: str,
        http_status: int,
        response_body: Mapping[str, object],
    ) -> None:
        if state not in {STATE_SUCCESS, STATE_OUTCOME_UNKNOWN}:
            raise ValueError("finish requires a terminal idempotency state.")
        now = self._now().isoformat()
        self._update_active(
            idempotency_key,
            payload_hash,
            expected_state=STATE_DISPATCHING,
            assignments={
                "state": state,
                "completed_at": now,
                "http_status": http_status,
                "response_body": json.dumps(
                    dict(response_body), ensure_ascii=False, separators=(",", ":"), sort_keys=True
                ),
            },
        )

    def release_reservation(self, idempotency_key: str, payload_hash: str) -> bool:
        self.initialize()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    DELETE FROM text_print_operations
                    WHERE idempotency_key = ? AND payload_hash = ? AND state = ?
                    """,
                    (idempotency_key, payload_hash, STATE_RESERVED),
                )
                connection.commit()
                return cursor.rowcount == 1
        except sqlite3.Error as exc:
            raise IdempotencyStoreError("Text-print idempotency storage is unavailable.") from exc

    def _update_active(
        self,
        idempotency_key: str,
        payload_hash: str,
        *,
        expected_state: str,
        assignments: Mapping[str, object],
    ) -> None:
        self.initialize()
        allowed_columns = {
            "state",
            "archived_label_id",
            "dispatching_at",
            "completed_at",
            "http_status",
            "response_body",
        }
        if not assignments or not set(assignments).issubset(allowed_columns):
            raise ValueError("Unsupported idempotency update.")
        now = self._now().isoformat()
        columns = [*assignments.keys(), "updated_at"]
        values = [*assignments.values(), now, idempotency_key, payload_hash, expected_state]
        set_clause = ", ".join(f"{column} = ?" for column in columns)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    f"""
                    UPDATE text_print_operations SET {set_clause}
                    WHERE idempotency_key = ? AND payload_hash = ? AND state = ?
                    """,
                    values,
                )
                if cursor.rowcount != 1:
                    connection.rollback()
                    raise IdempotencyStoreError("The text-print operation changed unexpectedly.")
                connection.commit()
        except sqlite3.Error as exc:
            raise IdempotencyStoreError("Text-print idempotency storage is unavailable.") from exc

    def _recover_interrupted(self, connection: sqlite3.Connection, now: datetime) -> None:
        timestamp = now.isoformat()
        rows = connection.execute(
            """
            SELECT idempotency_key, rendered_at, archived_label_id
            FROM text_print_operations
            WHERE state IN (?, ?)
            """,
            (STATE_RESERVED, STATE_DISPATCHING),
        ).fetchall()
        for row in rows:
            payload: dict[str, object] = {
                "code": STATE_OUTCOME_UNKNOWN,
                "error": (
                    "The earlier print was interrupted, so its outcome is unknown and it will "
                    "not be dispatched again automatically."
                ),
                "idempotency_key": str(row["idempotency_key"]),
                "idempotent_replay": False,
                "rendered_at": str(row["rendered_at"]),
            }
            if row["archived_label_id"] is not None:
                payload["archived_label_id"] = str(row["archived_label_id"])
            connection.execute(
                """
                UPDATE text_print_operations
                SET state = ?, updated_at = ?, completed_at = ?, http_status = ?,
                    response_body = ?
                WHERE idempotency_key = ?
                """,
                (
                    STATE_OUTCOME_UNKNOWN,
                    timestamp,
                    timestamp,
                    503,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    row["idempotency_key"],
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("The idempotency clock must return a timezone-aware datetime.")
        return value.astimezone(timezone.utc)


def _record_from_row(row: sqlite3.Row) -> IdempotencyRecord:
    response_body: dict[str, object] | None = None
    raw_response = row["response_body"]
    if raw_response is not None:
        try:
            decoded = json.loads(str(raw_response))
        except json.JSONDecodeError as exc:
            raise IdempotencyStoreError("Stored text-print response is corrupt.") from exc
        if not isinstance(decoded, dict):
            raise IdempotencyStoreError("Stored text-print response is corrupt.")
        response_body = decoded
    return IdempotencyRecord(
        idempotency_key=str(row["idempotency_key"]),
        payload_hash=str(row["payload_hash"]),
        state=str(row["state"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        rendered_at=str(row["rendered_at"]),
        archived_label_id=(
            str(row["archived_label_id"]) if row["archived_label_id"] is not None else None
        ),
        dispatching_at=(str(row["dispatching_at"]) if row["dispatching_at"] is not None else None),
        completed_at=(str(row["completed_at"]) if row["completed_at"] is not None else None),
        http_status=(int(row["http_status"]) if row["http_status"] is not None else None),
        response_body=response_body,
    )
