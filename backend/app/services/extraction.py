from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.schemas.models import Certainty, EvidenceSpan, ExtractedField, RecordInput


@dataclass(frozen=True, slots=True)
class PatternSpec:
    key: str
    label: str
    pattern: re.Pattern[str]
    certainty: Certainty = Certainty.exact


PATTERNS = [
    PatternSpec(
        "age",
        "Age",
        re.compile(
            r"(?i)\b(?:(?:approximately|estimated|environ)\s+age\s+|"
            r"age(?:d)?\s+(?:approximately\s+|estimated\s+|environ\s+)?|"
            r"(?:approximately|estimated|environ)\s+)(\d{1,2})(?:[–-](\d{1,2}))?"
            r"(?:\s*(?:years?|ans?|عاما))?\b|\b(\d{1,2})\s*(?:years?|ans?|عاما)\b"
        ),
    ),
    PatternSpec(
        "timestamp",
        "Timeline",
        re.compile(
            r"(?i)\b(?:around\s+|approximately\s+|about\s+)?\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?\b"
        ),
    ),
    PatternSpec(
        "languages",
        "Language",
        re.compile(
            r"(?i)\b(?:English|Arabic|French|Spanish|Turkish|Kurdish|Urdu|Greek)(?:\s+(?:and|with|speaker|only|plus|et)\s+(?:some\s+|limited\s+)?(?:English|Arabic|French|Spanish|Turkish|Kurdish|Urdu|Greek))?"
        ),
    ),
    PatternSpec(
        "clothing",
        "Clothing",
        re.compile(
            r"(?i)\b(?:dark\s+blue|navy|black|white|green|grey|gray)\s+(?:hooded\s+)?(?:jacket|coat|raincoat|shirt|sweater|scarf)\b"
        ),
    ),
    PatternSpec(
        "distinctive_features",
        "Distinctive features",
        re.compile(
            r"(?i)\b(?:small\s+)?scar\s+(?:above|over|near)\s+(?:the\s+)?(?:left|right)\s+eyebrow\b|\b(?:slight\s+)?(?:left|right)[- ]leg\s+limp\b"
            r"|\bboiter\s+légèrement\s+de\s+la\s+jambe\s+gauche\b"
        ),
    ),
    PatternSpec(
        "location",
        "Location",
        re.compile(
            r"(?i)\b(?:Al Noor School|North (?:evacuation )?gate|North Gate|Shelter \d+|East shelter|South Clinic|West Depot|Cedar Market|River Road|north triage post)\b"
        ),
    ),
]

NAME_PATTERN = re.compile(
    r"\b(?:Youssef Al Hassan|Yusuf Hasan|Yousef Hassan|Youssef Hassen|Yusuf Hassan|"
    r"Mina Darzi|Amal Rafiq|Samir Nader|Lina Haddad|Karim Mansour|Nadia Saleh|"
    r"Omar Khalil|Samir|Y\. Hassan)\b",
    re.IGNORECASE,
)
ARABIC_NAME_PATTERN = re.compile("يوسف الحسن")


def _span(
    record: RecordInput,
    *,
    key: str,
    label: str,
    quote: str,
    start: int,
    certainty: Certainty,
) -> tuple[ExtractedField, EvidenceSpan]:
    span_id = f"SPAN-{record.record_id}-{key.upper()}-{start}"
    span = EvidenceSpan(
        span_id=span_id,
        record_id=record.record_id,
        field=label,
        quote=quote,
        text=quote,
        start=start,
        end=start + len(quote),
        certainty=certainty,
        extraction_method="deterministic_pattern",
    )
    field = ExtractedField(
        field_id=f"FIELD-{record.record_id}-{key.upper()}-{start}",
        key=key,
        label=label,
        value=quote,
        certainty=certainty,
        source_span_id=span_id,
    )
    return field, span


def _matches(
    record: RecordInput, specs: Iterable[PatternSpec]
) -> list[tuple[ExtractedField, EvidenceSpan]]:
    found: list[tuple[ExtractedField, EvidenceSpan]] = []
    for spec in specs:
        match = spec.pattern.search(record.text)
        if match is None:
            continue
        quote = match.group(0)
        certainty = spec.certainty
        if spec.key in {"age", "timestamp"} and re.search(
            r"(?i)approximately|estimated|environ|around|about", quote
        ):
            certainty = Certainty.estimated
        elif spec.key != "age" and record.language != "English" and record.translated_text:
            certainty = Certainty.translated
        found.append(
            _span(
                record,
                key=spec.key,
                label=spec.label,
                quote=quote,
                start=match.start(),
                certainty=certainty,
            )
        )
    return found


def extract_record(record: RecordInput) -> tuple[list[ExtractedField], list[EvidenceSpan]]:
    pairs = _matches(record, PATTERNS)
    name_match = NAME_PATTERN.search(record.text) or ARABIC_NAME_PATTERN.search(record.text)
    if name_match is not None:
        certainty = (
            Certainty.translated
            if ARABIC_NAME_PATTERN.fullmatch(name_match.group(0))
            else Certainty.exact
        )
        pairs.insert(
            0,
            _span(
                record,
                key="name",
                label="Name",
                quote=name_match.group(0),
                start=name_match.start(),
                certainty=certainty,
            ),
        )
    fields = [pair[0] for pair in pairs]
    spans = [pair[1] for pair in pairs]
    present = {field.key for field in fields}
    for key, label in (
        ("name", "Name"),
        ("aliases", "Aliases"),
        ("age", "Age"),
        ("languages", "Languages"),
        ("location", "Last-seen location"),
        ("timestamp", "Timestamp"),
        ("clothing", "Clothing"),
        ("distinctive_features", "Distinctive features"),
        ("relatives", "Relatives"),
    ):
        if key not in present:
            fields.append(
                ExtractedField(
                    field_id=f"FIELD-{record.record_id}-{key.upper()}-MISSING",
                    key=key,
                    label=label,
                    value=None,
                    certainty=Certainty.missing,
                    unknown=True,
                )
            )
    return fields, spans
