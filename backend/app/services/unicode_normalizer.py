"""
Shared deterministic Unicode normalization utilities.

Used by both production extraction and benchmark mock extraction
to ensure consistent digit normalization, directional-control handling,
Arabic punctuation normalization, and script detection.

No network calls. No LLM. Deterministic across runs. Version-pinned.

Humanitarian safety principle: raw evidence is never mutated.
Normalized representations are derived, traceable, and auditable.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

NORMALIZATION_VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════
# Digit normalization — three digit systems to ASCII
# ═══════════════════════════════════════════════════════════

class DigitSystem(StrEnum):
    ascii = "ascii"
    arabic_indic = "arabic_indic"             # U+0660–U+0669
    eastern_arabic_indic = "eastern_arabic_indic"  # U+06F0–U+06F9


# Mapping tables
_ARABIC_INDIC_TO_ASCII: dict[str, str] = {
    '\u0660': '0', '\u0661': '1', '\u0662': '2', '\u0663': '3', '\u0664': '4',
    '\u0665': '5', '\u0666': '6', '\u0667': '7', '\u0668': '8', '\u0669': '9',
}

_EASTERN_ARABIC_INDIC_TO_ASCII: dict[str, str] = {
    '\u06f0': '0', '\u06f1': '1', '\u06f2': '2', '\u06f3': '3', '\u06f4': '4',
    '\u06f5': '5', '\u06f6': '6', '\u06f7': '7', '\u06f8': '8', '\u06f9': '9',
}

# Combined: all known non-ASCII digit systems → ASCII
_DIGIT_NORMALIZATION_MAP: dict[str, str] = {}
_DIGIT_NORMALIZATION_MAP.update(_ARABIC_INDIC_TO_ASCII)
_DIGIT_NORMALIZATION_MAP.update(_EASTERN_ARABIC_INDIC_TO_ASCII)


def _detect_digit_systems(value: str) -> list[DigitSystem]:
    """Detect which digit systems are present in a raw string."""
    present: list[DigitSystem] = []
    for ch in value:
        if ch.isascii() and ch.isdigit():
            if DigitSystem.ascii not in present:
                present.append(DigitSystem.ascii)
        elif ch in _ARABIC_INDIC_TO_ASCII:
            if DigitSystem.arabic_indic not in present:
                present.append(DigitSystem.arabic_indic)
        elif ch in _EASTERN_ARABIC_INDIC_TO_ASCII:
            if DigitSystem.eastern_arabic_indic not in present:
                present.append(DigitSystem.eastern_arabic_indic)
    return present


@dataclass(frozen=True, slots=True)
class DigitNormalizationResult:
    """Result of normalizing digits from any supported system to ASCII."""
    raw_value: str
    normalized_value: str
    systems_detected: list[DigitSystem] = field(default_factory=list)
    conversion_occurred: bool = False
    normalization_steps: list[str] = field(default_factory=list)
    version: str = NORMALIZATION_VERSION


def normalize_digits(value: str) -> DigitNormalizationResult:
    """Normalize all known digit systems to ASCII digits.

    Preserves non-digit characters untouched.
    Returns full provenance: raw value, normalized value, detected systems,
    and whether any conversion occurred.
    """
    systems = _detect_digit_systems(value)
    steps: list[str] = []
    converted = False
    result = value

    # Check if Arabic-Indic digits are present
    for ch in value:
        if ch in _ARABIC_INDIC_TO_ASCII:
            converted = True
            break
    if converted:
        for ar, en in _ARABIC_INDIC_TO_ASCII.items():
            result = result.replace(ar, en)
        steps.append("arabic_indic_to_ascii")

    # Check if Eastern Arabic-Indic digits are present
    eastern_converted = False
    for ch in value:
        if ch in _EASTERN_ARABIC_INDIC_TO_ASCII:
            eastern_converted = True
            break
    if eastern_converted:
        for ar, en in _EASTERN_ARABIC_INDIC_TO_ASCII.items():
            result = result.replace(ar, en)
        steps.append("eastern_arabic_indic_to_ascii")

    if not steps:
        steps.append("no_conversion_needed")

    return DigitNormalizationResult(
        raw_value=value,
        normalized_value=result,
        systems_detected=systems,
        conversion_occurred=converted or eastern_converted,
        normalization_steps=steps,
    )


def normalize_digits_only(value: str) -> str:
    """Convenience: return only the ASCII-digit normalized string."""
    return normalize_digits(value).normalized_value


# ═══════════════════════════════════════════════════════════
# Directional control mark handling
# ═══════════════════════════════════════════════════════════

# Unicode bidi control characters that should be stripped from normalized
# derived representations (never from raw evidence)
_BIDI_CONTROL_CHARS: set[str] = {
    '\u200e',  # LEFT-TO-RIGHT MARK (LRM)
    '\u200f',  # RIGHT-TO-LEFT MARK (RLM)
    '\u202a',  # LEFT-TO-RIGHT EMBEDDING (LRE)
    '\u202b',  # RIGHT-TO-LEFT EMBEDDING (RLE)
    '\u202c',  # POP DIRECTIONAL FORMATTING (PDF)
    '\u202d',  # LEFT-TO-RIGHT OVERRIDE (LRO)
    '\u202e',  # RIGHT-TO-LEFT OVERRIDE (RLO)
    '\u2066',  # LEFT-TO-RIGHT ISOLATE (LRI)
    '\u2067',  # RIGHT-TO-LEFT ISOLATE (RLI)
    '\u2068',  # FIRST STRONG ISOLATE (FSI)
    '\u2069',  # POP DIRECTIONAL ISOLATE (PDI)
}

# Controls that may appear and should be checked
_CONTROL_NAMES: dict[str, str] = {
    '\u200e': "LRM", '\u200f': "RLM",
    '\u202a': "LRE", '\u202b': "RLE", '\u202c': "PDF",
    '\u202d': "LRO", '\u202e': "RLO",
    '\u2066': "LRI", '\u2067': "RLI", '\u2068': "FSI", '\u2069': "PDI",
}


@dataclass(frozen=True, slots=True)
class BidiControlResult:
    """Result of directional control removal from derived text."""
    raw_value: str
    cleaned_value: str
    controls_removed: list[str] = field(default_factory=list)
    count_removed: int = 0
    normalization_steps: list[str] = field(default_factory=list)
    version: str = NORMALIZATION_VERSION


def remove_directional_controls(value: str) -> BidiControlResult:
    """Remove Unicode bidi control characters from a derived representation.

    The raw source text is never mutated. This function produces a clean
    derived value for comparison, parsing, and normalization purposes.
    """
    removed: list[str] = []
    cleaned: list[str] = []
    count = 0

    for ch in value:
        if ch in _BIDI_CONTROL_CHARS:
            name = _CONTROL_NAMES.get(ch, f"U+{ord(ch):04X}")
            if name not in removed:
                removed.append(name)
            count += 1
        else:
            cleaned.append(ch)

    steps = []
    if count > 0:
        steps.append(f"removed_{count}_bidi_controls")

    return BidiControlResult(
        raw_value=value,
        cleaned_value="".join(cleaned),
        controls_removed=removed,
        count_removed=count,
        normalization_steps=steps,
    )


def clean_directional(value: str) -> str:
    """Convenience: return only the cleaned string without bidi controls."""
    return remove_directional_controls(value).cleaned_value


# ═══════════════════════════════════════════════════════════
# Arabic punctuation normalization
# ═══════════════════════════════════════════════════════════

_ARABIC_PUNCTUATION_MAP: dict[str, str] = {
    '\u060c': ',',   # ARABIC COMMA
    '\u061b': ';',   # ARABIC SEMICOLON
    '\u061f': '?',   # ARABIC QUESTION MARK
}


@dataclass(frozen=True, slots=True)
class PunctuationNormalizationResult:
    """Result of Arabic punctuation normalization."""
    raw_value: str
    normalized_value: str
    replacements: list[str] = field(default_factory=list)
    version: str = NORMALIZATION_VERSION


def normalize_arabic_punctuation(value: str) -> PunctuationNormalizationResult:
    """Normalize Arabic punctuation to ASCII equivalents in derived text.

    Only for derived representations — raw text is never mutated.
    """
    replacements: list[str] = []
    result = value
    for ar, en in _ARABIC_PUNCTUATION_MAP.items():
        if ar in result:
            replacements.append(f"U+{ord(ar):04X}→'{en}'")
            result = result.replace(ar, en)
    return PunctuationNormalizationResult(
        raw_value=value,
        normalized_value=result,
        replacements=replacements,
    )


def clean_arabic_punctuation(value: str) -> str:
    """Convenience: return only the cleaned string."""
    return normalize_arabic_punctuation(value).normalized_value


# ═══════════════════════════════════════════════════════════
# Whitespace normalization
# ═══════════════════════════════════════════════════════════

def normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace and strip. For derived text only."""
    return " ".join(value.split())


