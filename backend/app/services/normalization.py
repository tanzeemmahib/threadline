from __future__ import annotations

import re
import unicodedata

from app.schemas.models import ExtractedField

ARABIC_VARIANTS = {
    "يوسف الحسن": ["yusuf hassan", "youssef hassan", "yusef hasan"],
}


def normalize_name(value: str) -> str:
    if value in ARABIC_VARIANTS:
        return ARABIC_VARIANTS[value][0]
    ascii_value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    words = re.findall(r"[a-z0-9]+", ascii_value.lower())
    return " ".join(word for word in words if word not in {"al", "el"})


def name_variants(value: str) -> list[str]:
    if value in ARABIC_VARIANTS:
        return [value, *ARABIC_VARIANTS[value]]
    normalized = normalize_name(value)
    compact = normalized.replace(" ", "")
    return list(dict.fromkeys([value, normalized, compact]))


def normalize_name_fields(fields: list[ExtractedField]) -> list[str]:
    names: list[str] = []
    for field in fields:
        if field.key == "name" and isinstance(field.value, str):
            field.normalized_value = normalize_name(field.value)
            names.extend(name_variants(field.value))
    return list(dict.fromkeys(names))
