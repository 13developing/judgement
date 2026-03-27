from __future__ import annotations

import json
from collections.abc import Generator
from typing_extensions import override

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from backend.database import get_session
from backend.main import app
from backend.services.providers.base import LLMProvider


class MockLLMProvider(LLMProvider):
    @property
    @override
    def api_key(self) -> str:
        return "mock-api-key"

    @property
    @override
    def base_url(self) -> str:
        return "https://mock.provider.local"

    @property
    @override
    def model(self) -> str:
        return "mock-model"

    @override
    async def chat_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        return json.dumps(
            {
                "question_type": "short_answer",
                "recognized_content": "mock image content",
                "judgment": "correct",
                "score": 5,
                "total_score": 5,
                "explanation": "mock image response",
            },
            ensure_ascii=False,
        )

    @override
    async def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        return json.dumps(
            {
                "question_type": "short_answer",
                "recognized_content": "mock text content",
                "judgment": "correct",
                "score": 5,
                "total_score": 5,
                "explanation": "mock text response",
            },
            ensure_ascii=False,
        )


@pytest.fixture()
def test_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def test_session(test_engine: Engine) -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        yield session


@pytest.fixture()
def client(test_session: Session) -> Generator[TestClient, None, None]:
    def _get_test_session() -> Generator[Session, None, None]:
        yield test_session

    app.dependency_overrides[get_session] = _get_test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        _ = app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
def mock_provider() -> MockLLMProvider:
    return MockLLMProvider()