# ═══════════════════════════════════════════════════════════
# Combined field-label cleanup for extraction
# ═══════════════════════════════════════════════════════════

def clean_text_for_parsing(value: str) -> str:
    """Apply safe normalization for text parsing (label matching, extraction).

    Applies (in order):
    1. Directional control removal
    2. Arabic punctuation normalization
    3. Whitespace normalization

    The raw source text is never touched — this produces a clean
    derived string for pattern matching and label recognition.
    """
    result = clean_directional(value)
    result = clean_arabic_punctuation(result)
    result = normalize_whitespace(result)
    return result


# ═══════════════════════════════════════════════════════════
# Arabic field-label recognition
# ═══════════════════════════════════════════════════════════

# Arabic field labels → canonical English field names
# Used for mixed-script and Arabic-only record extraction
ARABIC_FIELD_LABELS: dict[str, str] = {
    # Name
    "\u0627\u0644\u0627\u0633\u0645": "name",       # الاسم
    "\u0627\u0633\u0645": "name",                     # اسم
    "\u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u0643\u0627\u0645\u0644": "name",  # الاسم الكامل
    # Age
    "\u0627\u0644\u0639\u0645\u0631": "age",         # العمر
    "\u0639\u0645\u0631": "age",                       # عمر
    "\u0627\u0644\u0633\u0646": "age",                # السن
    # Date of Birth
    "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0645\u064a\u0644\u0627\u062f": "date_of_birth",  # تاريخ الميلاد
    "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0648\u0644\u0627\u062f\u0629": "date_of_birth",  # تاريخ الولادة
    # Phone
    "\u0647\u0627\u062a\u0641": "phone",             # هاتف
    "\u0627\u0644\u0647\u0627\u062a\u0641": "phone", # الهاتف
    "\u062c\u0648\u0627\u0644": "phone",              # جوال
    "\u0631\u0642\u0645 \u0627\u0644\u0647\u0627\u062a\u0641": "phone",  # رقم الهاتف
    # Email
    "\u0627\u0644\u0628\u0631\u064a\u062f \u0627\u0644\u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a": "email",  # البريد الإلكتروني
    "\u0628\u0631\u064a\u062f \u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a": "email",  # بريد إلكتروني
    "\u0625\u064a\u0645\u064a\u0644": "email",       # إيميل
    # Location / Address
    "\u0627\u0644\u0639\u0646\u0648\u0627\u0646": "home_address",  # العنوان
    "\u0639\u0646\u0648\u0627\u0646": "home_address",  # عنوان
    "\u0627\u0644\u0645\u0648\u0642\u0639": "last_known_location",  # الموقع
    "\u0645\u0643\u0627\u0646": "last_known_location",  # مكان
    "\u0622\u062e\u0631 \u0645\u0643\u0627\u0646": "last_known_location",  # آخر مكان
    "\u0622\u062e\u0631 \u0645\u0648\u0642\u0639": "last_known_location",  # آخر موقع
    # Government ID
    "\u0631\u0642\u0645 \u0627\u0644\u0647\u0648\u064a\u0629": "government_id",  # رقم الهوية
    "\u0627\u0644\u0647\u0648\u064a\u0629": "government_id",  # الهوية
    "\u0628\u0637\u0627\u0642\u0629": "government_id",  # بطاقة
    # Family
    "\u0627\u0644\u0623\u0645": "family_member_names",  # الأم
    "\u0627\u0644\u0623\u0628": "family_member_names",   # الأب
    "\u0627\u0644\u0623\u0642\u0627\u0631\u0628": "family_member_names",  # الأقارب
}


