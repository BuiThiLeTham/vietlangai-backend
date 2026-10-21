import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["AUTO_SEED"] = "true"
os.environ["ML_BASE_URL"] = "http://ml.invalid"

import pytest
from fastapi.testclient import TestClient

from app.integrations.ml_client import get_ml_client
from app.main import app


class FakeMl:
    async def translate(self, body: dict) -> dict:
        return {
            "text": "Hello" if body["target_lang"] == "en" else body["text"],
            "source_lang": body["source_lang"],
            "target_lang": body["target_lang"],
            "detected_lang": None,
            "route": "direct",
            "engine": "fake",
            "warnings": [],
            "steps": [],
        }

    async def ocr(self, filename: str, content: bytes, content_type: str) -> dict:
        return {"text": "xin chào", "engine": "fake", "warnings": []}

    async def asr(self, filename: str, content: bytes, content_type: str) -> dict:
        return {"text": "", "engine": "unloaded", "warnings": ["ASR chưa được nạp."]}


@pytest.fixture
def client():
    app.dependency_overrides[get_ml_client] = lambda: FakeMl()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
