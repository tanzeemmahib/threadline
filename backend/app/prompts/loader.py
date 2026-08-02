from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    template_id: str
    version: str
    content: str


@lru_cache
def load_prompt(template_id: str, version: str = "v1") -> PromptTemplate:
    path = Path(__file__).with_name("templates") / f"{template_id}.{version}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown prompt template: {template_id}.{version}")
    return PromptTemplate(template_id=template_id, version=version, content=path.read_text("utf-8"))