def detect_arabic_field_label(text: str, *, clean: bool = True) -> str | None:
    """Detect if a line or segment begins with a known Arabic field label.

    Returns the canonical English field name, or None.
    The text should be a short segment (line or label portion).
    """
    working = clean_text_for_parsing(text) if clean else text
    working_lower = working.lower().strip()
    for arabic_label, canonical_name in ARABIC_FIELD_LABELS.items():
        if working_lower.startswith(arabic_label):
            return canonical_name
    return None


def get_arabic_label_pattern() -> str:
    """Return a regex alternation of all known Arabic field labels."""
    labels = sorted(ARABIC_FIELD_LABELS.keys(), key=len, reverse=True)
    escaped = [re.escape(lbl) for lbl in labels]
    return "|".join(escaped)


# ═══════════════════════════════════════════════════════════
# Position-preserving parsing view
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class SpanMapping:
    """Maps a parsing-text span back to the corresponding raw-text span."""
    parsing_start: int
    parsing_end: int
    raw_start: int
    raw_end: int
    parsing_value: str       # substring in parsing_text
    raw_value: str           # substring in raw_text
    transformations: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ParsingView:
    """A transformed version of raw text with position-preserving index mapping.

    Holds:
    - raw_text: the original untransformed source
    - parsing_text: the cleaned text suitable for regex matching
    - raw_to_parsing: list mapping raw index → parsing index (or -1 if removed)
    - parsing_to_raw_start: list mapping parsing index → raw start index
    - parsing_to_raw_end: list mapping parsing index → raw end index (exclusive)

    Each parsing character maps to a contiguous raw-text span [start, end).
    For ordinary 1:1 characters, end = start + 1.
    For collapsed whitespace, end may be > start + 1, encompassing all
    the raw whitespace characters represented by this parsing space.

    When a regex matches parsing_text[p_start:p_end], map_span() computes
    the raw span from the raw_start of the first included character through
    the raw_end of the last included character.
    """
    raw_text: str
    parsing_text: str
    raw_to_parsing: list[int] = field(default_factory=list)
    parsing_to_raw_start: list[int] = field(default_factory=list)
    parsing_to_raw_end: list[int] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    version: str = NORMALIZATION_VERSION

    def map_span(self, parsing_start: int, parsing_end: int) -> SpanMapping:
        """Map a parsing-text span back to raw-text offsets.

        Uses the parsing-to-raw start/end arrays to compute exact raw spans.
        Does NOT search for substrings in raw text.

        Returns:
            SpanMapping with raw offsets and values
        """
        if parsing_start < 0 or parsing_end > len(self.parsing_text):
            raise IndexError(
                f"Span [{parsing_start}:{parsing_end}] out of bounds "
                f"for parsing_text of length {len(self.parsing_text)}"
            )
        if parsing_start >= parsing_end:
            return SpanMapping(
                parsing_start=parsing_start, parsing_end=parsing_end,
                raw_start=0, raw_end=0,
                parsing_value="", raw_value="",
            )

        # Map start: raw_start of the first parsing character in the span
        if parsing_start < len(self.parsing_to_raw_start):
            raw_start = self.parsing_to_raw_start[parsing_start]
        else:
            raw_start = len(self.raw_text)

        # Map end: raw_end of the last parsing character in the span
        last_idx = parsing_end - 1
        if last_idx < len(self.parsing_to_raw_end):
            raw_end = self.parsing_to_raw_end[last_idx]
        else:
            raw_end = len(self.raw_text)

        # Clamp
        raw_start = max(0, min(raw_start, len(self.raw_text)))
        raw_end = max(raw_start, min(raw_end, len(self.raw_text)))

        return SpanMapping(
            parsing_start=parsing_start,
            parsing_end=parsing_end,
            raw_start=raw_start,
            raw_end=raw_end,
            parsing_value=self.parsing_text[parsing_start:parsing_end],
            raw_value=self.raw_text[raw_start:raw_end],
            transformations=list(self.transformations),
        )


