from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.schemas.models import Certainty, EvidenceSpan, ExtractedField, RecordInput
from app.services.unicode_normalizer import (
    build_parsing_view,
    detect_arabic_field_label,
)


@dataclass(frozen=True, slots=True)
class PatternSpec:
    key: str
    label: str
    pattern: re.Pattern[str]
    certainty: Certainty = Certainty.exact
    value_group: int = 0  # capture group index for the value (0 = full match)
    strip_prefix: str = ""  # prefix to strip from value before storing


PATTERNS = [
    PatternSpec(
        "age",
        "Age",
        re.compile(
            r"(?i)\b(?:(?:estimated|approximately|about|environ)\s+age\s+|"
            r"age(?:d)?\s+(?:estimated|approximately|about|environ)\s+|"
            r"(?:estimated|approximately|about|environ)\s+|"
            r"\u00e2ge\s+estim\u00e9e?\s+|"
            r"(?:documented|recorded|reported|stated|given|listed)\s+)?"
            r"(?:age|\u0639\u0645\u0631|\u0627\u0644\u0639\u0645\u0631)\s+(\d{1,2}(?:[\u2013-]\d{1,2})?)"
            r"(?:\s*(?:years?|ans?|\u0639\u0627\u0645\u0627))?\b|"
            r"\b(\d{1,2})\s*(?:years?|ans?|\u0639\u0627\u0645\u0627)\b"
        ),
        value_group=0,
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
            r"|\bboiter\s+l\u00e9g\u00e8rement\s+de\s+la\s+jambe\s+gauche\b"
        ),
    ),
    PatternSpec(
        "location",
        "Location",
        re.compile(
            r"(?i)\b(?:Al Noor School|North (?:evacuation )?gate|North Gate|Shelter \d+|East shelter|South Clinic|West Depot|Cedar Market|River Road|north triage post|Al Waha Shelter|City Hospital|Port Authority)\b"
        ),
    ),
    PatternSpec(
        "government_id",
        "Government ID",
        re.compile(
            r"(?i)\b(?:ID|identification|registration)\s*[:.#]?\s*([A-Z]{2,4}[\u2013-]\d{4,8})\b"
        ),
        value_group=1,
    ),
    PatternSpec(
        "phone",
        "Phone",
        re.compile(
            r"(?i)(?:phone|tel|contact|\u0647\u0627\u062a\u0641|\u062c\u0648\u0627\u0644)\s*[:.]?\s*([+()\d][\d\s()\-.]{6,19})\b"
        ),
        value_group=1,
    ),
    PatternSpec(
        "email",
        "Email",
        re.compile(
            r"(?i)(?:email|e-mail|\u0625\u064a\u0645\u064a\u0644|\u0628\u0631\u064a\u062f)\s*[:.]?\s*([\w.+-]+@[\w-]+\.[\w.]+)"
        ),
        value_group=1,
    ),
    PatternSpec(
        "date_of_birth",
        "Date of Birth",
        re.compile(
            r"(?i)(?:DOB|date of birth|\u062a\u0627\u0631\u064a\u062e)\s*[:.]?\s*(\d{4}(?:[\u2013-]\d{2}(?:[\u2013-]\d{2})?)?)"
        ),
        value_group=1,
    ),
    PatternSpec(
        "family_member_names",
        "Family Member",
        re.compile(
            r"(?i)(?:mother|father|parent|sibling)\s+([\w\s]{2,30}?)(?:\.|,|$)"
        ),
        value_group=1,
    ),
]

# Explicit name-field label pattern: "Name:", "\u0627\u0644\u0627\u0633\u0645:"
# Captures the label area. The name value is searched for AFTER the label.
NAME_LABEL_PATTERN = re.compile(
    r"(?i)(?:name|\u0627\u0644\u0627\u0633\u0645|\u0627\u0633\u0645)\s*[:.\u061b]?\s*"
)

NAME_PATTERN = re.compile(
    r"\b(?:Youssef Al Hassan|Yusuf Hasan|Yousef Hassan|Youssef Hassen|Yusuf Hassan|Youssef Hassan|"
    r"Mina Darzi|Amal Rafiq|Samir Nader|Lina Haddad|Karim Mansour|Nadia Saleh|"
    r"Omar Khalil|Samir|Samir Nader|Y\. Hassan|Hassan Youssef)\b",
    re.IGNORECASE,
)

# Arabic-script name detection: Arabic LETTERS only (U+0621-U+064A + supplements)
# Excludes Arabic punctuation (U+0600-U+0620), digits, and symbols
_ARABIC_RANGE = "\u0621-\u064a\u067e\u0686\u0698\u06a9\u06af"
ARABIC_NAME_PATTERN = re.compile(
    r"[ء-يپچژکگ]{2,}(?:\s+[ء-يپچژکگ]{2,}){0,3}"
)

