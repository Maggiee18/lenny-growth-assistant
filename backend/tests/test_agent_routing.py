import pytest

from app.agents.router import Intent, classify_intent


@pytest.mark.parametrize(
    "message",
    [
        "Can you write a ship 30 for 30 essay about activation?",
        "Turn this into a Ship30 post",
        "Draft an essay on retention loops",
        "write an essay about this",
    ],
)
def test_classifies_ship30_requests(message):
    assert classify_intent(message) == Intent.SHIP30


@pytest.mark.parametrize(
    "message",
    [
        "Generate an HTML page summarizing this",
        "Can you make a landing page for this idea?",
        "Give me the html/css for a pricing table",
    ],
)
def test_classifies_html_artifact_requests(message):
    assert classify_intent(message) == Intent.HTML_ARTIFACT


@pytest.mark.parametrize(
    "message",
    [
        "Create a markdown summary of this conversation",
        "Make me a one-pager on this",
        "Give me a cheat sheet for onboarding",
    ],
)
def test_classifies_markdown_artifact_requests(message):
    assert classify_intent(message) == Intent.MARKDOWN_ARTIFACT


@pytest.mark.parametrize(
    "message",
    [
        "What does Lenny's guests say about pricing?",
        "How should I think about retention?",
        "What's the difference between activation and engagement?",
    ],
)
def test_classifies_plain_questions_as_grounded_qa(message):
    assert classify_intent(message) == Intent.GROUNDED_QA


def test_html_pattern_takes_priority_over_markdown_when_both_could_match():
    # "artifact" alone would match markdown; explicit "html" should win.
    assert classify_intent("Generate an HTML artifact for this") == Intent.HTML_ARTIFACT


async def test_agent_dispatches_ship30_intent_and_abstains_without_evidence(
    db_session, fake_chat_provider, fake_embedding_provider
):
    """No transcripts are seeded in db_session, so retrieval returns nothing;
    the ship30 tool must abstain rather than fabricate an essay."""
    from app.agents.agent import PodcastAgent
    from app.core.config import get_settings

    agent = PodcastAgent(fake_chat_provider, fake_embedding_provider, get_settings())
    result = await agent.handle_turn(db_session, "Write a ship 30 essay about growth loops", [])

    assert result.intent == Intent.SHIP30
    assert result.abstained is True
    assert result.artifact_content is None


async def test_agent_dispatches_grounded_qa_intent_by_default(db_session, fake_chat_provider, fake_embedding_provider):
    from app.agents.agent import PodcastAgent
    from app.core.config import get_settings

    agent = PodcastAgent(fake_chat_provider, fake_embedding_provider, get_settings())
    result = await agent.handle_turn(db_session, "What do guests say about retention?", [])

    assert result.intent == Intent.GROUNDED_QA