def build_parsing_view(
    raw_text: str,
    *,
    strip_bidi: bool = True,
    normalize_arabic_punct: bool = True,
    normalize_digits: bool = True,
    collapse_whitespace: bool = True,
) -> ParsingView:
    """Build a position-preserving parsing view of raw text.

    Applies transformations in order while maintaining index mappings:
    1. Directional control removal
    2. Arabic punctuation substitution
    3. Digit normalization
    4. Whitespace collapse

    Each transformation updates both the parsing text and the bidirectional
    index maps so that regex matches on parsing_text can be precisely mapped
    back to raw_text offsets.
    """
    raw_to_par: list[int] = []
    par_to_raw_start: list[int] = []
    par_to_raw_end: list[int] = []
    parsing_chars: list[str] = []
    transforms: list[str] = []

    i = 0
    while i < len(raw_text):
        ch = raw_text[i]

        # Step 1: Skip bidi controls
        if strip_bidi and ch in _BIDI_CONTROL_CHARS:
            raw_to_par.append(-1)  # removed
            i += 1
            if "strip_bidi" not in transforms:
                transforms.append("strip_bidi")
            continue

        # Step 2: Normalize Arabic punctuation
        if normalize_arabic_punct and ch in _ARABIC_PUNCTUATION_MAP:
            mapped = _ARABIC_PUNCTUATION_MAP[ch]
            par_idx = len(parsing_chars)
            raw_to_par.append(par_idx)
            par_to_raw_start.append(i)
            par_to_raw_end.append(i + 1)
            parsing_chars.append(mapped)
            i += 1
            if "normalize_arabic_punct" not in transforms:
                transforms.append("normalize_arabic_punct")
            continue

        # Step 3: Normalize digits
        if normalize_digits and ch in _DIGIT_NORMALIZATION_MAP:
            mapped = _DIGIT_NORMALIZATION_MAP[ch]
            par_idx = len(parsing_chars)
            raw_to_par.append(par_idx)
            par_to_raw_start.append(i)
            par_to_raw_end.append(i + 1)
            parsing_chars.append(mapped)
            i += 1
            if "normalize_digits" not in transforms:
                transforms.append("normalize_digits")
            continue

        # Step 4: Collapse whitespace — one parsing space represents the full raw whitespace run
        if collapse_whitespace and ch in (' ', '\t', '\r', '\n', '\u00A0'):
            if parsing_chars and parsing_chars[-1] == ' ':
                # Extend the raw_end of the existing parsing space to include this char
                par_idx = len(parsing_chars) - 1
                par_to_raw_end[par_idx] = i + 1
                raw_to_par.append(-1)  # collapsed into previous
                i += 1
                continue
            par_idx = len(parsing_chars)
            raw_to_par.append(par_idx)
            par_to_raw_start.append(i)
            par_to_raw_end.append(i + 1)
            parsing_chars.append(' ')
            i += 1
            if "collapse_whitespace" not in transforms:
                transforms.append("collapse_whitespace")
            continue

        # Default: pass through unchanged
        par_idx = len(parsing_chars)
        raw_to_par.append(par_idx)
        par_to_raw_start.append(i)
        par_to_raw_end.append(i + 1)
        parsing_chars.append(ch)
        i += 1

    return ParsingView(
        raw_text=raw_text,
        parsing_text="".join(parsing_chars),
        raw_to_parsing=raw_to_par,
        parsing_to_raw_start=par_to_raw_start,
        parsing_to_raw_end=par_to_raw_end,
        transformations=transforms,
    )
