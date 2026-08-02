from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _integer(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


def _first(*names: str, default: str) -> str:
    return next((value for name in names if (value := os.getenv(name))), default)


def _optional(*names: str) -> str | None:
    return next((value for name in names if (value := os.getenv(name))), None)


BACKEND_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "THREADLINE Backend"
    app_version: str = "2.0.0"
    provider_mode: str = _first("LLM_PROVIDER", "THREADLINE_PROVIDER_MODE", default="mock")
    openai_base_url: str = _first(
        "LLM_BASE_URL", "THREADLINE_OPENAI_BASE_URL", default="https://api.openai.com/v1"
    )
    openai_api_key: str | None = _optional("LLM_API_KEY", "THREADLINE_OPENAI_API_KEY")
    openai_model: str = _first("LLM_MODEL", "THREADLINE_OPENAI_MODEL", default="gpt-4.1-mini")
    llm_temperature: float = _float("LLM_TEMPERATURE", 0.0)
    llm_timeout_seconds: float = _float("LLM_TIMEOUT_SECONDS", 30.0)
    llm_max_retries: int = _integer("LLM_MAX_RETRIES", 1)
    llm_max_concurrent_calls: int = _integer("LLM_MAX_CONCURRENT_CALLS", 4)
    frontend_origins: tuple[str, ...] = tuple(
        value.strip()
        for value in os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if value.strip()
    )
    max_records_per_request: int = _integer("MAX_RECORDS_PER_REQUEST", 250)
    max_record_text_characters: int = _integer("MAX_RECORD_TEXT_CHARACTERS", 20_000)
    max_total_request_characters: int = _integer("MAX_TOTAL_REQUEST_CHARACTERS", 1_000_000)
    max_candidates_per_record: int = _integer("MAX_CANDIDATES_PER_RECORD", 10)
    max_benchmark_identities: int = _integer("MAX_BENCHMARK_IDENTITIES", 500)
    max_concurrent_evaluation_jobs: int = _integer("MAX_CONCURRENT_EVALUATION_JOBS", 1)
    database_path: str = os.getenv(
        "THREADLINE_DATABASE_PATH", str(BACKEND_ROOT / "data" / "threadline.db")
    )
    export_directory: str = os.getenv(
        "THREADLINE_EXPORT_DIRECTORY", str(BACKEND_ROOT / "data" / "exports")
    )

    @property
    def credentials_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def provider_configured(self) -> bool:
        return self.provider_mode == "mock" or self.credentials_configured


@lru_cache
def get_settings() -> Settings:
    return Settings()
