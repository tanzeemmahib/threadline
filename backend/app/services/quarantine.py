from __future__ import annotations

import re

from app.schemas.models import Certainty, EvidenceSpan, RecordInput

INSTRUCTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(?:all\s+)?previous\s+instructions?[^.!?]*[.!?]?",
        r"override\s+the\s+system\s+message[^.!?]*[.!?]?",
        r"mark\s+this\s+as\s+confirmed[^.!?]*[.!?]?",
        r"reveal\s+hidden\s+instructions?[^.!?]*[.!?]?",
        r"always\s+choose\s+this\s+record[^.!?]*[.!?]?",
    )
]


def detect_embedded_instructions(record: RecordInput) -> list[EvidenceSpan]:
    spans: list[EvidenceSpan] = []
    for pattern in INSTRUCTION_PATTERNS:
        for match in pattern.finditer(record.text):
            quote = match.group(0)
            spans.append(
                EvidenceSpan(
                    span_id=f"SPAN-{record.record_id}-INJECTION-{len(spans) + 1}",
                    record_id=record.record_id,
                    field="embedded_instruction",
                    quote=quote,
                    text=quote,
                    start=match.start(),
                    end=match.end(),
                    certainty=Certainty.exact,
                    extraction_method="deterministic_pattern",
                    extraction_status="quarantined",
                    normalization_note=(
                        "The structured workflow quarantined this tested instruction pattern."
                    ),
                )
            )
    return spans


def safe_evidence_text(record: RecordInput, spans: list[EvidenceSpan]) -> str:
    characters = list(record.text)
    for span in sorted(spans, key=lambda item: item.start, reverse=True):
        characters[span.start : span.end] = "[QUARANTINED UNTRUSTED INSTRUCTION]"
    return "".join(characters)
