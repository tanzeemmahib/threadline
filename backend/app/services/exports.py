from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.models import ExportManifest, ExportRequest, StoredResult

SENSITIVE_KEYS = {"api_key", "authorization", "token", "secret", "password"}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _scrub(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _markdown(result: StoredResult) -> str:
    payload = result.payload
    lines = [
        f"# THREADLINE research result {result.result_id}",
        "",
        f"- Result type: {result.result_type}",
        f"- Provider mode: {result.provider_mode}",
        f"- Created: {result.created_at.isoformat()}",
        "- Safety: candidate connections require authorized human review; this artifact does not determine identity.",
        "",
        "## Deterministic summary",
        "",
    ]
    if "multi_seed" in payload:
        summary = payload["multi_seed"]
        lines.extend(
            [
                f"Successful runs: {summary.get('successful_runs', 0)}; failed runs: {summary.get('failed_runs', 0)}.",
                "",
                "| Metric | Mean | Std. dev. | Min | Max | 95% bootstrap CI |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for metric in summary.get("metrics", []):
            interval = metric.get("confidence_interval", {})
            lines.append(
                f"| {metric.get('metric_id')} | {metric.get('mean')} | {metric.get('standard_deviation')} "
                f"| {metric.get('minimum')} | {metric.get('maximum')} "
                f"| [{interval.get('lower')}, {interval.get('upper')}] |"
            )
    else:
        lines.append("The complete structured payload is included in the JSON export.")
    return "\n".join(lines) + "\n"


def _csv(result: StoredResult) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["result_id", "result_type", "provider_mode", "section", "metric", "value"])
    payload = result.payload
    metrics = payload.get("multi_seed", {}).get("metrics", [])
    if metrics:
        for metric in metrics:
            writer.writerow(
                [
                    result.result_id,
                    result.result_type,
                    result.provider_mode,
                    "multi_seed",
                    metric.get("metric_id"),
                    metric.get("mean"),
                ]
            )
    else:
        writer.writerow(
            [
                result.result_id,
                result.result_type,
                result.provider_mode,
                "summary",
                "payload_keys",
                len(payload),
            ]
        )
    return stream.getvalue()


def export_result(
    result: StoredResult, request: ExportRequest, export_directory: str
) -> ExportManifest:
    safe_result = result.model_copy(update={"payload": _scrub(result.payload)})
    if request.format == "json":
        content = json.dumps(
            safe_result.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True
        )
        content_type, extension = "application/json", "json"
    elif request.format == "csv":
        content = _csv(safe_result)
        content_type, extension = "text/csv; charset=utf-8", "csv"
    else:
        content = _markdown(safe_result)
        content_type, extension = "text/markdown; charset=utf-8", "md"
    encoded = content.encode("utf-8")
    export_id = f"EXPORT-{uuid4()}"
    filename = f"{result.result_id}-{export_id[-8:]}.{extension}"
    directory = Path(export_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(encoded)
    return ExportManifest(
        export_id=export_id,
        result_id=result.result_id,
        format=request.format,
        created_at=datetime.now(UTC),
        filename=filename,
        content_type=content_type,
        content_sha256=hashlib.sha256(encoded).hexdigest(),
        bytes=len(encoded),
        provider_mode=result.provider_mode,
        content=content,
    )