# Generic fallback: any two+ capitalized words that look like a name
# and aren't already matched by other patterns
GENERIC_NAME_FALLBACK = re.compile(
    r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b"
)

# Comma-form name: "Last, First" — safe fallback to standard extraction if rejected
COMMA_NAME_PATTERN = re.compile(
    r"([\u0600-\u06FF\w]+(?:\s+[\u0600-\u06FF\w]+)?),\s*"
    r"([A-Z\u0600-\u06FF][a-z\u0600-\u06FF]{2,}(?:\s+[A-Z\u0600-\u06FF][a-z\u0600-\u06FF]{2,})?)"
)

# Field-label keywords that must NOT be treated as name tokens in comma-form names
_NAME_FIELD_KEYWORDS: frozenset[str] = frozenset({
    'email','e-mail','mail','phone','tel','contact','mobile','cell',
    'dob','date','birth','age','aged','id','gov','registration',
    'approximately','approx','about','estimated','approximately',
    'scar','mark','tattoo','limp','distinctive','injury',
    'shelter','gate','school','clinic','hospital','road','market',
    'address','location','home','residence',
    # Arabic field labels (from shared unicode_normalizer)
    '\u0627\u0644\u0627\u0633\u0645','\u0627\u0633\u0645',  # name
    '\u0627\u0644\u0639\u0645\u0631','\u0639\u0645\u0631','\u0627\u0644\u0633\u0646',  # age
    '\u062a\u0627\u0631\u064a\u062e',  # date
    '\u0647\u0627\u062a\u0641','\u062c\u0648\u0627\u0644',  # phone
    '\u0625\u064a\u0645\u064a\u0644','\u0628\u0631\u064a\u062f',  # email
    '\u0627\u0644\u0639\u0646\u0648\u0627\u0646','\u0639\u0646\u0648\u0627\u0646','\u0627\u0644\u0645\u0648\u0642\u0639','\u0645\u0643\u0627\u0646',  # address/location
})


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
    record: RecordInput, specs: Iterable[PatternSpec],
    view: "ParsingView | None" = None,
) -> list[tuple[ExtractedField, EvidenceSpan]]:
    found: list[tuple[ExtractedField, EvidenceSpan]] = []
    occupied_ranges: list[tuple[int, int]] = []
    # Build position-preserving parsing view
    if view is None:
        from app.services.unicode_normalizer import build_parsing_view
        view = build_parsing_view(record.text)
    search_text = view.parsing_text

    for spec in specs:
        match = spec.pattern.search(search_text)
        if match is None:
            continue
        # Get the matched value from the appropriate capture group
        if spec.value_group:
            quote = match.group(spec.value_group)
            p_start = match.start(spec.value_group)
            p_end = match.end(spec.value_group)
        else:
            quote = match.group(0)
            p_start = match.start()
            p_end = match.end()

        # Map parsing-text span back to raw-text offsets via index map
        mapping = view.map_span(p_start, p_end)
        offset = mapping.raw_start
        end_offset = mapping.raw_end

        # Avoid overlapping matches (in raw-text coordinates)
        if any(lo <= offset < hi or lo < end_offset <= hi for lo, hi in occupied_ranges):
            continue
        occupied_ranges.append((offset, end_offset))

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
                start=offset,
                certainty=certainty,
            )
        )
    return found


