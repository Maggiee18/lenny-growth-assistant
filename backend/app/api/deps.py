from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import PodcastAgent
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.factory import get_chat_provider, get_embedding_provider


def get_app_settings() -> Settings:
    return get_settings()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db():
        yield session


def get_llm_provider() -> LLMProvider:
    return get_chat_provider()


def get_emb_provider() -> EmbeddingProvider:
    return get_embedding_provider()


def get_agent() -> PodcastAgent:
    return PodcastAgent(get_chat_provider(), get_embedding_provider(), get_settings())
