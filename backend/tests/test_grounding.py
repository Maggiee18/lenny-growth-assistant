"""Grounding contract tests (see architecture.md "Grounding contract").

These exercise app.agents.tools.answer_from_sources directly against a fake
LLM provider, independent of the DB/HTTP layers already covered elsewhere,
so the abstention rule itself -- "no chunks => refuse, never invent" -- is
pinned down as a unit behavior.
"""
from app.agents.tools import ABSTENTION_MESSAGE, answer_from_sources
from app.retrieval.retriever import RetrievedChunk
import uuid


def _chunk(title="Some Episode", content="Retention improves when onboarding is shorter.", score=0.8):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        episode="Ep 1",
        source_url="https://example.com/ep1",
        content=content,
        relevance_score=score,
        retrieval_method="vector",
    )


async def test_empty_retrieval_abstains(fake_chat_provider):
    result = await answer_from_sources(fake_chat_provider, "unsupported question", [], [])
    assert result.abstained is True
    assert result.content == ABSTENTION_MESSAGE
    assert result.sources == []


async def test_grounded_answer_with_strong_evidence_is_not_abstained(fake_chat_provider):
    chunks = [_chunk(score=0.91)]
    result = await answer_from_sources(fake_chat_provider, "How does onboarding affect retention?", [], chunks)
    assert result.abstained is False
    assert result.sources == chunks
    assert result.content  # model produced an answer


async def test_multi_source_answer_carries_all_sources_for_citation(fake_chat_provider):
    chunks = [_chunk(title="Ep A", score=0.9), _chunk(title="Ep B", score=0.7)]
    result = await answer_from_sources(fake_chat_provider, "Compare retention approaches", [], chunks)
    titles = {s.title for s in result.sources}
    assert titles == {"Ep A", "Ep B"}


async def test_weak_single_low_score_chunk_still_passed_through_for_partial_answer(fake_chat_provider):
    # Thresholding happens in retrieval.retriever, not in answer_from_sources --
    # once a chunk is deemed relevant enough to retrieve, the agent answers
    # with it but the prompt instructs the model to flag partial coverage.
    chunks = [_chunk(score=0.56)]
    result = await answer_from_sources(fake_chat_provider, "Edge-of-threshold question", [], chunks)
    assert result.abstained is False
    assert "Transcript excerpts" in fake_chat_provider.last_messages[-1].content


async def test_system_prompt_instructs_model_to_treat_transcript_as_untrusted_data(fake_chat_provider):
    chunks = [_chunk()]
    await answer_from_sources(fake_chat_provider, "question", [], chunks)
    system_msg = fake_chat_provider.last_messages[0]
    assert system_msg.role == "system"
    assert "untrusted data" in system_msg.content.lower()
    assert "never invent" in system_msg.content.lower() or "never state a fact" in system_msg.content.lower()
