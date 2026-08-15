from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.audit_chain import verify_audit_chain  # noqa: E402
from app.services.storage import SQLiteRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Tamper with a copied THREADLINE database.")
    parser.add_argument("--database", required=True)
    parser.add_argument("--run-id", required=True)
    arguments = parser.parse_args()
    source_path = Path(arguments.database).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    with tempfile.TemporaryDirectory(prefix="threadline-audit-smoke-") as directory:
        copy_path = Path(directory) / "copied-test.db"
        source = sqlite3.connect(source_path)
        copied = sqlite3.connect(copy_path)
        source.backup(copied)
        source.close()
        row = copied.execute(
            """
            SELECT event_id, payload_json FROM audit_chain_events
            WHERE workflow_run_id=? ORDER BY sequence_number LIMIT 1 OFFSET 1
            """,
            (arguments.run_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("The copied run has fewer than two audit events.")
        payload = json.loads(row[1])
        payload["payload"]["tamper_probe"] = "one-byte-equivalent-change"
        copied.execute(
            "UPDATE audit_chain_events SET payload_json=? WHERE event_id=?",
            (json.dumps(payload, sort_keys=True, ensure_ascii=False), row[0]),
        )
        copied.commit()
        copied.close()
        events = SQLiteRepository(str(copy_path)).audit_chain(arguments.run_id)
        result = verify_audit_chain(arguments.run_id, events)
        print(f"status={result.status.value}")
        print(f"first_invalid_event_id={result.first_invalid_event_id}")
        print(f"first_invalid_sequence={result.first_invalid_sequence}")
        return 0 if not result.valid and result.first_invalid_event_id == row[0] else 1


if __name__ == "__main__":
    raise SystemExit(main())
