from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.demo import demo_request
from app.main import create_app
from app.schemas.models import AnalyzeRequest


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        provider_mode="mock",
        openai_api_key=None,
        database_path=str(tmp_path / "threadline.db"),
        export_directory=str(tmp_path / "exports"),
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def demo() -> AnalyzeRequest:
    return demo_request().model_copy(deep=True)
