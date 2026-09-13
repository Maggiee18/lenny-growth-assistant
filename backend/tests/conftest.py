"""Test configuration.

DB-backed tests use an in-memory SQLite database via aiosqlite so the suite
runs with zero external dependencies. pgvector-specific behavior (cosine
distance search, ivfflat index) cannot run on SQLite, so retrieval tests
exercise the retriever against a fake embedding provider and a stub query
path (test_retrieval.py) rather than a real vector index -- true pgvector
integration is covered by eval/ against the real Docker Postgres, documented
in architecture.md "Testing strategy".
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.providers.base import ChatMessage, ChatResult, EmbeddingProvider, LLMProvider


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


class FakeChatProvider(LLMProvider):
    name = "fake"

    def __init__(self, response: str = "This is a grounded test answer.", model: str = "fake-model"):
        self.response = response
        self._model = model
        self.last_messages: list[ChatMessage] = []

    @property
    def model(self) -> str:
        return self._model

    async def is_available(self):
        return True, "ok"

    async def chat(self, messages, *, tools=None, temperature=0.3, max_tokens=2000):
        self.last_messages = messages
        return ChatResult(content=self.response, tool_calls=[], raw_model=self._model, stop_reason="stop")

    async def stream_chat(self, messages, *, temperature=0.3, max_tokens=2000):
        for word in self.response.split():
            yield word + " "


class FakeEmbeddingProvider(EmbeddingProvider):
    name = "fake-embeddings"

    def __init__(self, dimensions: int = 8):
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def is_available(self):
        return True, "ok"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float((hash(t) >> i) % 7) for i in range(self._dimensions)] for t in texts]


@pytest.fixture
def fake_chat_provider() -> FakeChatProvider:
    return FakeChatProvider()


@pytest.fixture
def fake_embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest_asyncio.fixture
async def client(db_session, fake_chat_provider, fake_embedding_provider) -> AsyncIterator[AsyncClient]:
    from app.agents.agent import PodcastAgent
    from app.api.deps import get_agent
    from app.core.config import get_settings
    from app.main import app

    async def _override_get_db():
        yield db_session

    def _override_get_agent():
        return PodcastAgent(fake_chat_provider, fake_embedding_provider, get_settings())

    app.dependency_overrides[get_db_session] = _override_get_db
    app.dependency_overrides[get_agent] = _override_get_agent
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def random_uuid_str() -> str:
    return str(uuid.uuid4())