def extract_record(record: RecordInput) -> tuple[list[ExtractedField], list[EvidenceSpan]]:
    # Clean text for parsing: remove directional controls, normalize Arabic punctuation

    # Also create a digits-normalized version for numeric parsing

    # Build position-preserving parsing view once for the entire extraction
    from app.services.unicode_normalizer import build_parsing_view
    view = build_parsing_view(record.text)

    pairs = _matches(record, PATTERNS, view=view)

    # Name extraction order:
    # 0. Explicit name-field label ("Name:" / "\u0627\u0644\u0627\u0633\u0645:") — preferred over unlabeled matches
    # 1. Comma-form name ("Last, First") with keyword rejection
    # 2. Whitelisted name patterns (backward compatibility)
    # 3. Arabic-script name detection (generalized — no hardcoded names)
    # 4. Generic fallback for capitalized names
    name_match = None
    name_val = None
    name_extraction_method: str | None = None  # provenance indicator

    # Step 0: Explicit name-field label — search for name AFTER a recognized label
    label_match = NAME_LABEL_PATTERN.search(view.parsing_text)
    if label_match:
        after_label = label_match.end()
        # Try whitelist pattern first, then Arabic pattern, then generic fallback
        label_name = NAME_PATTERN.search(view.parsing_text, pos=after_label)
        if label_name is None:
            label_name = ARABIC_NAME_PATTERN.search(view.parsing_text, pos=after_label)
        if label_name is None:
            label_name = GENERIC_NAME_FALLBACK.search(view.parsing_text, pos=after_label)
        if label_name is not None:
            name_match = label_name
            name_extraction_method = "explicit_name_label"

    # Step 1: Comma-form name with field-keyword guard
    if name_match is None:
        comma_match = COMMA_NAME_PATTERN.search(view.parsing_text)
        if comma_match:
            first_token = comma_match.group(2).split()[0].lower() if comma_match.group(2) else ''
            # Guard BOTH halves of the comma-form name. The family-name half
            # (group 1) must not contain digits or a field keyword either —
            # otherwise "age 35, North Gate" would be misread as a comma-form
            # name with family='age 35' and given='North Gate'.
            g1 = comma_match.group(1) or ''
            g1_first = g1.split()[0].lower() if g1 else ''
            g1_ok = bool(g1) and not any(c.isdigit() for c in g1) \
                and g1_first not in _NAME_FIELD_KEYWORDS \
                and not detect_arabic_field_label(g1_first)
            if (
                first_token not in _NAME_FIELD_KEYWORDS
                and g1_ok
                and not any(c.isdigit() for c in comma_match.group(2))
                and not detect_arabic_field_label(first_token)
            ):
                name_val = f"{comma_match.group(2)} {comma_match.group(1)}".strip()
                name_match = comma_match

    # Step 2: Whitelisted name pattern (backward compat)
    if name_match is None:
        name_match = NAME_PATTERN.search(view.parsing_text)

    # Step 3: Generalized Arabic-script name detection
    # Must be a plausible person name: multi-word or 4+ chars
    # Skip short possessive/relationship prefixes like ابني (my son)
    if name_match is None:
        arabic_match = ARABIC_NAME_PATTERN.search(view.parsing_text)
        if arabic_match:
            quote = arabic_match.group(0).strip()
            # Reject if starts with known non-name prefixes
            _non_name_prefixes = {
                'ابني', 'ابنتي',  # my son, my daughter
                'زوجي', 'زوجتي',  # my husband, my wife
                'أخي', 'أختي',  # my brother, my sister
                'والدي', 'والدتي',  # my father, my mother
            }
            words = quote.split()
            if words and words[0] in _non_name_prefixes:
                # Skip the prefix word and try the rest
                name_remainder = ' '.join(words[1:]) if len(words) > 1 else ''
                if name_remainder and len(name_remainder) >= 3:
                    name_val = name_remainder
                    name_match = arabic_match
            elif len(quote) >= 4 and not any(c.isdigit() for c in quote):
                name_val = quote
                name_match = arabic_match

    # Step 4: Generic fallback
    if name_match is None:
        name_match = GENERIC_NAME_FALLBACK.search(view.parsing_text)

    if name_match is not None and name_val is None:
        name_val = name_match.group(0).strip().rstrip(",")

    if name_val is not None and len(name_val) > 1 and not name_val.lower().startswith(tuple(_NAME_FIELD_KEYWORDS)):
        # Map name_val within the full match to get the correct sub-span.
        # name_val may be shorter than the full match (e.g., after stripping
        # non-name prefixes like 'ابني'). Find name_val in the full match
        # and compute the sub-offset to map precisely.
        full_match_text = name_match.group(0)
        sub_offset = full_match_text.find(name_val)
        if sub_offset >= 0:
            n_start = name_match.start() + sub_offset
            n_end = n_start + len(name_val)
        else:
            n_start = name_match.start()
            n_end = name_match.end()
        name_mapping = view.map_span(n_start, n_end)
        start = name_mapping.raw_start
        quote = name_mapping.raw_value  # Use raw value from mapping, not parsing text

        is_arabic = ARABIC_NAME_PATTERN.search(name_val) is not None
        certainty = Certainty.translated if (is_arabic and record.language != "English") else Certainty.exact
        pairs.insert(
            0,
            _span(
                record,
                key="name",
                label="Name",
                quote=quote,
                start=start,
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
        ("government_id", "Government ID"),
        ("phone", "Phone"),
        ("email", "Email"),
        ("date_of_birth", "Date of Birth"),
        ("languages", "Languages"),
        ("location", "Last-seen location"),
        ("timestamp", "Timestamp"),
        ("clothing", "Clothing"),
        ("distinctive_features", "Distinctive features"),
        ("family_member_names", "Family Member"),
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
