from app.db.models import TranscriptChunk, TranscriptDocument
from app.retrieval.retriever import retrieve


async def _add_doc(db_session, title, content, embedding, source_url="https://x.test"):
    doc = TranscriptDocument(title=title, episode=None, source_url=source_url, content_hash=title)
    db_session.add(doc)
    await db_session.flush()
    db_session.add(TranscriptChunk(document_id=doc.id, chunk_index=0, content=content, embedding=embedding))
    await db_session.commit()
    return doc


async def test_retrieve_returns_empty_list_when_no_documents(db_session, fake_embedding_provider):
    results = await retrieve(db_session, fake_embedding_provider, "anything", top_k=5, similarity_threshold=0.55)
    assert results == []


async def test_retrieve_ranks_closest_vector_first(db_session, fake_embedding_provider):
    query = "pricing strategy"
    [query_vec] = await fake_embedding_provider.embed([query])
    off_vec = [v + 5 for v in query_vec]  # deliberately dissimilar

    await _add_doc(db_session, "Exact match doc", "irrelevant text", embedding=query_vec)
    await _add_doc(db_session, "Far doc", "irrelevant text", embedding=off_vec)

    results = await retrieve(db_session, fake_embedding_provider, query, top_k=5, similarity_threshold=0.0)
    assert results[0].title == "Exact match doc"


async def test_retrieve_respects_similarity_threshold_and_falls_back_to_keyword(db_session, fake_embedding_provider):
    query = "activation funnel"
    [query_vec] = await fake_embedding_provider.embed([query])
    unrelated_vec = [v + 100 for v in query_vec]

    await _add_doc(db_session, "Unrelated vector doc", "this document mentions the word funnel explicitly", embedding=unrelated_vec)

    # Threshold set high enough that the dissimilar vector match won't clear it,
    # so the keyword fallback (matching "funnel" in content) should kick in.
    results = await retrieve(db_session, fake_embedding_provider, query, top_k=5, similarity_threshold=0.999)
    assert any(r.retrieval_method == "keyword" for r in results)


async def test_retrieve_top_k_is_respected(db_session, fake_embedding_provider):
    query = "growth"
    [query_vec] = await fake_embedding_provider.embed([query])
    for i in range(5):
        await _add_doc(db_session, f"Doc {i}", "growth content", embedding=query_vec, source_url=f"https://x.test/{i}")

    results = await retrieve(db_session, fake_embedding_provider, query, top_k=2, similarity_threshold=0.0)
    assert len(results) == 2


async def test_retrieve_preserves_source_metadata(db_session, fake_embedding_provider):
    query = "retention"
    [query_vec] = await fake_embedding_provider.embed([query])
    await _add_doc(db_session, "Retention 101", "retention content", embedding=query_vec, source_url="https://podcast.test/ep9")

    results = await retrieve(db_session, fake_embedding_provider, query, top_k=5, similarity_threshold=0.0)
    assert results[0].source_url == "https://podcast.test/ep9"
    assert results[0].title == "Retention 101"
