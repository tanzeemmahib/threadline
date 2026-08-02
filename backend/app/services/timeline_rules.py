from __future__ import annotations

import re
from datetime import datetime

from app.schemas.models import NormalizedRecord, ValidationResult


def minutes_from_text(text: str) -> int | None:
    match = re.search(r"(?i)\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?", text)
    if match is None:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    suffix = (match.group(3) or "").lower().replace(".", "")
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute


def timeline_compatibility(
    record_a: NormalizedRecord, record_b: NormalizedRecord
) -> ValidationResult:
    a_minutes = minutes_from_text(record_a.text)
    b_minutes = minutes_from_text(record_b.text)
    if a_minutes is None or b_minutes is None:
        return ValidationResult(
            check="timeline_compatibility",
            passed=True,
            detail="Timeline evidence is incomplete; compatibility remains unresolved.",
        )
    plausible = b_minutes >= a_minutes or abs(b_minutes - a_minutes) <= 30
    return ValidationResult(
        check="timeline_compatibility",
        passed=plausible,
        detail=(
            "Chronological order is plausible; this does not prove identity."
            if plausible
            else "A deterministic negative travel interval was detected."
        ),
    )


def event_sort_key(record: NormalizedRecord) -> tuple[int, datetime]:
    minutes = minutes_from_text(record.text)
    fallback = record.timestamp or datetime.min
    return (minutes if minutes is not None else 10_000, fallback)
