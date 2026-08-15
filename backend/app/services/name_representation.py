"""
Deterministic, transliteration-aware name representation and comparison.

Humanitarian safety principle: Unicode NFKD alone is NOT transliteration.
Arabic is an abjad without written short vowels — consonant-skeleton matching
is required for cross-script comparison. Cyrillic and Greek are mapped character
by character using deterministic tables.

Every comparison channel is precisely named for provenance:
- formal_transliteration_match: character-level mapping (Cyrillic, Greek)
- consonant_skeleton_compatible: Arabic consonant-skeleton cross-script
- known_variant_match: TRANSLITERATION_VARIANTS normalization (Muhammad→muhammad)
- token_reordered_compatible: same tokens, different order
- fuzzy_name_similarity: RapidFuzz fallback

No network calls. No LLM. Deterministic across runs. Version-pinned.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


# ═══════════════════════════════════════════════════════════
# Script detection
# ═══════════════════════════════════════════════════════════

class NameScript(StrEnum):
    latin = "latin"
    arabic = "arabic"
    cyrillic = "cyrillic"
    greek = "greek"
    mixed = "mixed"
    unknown = "unknown"


def _detect_script(text: str) -> NameScript:
    if not text.strip():
        return NameScript.unknown
    scripts: set[NameScript] = set()
    for ch in text:
        cp = ord(ch)
        if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
            scripts.add(NameScript.arabic)
        elif 0x0400 <= cp <= 0x04FF or 0x0500 <= cp <= 0x052F:
            scripts.add(NameScript.cyrillic)
        elif 0x0370 <= cp <= 0x03FF:
            scripts.add(NameScript.greek)
        elif ord(ch.lower()) < 128 and ch.isalpha():
            scripts.add(NameScript.latin)
        elif ch.isalpha():
            scripts.add(NameScript.unknown)
    if not scripts:
        return NameScript.latin
    if len(scripts) == 1:
        return next(iter(scripts))
    return NameScript.mixed


# ═══════════════════════════════════════════════════════════
# Arabic → Latin consonant-skeleton mapping
# ═══════════════════════════════════════════════════════════

ARABIC_CONSONANT_MAP: dict[int, str] = {
    0x0621: "'", 0x0622: "A", 0x0623: "A", 0x0624: "W", 0x0625: "A",
    0x0626: "Y", 0x0627: "A", 0x0628: "B", 0x0629: "H", 0x062A: "T",
    0x062B: "TH", 0x062C: "J", 0x062D: "H", 0x062E: "KH", 0x062F: "D",
    0x0630: "DH", 0x0631: "R", 0x0632: "Z", 0x0633: "S", 0x0634: "SH",
    0x0635: "S", 0x0636: "D", 0x0637: "T", 0x0638: "Z", 0x0639: "'",
    0x063A: "GH", 0x0641: "F", 0x0642: "Q", 0x0643: "K", 0x0644: "L",
    0x0645: "M", 0x0646: "N", 0x0647: "H", 0x0648: "W", 0x0649: "Y",
    0x064A: "Y", 0x067E: "P", 0x0686: "CH", 0x0698: "ZH",
    0x06A9: "K", 0x06AF: "G",
    0xFB50: "A", 0xFB51: "A", 0xFB52: "B", 0xFB53: "B", 0xFB54: "B",
    0xFB56: "T", 0xFB57: "T", 0xFB58: "T", 0xFB59: "T",
    0xFB5A: "TH", 0xFB5B: "TH", 0xFB5C: "TH", 0xFB5D: "TH",
    0xFB5E: "J", 0xFB5F: "J", 0xFB60: "J", 0xFB61: "J",
    0xFB62: "H", 0xFB63: "H", 0xFB64: "H", 0xFB65: "H",
    0xFB66: "KH", 0xFB67: "KH", 0xFB68: "KH", 0xFB69: "KH",
    0xFB6A: "D", 0xFB6B: "D", 0xFB6C: "DH", 0xFB6D: "DH",
    0xFB6E: "R", 0xFB6F: "R", 0xFB70: "Z", 0xFB71: "Z",
    0xFB72: "S", 0xFB73: "S", 0xFB74: "S", 0xFB75: "S",
    0xFB76: "SH", 0xFB77: "SH", 0xFB78: "SH", 0xFB79: "SH",
    0xFB7A: "S", 0xFB7B: "S", 0xFB7C: "S", 0xFB7D: "S",
    0xFB7E: "D", 0xFB7F: "D", 0xFB80: "T", 0xFB81: "T",
    0xFB82: "Z", 0xFB83: "Z", 0xFB84: "'", 0xFB85: "'",
    0xFB86: "GH", 0xFB87: "GH", 0xFB8A: "F", 0xFB8B: "F",
    0xFB8C: "Q", 0xFB8D: "Q", 0xFB8E: "K", 0xFB8F: "K",
    0xFB90: "L", 0xFB91: "L", 0xFB92: "M", 0xFB93: "M",
    0xFB94: "N", 0xFB95: "N", 0xFB96: "H", 0xFB97: "H",
    0xFB98: "W", 0xFB99: "W", 0xFB9A: "Y", 0xFB9B: "Y",
    0xFB9C: "A", 0xFB9D: "A", 0xFB9E: "P", 0xFB9F: "P",
    0xFBA0: "CH", 0xFBA1: "CH", 0xFBA2: "CH", 0xFBA3: "CH",
    0xFBA6: "G", 0xFBA7: "G",
    0xFE80: "'", 0xFE81: "A", 0xFE82: "A", 0xFE83: "A", 0xFE84: "A",
    0xFE85: "W", 0xFE86: "W", 0xFE87: "A", 0xFE88: "A",
    0xFE89: "Y", 0xFE8A: "Y", 0xFE8B: "Y", 0xFE8C: "Y",
    0xFE8D: "A", 0xFE8E: "A", 0xFE8F: "B", 0xFE90: "B", 0xFE91: "B", 0xFE92: "B",
    0xFE93: "H", 0xFE94: "H", 0xFE95: "T", 0xFE96: "T", 0xFE97: "T", 0xFE98: "T",
    0xFE99: "TH", 0xFE9A: "TH", 0xFE9B: "TH", 0xFE9C: "TH",
    0xFE9D: "J", 0xFE9E: "J", 0xFE9F: "J", 0xFEA0: "J",
    0xFEA1: "H", 0xFEA2: "H", 0xFEA3: "H", 0xFEA4: "H",
    0xFEA5: "KH", 0xFEA6: "KH", 0xFEA7: "KH", 0xFEA8: "KH",
    0xFEA9: "D", 0xFEAA: "D", 0xFEAB: "DH", 0xFEAC: "DH",
    0xFEAD: "R", 0xFEAE: "R", 0xFEAF: "Z", 0xFEB0: "Z",
    0xFEB1: "S", 0xFEB2: "S", 0xFEB3: "S", 0xFEB4: "S",
    0xFEB5: "SH", 0xFEB6: "SH", 0xFEB7: "SH", 0xFEB8: "SH",
    0xFEB9: "S", 0xFEBA: "S", 0xFEBB: "S", 0xFEBC: "S",
    0xFEBD: "D", 0xFEBE: "D", 0xFEBF: "T", 0xFEC0: "T",
    0xFEC1: "Z", 0xFEC2: "Z", 0xFEC3: "'", 0xFEC4: "'",
    0xFEC5: "GH", 0xFEC6: "GH", 0xFEC9: "F", 0xFECA: "F",
    0xFECB: "Q", 0xFECC: "Q", 0xFECD: "K", 0xFECE: "K",
    0xFECF: "L", 0xFED0: "L", 0xFED1: "M", 0xFED2: "M",
    0xFED3: "N", 0xFED4: "N", 0xFED5: "H", 0xFED6: "H",
    0xFED7: "W", 0xFED8: "W", 0xFED9: "Y", 0xFEDA: "Y",
    0xFEDB: "L", 0xFEDC: "L", 0xFEDD: "A", 0xFEDE: "A",
    0xFEDF: "L", 0xFEE0: "L", 0xFEE1: "A", 0xFEE2: "A",
    0xFEE3: "A", 0xFEE4: "A", 0xFEE5: "W", 0xFEE6: "W",
    0xFEE7: "Y", 0xFEE8: "Y", 0xFEE9: "B", 0xFEEA: "B",
    0xFEEB: "L", 0xFEEC: "L", 0xFEED: "B", 0xFEEE: "B",
}


def arabic_consonant_skeleton(text: str, *, preserve_spaces: bool = True) -> str:
    """Extract the consonant skeleton from an Arabic name.

    Spaces are preserved to maintain word boundaries (critical for
    multi-token name detection). Example: يوسف الحسن → "YWSF LHSN"
    """
    result: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0x064B <= cp <= 0x0652:
            continue
        if ch == " " or ch == "\u00A0":
            if preserve_spaces:
                result.append(" ")
            continue
        mapped = ARABIC_CONSONANT_MAP.get(cp)
        if mapped:
            result.append(mapped)
        elif ch.isalpha():
            result.append(ch)
    return "".join(result).strip()


# ═══════════════════════════════════════════════════════════
# Cyrillic → Latin formal transliteration (ISO 9-like)
# ═══════════════════════════════════════════════════════════

CYRILLIC_TO_LATIN: dict[int, str] = {
    0x0410: "A", 0x0430: "a", 0x0411: "B", 0x0431: "b",
    0x0412: "V", 0x0432: "v", 0x0413: "G", 0x0433: "g",
    0x0414: "D", 0x0434: "d", 0x0415: "E", 0x0435: "e",
    0x0401: "Yo", 0x0451: "yo", 0x0416: "Zh", 0x0436: "zh",
    0x0417: "Z", 0x0437: "z", 0x0418: "I", 0x0438: "i",
    0x0419: "Y", 0x0439: "y", 0x041A: "K", 0x043A: "k",
    0x041B: "L", 0x043B: "l", 0x041C: "M", 0x043C: "m",
    0x041D: "N", 0x043D: "n", 0x041E: "O", 0x043E: "o",
    0x041F: "P", 0x043F: "p", 0x0420: "R", 0x0440: "r",
    0x0421: "S", 0x0441: "s", 0x0422: "T", 0x0442: "t",
    0x0423: "U", 0x0443: "u", 0x0424: "F", 0x0444: "f",
    0x0425: "Kh", 0x0445: "kh", 0x0426: "Ts", 0x0446: "ts",
    0x0427: "Ch", 0x0447: "ch", 0x0428: "Sh", 0x0448: "sh",
    0x0429: "Shch", 0x0449: "shch", 0x042A: "", 0x044A: "",
    0x042B: "Y", 0x044B: "y", 0x042C: "", 0x044C: "",
    0x042D: "E", 0x044D: "e", 0x042E: "Yu", 0x044E: "yu",
    0x042F: "Ya", 0x044F: "ya", 0x0404: "Ye", 0x0454: "ye",
    0x0406: "I", 0x0456: "i", 0x0407: "Yi", 0x0457: "yi",
    0x0490: "G", 0x0491: "g", 0x0408: "J", 0x0458: "j",
    0x0409: "Lj", 0x0459: "lj", 0x040A: "Nj", 0x045A: "nj",
    0x040F: "Dzh", 0x045F: "dzh",
}

GREEK_TO_LATIN: dict[int, str] = {
    0x0391: "A", 0x03B1: "a", 0x0392: "B", 0x03B2: "b",
    0x0393: "G", 0x03B3: "g", 0x0394: "D", 0x03B4: "d",
    0x0395: "E", 0x03B5: "e", 0x0396: "Z", 0x03B6: "z",
    0x0397: "I", 0x03B7: "i", 0x0398: "Th", 0x03B8: "th",
    0x0399: "I", 0x03B9: "i", 0x039A: "K", 0x03BA: "k",
    0x039B: "L", 0x03BB: "l", 0x039C: "M", 0x03BC: "m",
    0x039D: "N", 0x03BD: "n", 0x039E: "X", 0x03BE: "x",
    0x039F: "O", 0x03BF: "o", 0x03A0: "P", 0x03C0: "p",
    0x03A1: "R", 0x03C1: "r", 0x03A3: "S", 0x03C3: "s", 0x03C2: "s",
    0x03A4: "T", 0x03C4: "t", 0x03A5: "Y", 0x03C5: "y",
    0x03A6: "F", 0x03C6: "f", 0x03A7: "Ch", 0x03C7: "ch",
    0x03A8: "Ps", 0x03C8: "ps", 0x03A9: "O", 0x03C9: "o",
}

# Common Latin spelling variants (not transliteration — heuristic normalization)
TRANSLITERATION_VARIANTS: dict[str, str] = {
    "muhammad": "muhammad", "mohammad": "muhammad", "mohammed": "muhammad",
    "muhammed": "muhammad", "mohamed": "muhammad", "mohamad": "muhammad",
    "mohd": "muhammad", "youssef": "yusuf", "yusuf": "yusuf",
    "yousef": "yusuf", "yusef": "yusuf", "youseff": "yusuf",
    "ali": "ali", "aly": "ali", "hassan": "hasan", "hasan": "hasan",
    "hassen": "hasan", "hussain": "husayn", "hussein": "husayn",
    "husein": "husayn", "abdullah": "abdullah", "abdallah": "abdullah",
    "abdel lah": "abdullah", "abdul lah": "abdullah", "abdul": "abdullah",
    "ahmad": "ahmad", "ahmed": "ahmad", "ahmet": "ahmad",
    "ibrahim": "ibrahim", "ebraheem": "ibrahim",
}

# Honorifics and articles — auditable stripping rules
COMMON_HONORIFICS: set[str] = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "sir", "madam",
    "haji", "hajjah", "alhaji", "hajiya", "sheikh", "sheikha",
    "syed", "sayyid", "sayyida", "ustaadh", "ustadha", "hafiz", "hafiza",
}
COMMON_ARTICLES: set[str] = {"al", "el", "bin", "bint", "ibn", "abu", "um", "umm"}

_VOWELS = frozenset("aeiouAEIOU")
NORMALIZATION_VERSION = "1.1.0"


# ═══════════════════════════════════════════════════════════
# NameRepresentation
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class NameRepresentation:
    raw_value: str
    record_id: str = ""
    unicode_normalized: str = ""
    script: NameScript = NameScript.unknown
    normalized_original_script: str = ""
    latin_transliteration: str | None = None
    normalized_latin_transliteration: str | None = None
    consonant_skeleton: str = ""
    normalized_skeleton: str = ""
    tokens: tuple[str, ...] = ()
    tokens_no_articles: tuple[str, ...] = ()
    initials: str = ""
    normalization_version: str = NORMALIZATION_VERSION
    transliteration_method: str = ""  # e.g. "arabic_consonant_skeleton", "cyrillic_char_map"
    warning: str | None = None
    token_count: int = 0
    is_short_name: bool = False
    is_common_name: bool = False


# ═══════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════

def _unicode_normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _latin_normalize(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    tokens = [t for t in tokens if t.lower() not in COMMON_HONORIFICS]
    tokens = [t for t in tokens if t.lower() not in COMMON_ARTICLES]
    return " ".join(tokens)


def _consonant_skeleton(value: str) -> str:
    result: list[str] = []
    last = ""
    for ch in value.upper():
        if ch.isalpha() and ch not in _VOWELS:
            if ch != last:
                result.append(ch)
                last = ch
    return "".join(result)


def _source_word_count(text: str) -> int:
    """Word count from source text, regardless of script."""
    stripped = text.strip()
    if not stripped:
        return 0
    # Handle both ASCII spaces and Unicode spacing characters
    words = re.split(r"[\s\u00A0]+", stripped)
    return len([w for w in words if w])


# ═══════════════════════════════════════════════════════════
# Canonical entry point
# ═══════════════════════════════════════════════════════════

def represent_name(
    raw_value: str,
    record_id: str = "",
    *,
    honorific_strip: bool = True,
) -> NameRepresentation:
    if not raw_value or not raw_value.strip():
        return NameRepresentation(
            raw_value=raw_value or "", record_id=record_id,
            warning="Empty or whitespace-only name",
        )

    unicode_norm = _unicode_normalize(raw_value)
    script = _detect_script(unicode_norm)
    normalized_original = unicode_norm
    source_words = _source_word_count(raw_value)

    latin_translit: str | None = None
    method = ""
    warning: str | None = None
    skeleton = ""

    if script == NameScript.arabic:
        skeleton = arabic_consonant_skeleton(raw_value, preserve_spaces=True)
        method = "arabic_consonant_skeleton"
        latin_translit = skeleton.lower()
    elif script == NameScript.cyrillic:
        latin_translit = _map_script(raw_value, CYRILLIC_TO_LATIN)
        method = "cyrillic_formal_transliteration"
        skeleton = _consonant_skeleton(latin_translit)
    elif script == NameScript.greek:
        latin_translit = _map_script(raw_value, GREEK_TO_LATIN)
        method = "greek_formal_transliteration"
        skeleton = _consonant_skeleton(latin_translit)
    elif script == NameScript.latin:
        latin_translit = unicode_norm
        method = "latin_native"
        skeleton = _consonant_skeleton(unicode_norm)
    elif script == NameScript.mixed:
        latin_translit = unicode_norm
        method = "mixed_script_unicode"
        skeleton = _consonant_skeleton(unicode_norm)
        warning = "Mixed-script name — transliteration may be incomplete"
    else:
        latin_translit = unicode_norm
        method = "unicode_normalization_fallback"
        skeleton = _consonant_skeleton(unicode_norm)
        warning = "Unsupported script — using Unicode normalization only"

    normalized_latin = _latin_normalize(latin_translit or "")
    normalized_latin_variant = TRANSLITERATION_VARIANTS.get(normalized_latin.lower(), normalized_latin.lower())
    tokens = tuple(re.findall(r"[a-z0-9]+", normalized_latin_variant))
    tokens_no_articles = tuple(t for t in tokens if t.lower() not in COMMON_ARTICLES)
    if honorific_strip:
        tokens_no_articles = tuple(t for t in tokens_no_articles if t.lower() not in COMMON_HONORIFICS)
    initials = "".join(t[0] for t in tokens if t) if tokens else ""

    # Short-name detection based on SOURCE text word count, not transliterated
    is_short = source_words <= 1 or (source_words == 2 and len(tokens[0]) <= 2 if tokens else True)

    return NameRepresentation(
        raw_value=raw_value, record_id=record_id,
        unicode_normalized=unicode_norm, script=script,
        normalized_original_script=normalized_original,
        latin_transliteration=latin_translit,
        normalized_latin_transliteration=normalized_latin_variant,
        consonant_skeleton=skeleton,
        normalized_skeleton=normalized_latin_variant.replace(" ", ""),
        tokens=tokens, tokens_no_articles=tokens_no_articles,
        initials=initials,
        normalization_version=NORMALIZATION_VERSION,
        transliteration_method=method, warning=warning,
        token_count=source_words,  # source word count, not transliterated
        is_short_name=is_short,
    )


def _map_script(text: str, mapping: dict[int, str]) -> str:
    result: list[str] = []
    for ch in text:
        mapped = mapping.get(ord(ch))
        result.append(mapped if mapped is not None else ch)
    return "".join(result)


# ═══════════════════════════════════════════════════════════
# Multi-channel comparison — precise provenance for every channel
# ═══════════════════════════════════════════════════════════

class NameComparisonChannel(StrEnum):
    # Same-script channels
    exact_original = "exact_original"
    normalized_original = "normalized_original"
    # Formal transliteration (character-level mapping: Cyrillic, Greek)
    formal_transliteration_match = "formal_transliteration_match"
    # Consonant-skeleton cross-script (Arabic → Latin skeleton)
    consonant_skeleton_compatible = "consonant_skeleton_compatible"
    # Known Latin spelling variants (Muhammad→muhammad)
    known_variant_match = "known_variant_match"
    # Token-based channels
    token_reordered_compatible = "token_reordered_compatible"
    token_set_compatible = "token_set_compatible"
    # Weak channels
    initials_match = "initials_match"
    ambiguous = "ambiguous"
    mismatch = "mismatch"


@dataclass(slots=True)
class NameComparisonResult:
    channel: NameComparisonChannel = NameComparisonChannel.mismatch
    reason_code: str = "name_mismatch"
    fuzzy_score: float = 0.0
    is_cross_script: bool = False
    is_formal_transliteration: bool = False  # Cyrillic/Greek character map
    is_consonant_skeleton: bool = False      # Arabic consonant skeleton
    is_known_variant: bool = False           # TRANSLITERATION_VARIANTS
    is_token_reordered: bool = False
    left_representation: NameRepresentation | None = None
    right_representation: NameRepresentation | None = None
    detail: str = ""


def compare_names(
    left: NameRepresentation,
    right: NameRepresentation,
    fuzzy_threshold: float = 72.0,
) -> NameComparisonResult:
    """Multi-channel deterministic name comparison with precise provenance."""
    cross_script = left.script != right.script

    if not left.raw_value.strip() and not right.raw_value.strip():
        return NameComparisonResult(reason_code="both_missing", detail="Both names are missing")
    if not left.raw_value.strip():
        return NameComparisonResult(reason_code="left_missing", detail="Left name is missing")
    if not right.raw_value.strip():
        return NameComparisonResult(reason_code="right_missing", detail="Right name is missing")

    # Channel 1: Exact original-script match
    if left.normalized_original_script and left.normalized_original_script == right.normalized_original_script:
        if not cross_script:
            return NameComparisonResult(
                channel=NameComparisonChannel.exact_original,
                reason_code="name_exact_original_script", fuzzy_score=100.0,
                left_representation=left, right_representation=right,
                detail=f"Exact same-script match",
            )

    # Channel 2: Normalized original-script match (same script, RapidFuzz ≥95)
    if not cross_script and left.normalized_original_script and right.normalized_original_script:
        from rapidfuzz.fuzz import ratio as fuzz_ratio
        orig_fuzzy = fuzz_ratio(left.normalized_original_script, right.normalized_original_script)
        if orig_fuzzy >= 95:
            return NameComparisonResult(
                channel=NameComparisonChannel.normalized_original,
                reason_code="name_normalized_original", fuzzy_score=orig_fuzzy,
                left_representation=left, right_representation=right,
                detail=f"Normalized same-script match: {orig_fuzzy:.0f}/100",
            )

    # Channel 3: Known variant match (TRANSLITERATION_VARIANTS normalization)
    if (
        left.normalized_latin_transliteration
        and right.normalized_latin_transliteration
        and left.normalized_latin_transliteration == right.normalized_latin_transliteration
    ):
        # Check if this equality came from variant normalization
        left_raw = _latin_normalize(left.latin_transliteration or "")
        right_raw = _latin_normalize(right.latin_transliteration or "")
        if left_raw != right_raw:
            return NameComparisonResult(
                channel=NameComparisonChannel.known_variant_match,
                reason_code="name_known_variant_match",
                fuzzy_score=100.0,
                is_cross_script=cross_script, is_known_variant=True,
                left_representation=left, right_representation=right,
                detail=f"Known variant normalization matched: '{left.normalized_latin_transliteration}'",
            )

    # Channel 4: Formal transliteration match (Cyrillic/Greek character mapping)
    if left.normalized_latin_transliteration and right.normalized_latin_transliteration:
        from rapidfuzz.fuzz import ratio as fuzz_ratio
        latin_fuzzy = fuzz_ratio(
            left.normalized_latin_transliteration,
            right.normalized_latin_transliteration,
        )
        if latin_fuzzy >= 90:
            is_formal = (
                left.transliteration_method in ("cyrillic_formal_transliteration", "greek_formal_transliteration")
                or right.transliteration_method in ("cyrillic_formal_transliteration", "greek_formal_transliteration")
            )
            return NameComparisonResult(
                channel=(
                    NameComparisonChannel.formal_transliteration_match if (cross_script and is_formal)
                    else NameComparisonChannel.normalized_original
                ),
                reason_code=(
                    "name_formal_transliteration_match" if (cross_script and is_formal)
                    else "name_normalized_latin"
                ),
                fuzzy_score=latin_fuzzy,
                is_cross_script=cross_script,
                is_formal_transliteration=(cross_script and is_formal),
                left_representation=left, right_representation=right,
                detail=f"Formal transliteration match: {latin_fuzzy:.0f}/100 (cross-script={cross_script})",
            )

    # Channel 5: Consonant skeleton match (cross-script, mainly Arabic)
    if cross_script and left.consonant_skeleton and right.consonant_skeleton:
        from rapidfuzz.fuzz import ratio as fuzz_ratio
        skel_fuzzy = fuzz_ratio(left.consonant_skeleton, right.consonant_skeleton)
        if skel_fuzzy >= 72:
            return NameComparisonResult(
                channel=NameComparisonChannel.consonant_skeleton_compatible,
                reason_code="name_consonant_skeleton_compatible",
                fuzzy_score=skel_fuzzy,
                is_cross_script=True, is_consonant_skeleton=True,
                left_representation=left, right_representation=right,
                detail=f"Consonant skeleton compatible: '{left.consonant_skeleton}' ≈ '{right.consonant_skeleton}' ({skel_fuzzy:.0f}/100)",
            )

    # Channel 6: Token-set match (order-independent)
    if left.tokens and right.tokens:
        left_set = set(left.tokens)
        right_set = set(right.tokens)
        if left_set and right_set:
            overlap = left_set & right_set
            union = left_set | right_set
            jaccard = len(overlap) / len(union) if union else 0
            if jaccard >= 0.6:
                is_reordered = left_set == right_set and left.tokens != right.tokens
                return NameComparisonResult(
                    channel=(
                        NameComparisonChannel.token_reordered_compatible if is_reordered
                        else NameComparisonChannel.token_set_compatible
                    ),
                    reason_code=(
                        "name_token_reordered_compatible" if is_reordered
                        else "name_token_set_compatible"
                    ),
                    fuzzy_score=jaccard * 100,
                    is_cross_script=cross_script, is_token_reordered=is_reordered,
                    left_representation=left, right_representation=right,
                    detail=f"Token set Jaccard={jaccard:.2f} (reordered={is_reordered})",
                )

    # Channel 7: Initials match (very weak)
    if left.is_short_name and right.is_short_name and left.initials and right.initials:
        if left.initials == right.initials and len(left.initials) >= 2:
            return NameComparisonResult(
                channel=NameComparisonChannel.initials_match,
                reason_code="name_initials_match", fuzzy_score=60.0,
                detail=f"Initials match: '{left.initials}'",
            )

    # Fallback: RapidFuzz on normalized Latin
    if left.normalized_latin_transliteration and right.normalized_latin_transliteration:
        from rapidfuzz.fuzz import ratio as fuzz_ratio
        fallback_fuzzy = fuzz_ratio(
            left.normalized_latin_transliteration,
            right.normalized_latin_transliteration,
        )
        if fallback_fuzzy >= fuzzy_threshold:
            channel = (
                NameComparisonChannel.formal_transliteration_match if cross_script
                else NameComparisonChannel.normalized_original
            )
            return NameComparisonResult(
                channel=channel,
                reason_code=("name_fuzzy_similarity" if cross_script else "name_compatible"),
                fuzzy_score=fallback_fuzzy,
                is_cross_script=cross_script,
                left_representation=left, right_representation=right,
                detail=f"Fuzzy similarity: {fallback_fuzzy:.0f}/100",
            )
        elif fallback_fuzzy >= 45:
            return NameComparisonResult(
                channel=NameComparisonChannel.ambiguous,
                reason_code="name_partial", fuzzy_score=fallback_fuzzy,
                is_cross_script=cross_script,
                left_representation=left, right_representation=right,
                detail=f"Partial fuzzy similarity: {fallback_fuzzy:.0f}/100",
            )

    from rapidfuzz.fuzz import ratio as fuzz_ratio
    final_fuzzy = fuzz_ratio(
        left.normalized_latin_transliteration or "",
        right.normalized_latin_transliteration or "",
    ) if left.normalized_latin_transliteration and right.normalized_latin_transliteration else 0.0

    return NameComparisonResult(
        channel=NameComparisonChannel.mismatch,
        reason_code="name_divergent", fuzzy_score=final_fuzzy,
        is_cross_script=cross_script,
        detail=f"Names diverge: fuzzy={final_fuzzy:.0f}/100",
    )
