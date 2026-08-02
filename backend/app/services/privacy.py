from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Redaction:
    kind: str
    original: str
    replacement: str
    reason: str


PATTERNS = {
    "phone_number": re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)"),
    "email_address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "residential_address": re.compile(
        r"\b\d{1,5}\s+[A-Za-z][A-Za-z ]+\s+(?:Street|St|Road|Rd|Avenue|Ave)\b",
        re.IGNORECASE,
    ),
    "medical_note": re.compile(r"(?i)\b(?:diagnosis|medical note):\s*[^.;]+[.;]?"),
}


def redact_text(value: str) -> tuple[str, list[Redaction]]:
    redacted = value
    redactions: list[Redaction] = []
    for kind, pattern in PATTERNS.items():
        for match in list(pattern.finditer(redacted))[::-1]:
            replacement = f"[REDACTED {kind.upper()}]"
            original = match.group(0)
            redacted = redacted[: match.start()] + replacement + redacted[match.end() :]
            redactions.append(
                Redaction(
                    kind=kind,
                    original=original,
                    replacement=replacement,
                    reason="Not necessary for the frontend reviewer role.",
                )
            )
    return redacted, list(reversed(redactions))
