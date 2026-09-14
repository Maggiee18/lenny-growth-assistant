"""Unit tests for the eval harness's own aggregation logic.

Run with: python -m pytest eval/test_run_eval.py -v (uses the backend venv's
pytest, e.g. backend/.venv/Scripts/python.exe -m pytest eval/test_run_eval.py)

These exist because the harness itself had a real bug found live: a summary
statistic (artifact_generation_success_rate) came back as 3.0 -- an
impossible value for something meant to be a 0-1 rate -- because the
denominator checked `"expect_artifact_type" in str(result_record)`, which is
never true (that key lives on the original question dict, not the result
record built during the run). See run_eval.py::_summarize's comment for
the fix.
"""
from run_eval import _summarize, word_count


def _base_config():
    return {"provider": "ollama", "model": "llama3.1:8b"}


def test_artifact_generation_success_rate_is_a_fraction_not_a_multiple():
    questions = [
        {"id": "q7", "expect_artifact_type": "ship30"},
        {"id": "q8", "expect_artifact_type": "markdown"},
        {"id": "q9", "expect_artifact_type": "html"},
    ]
    results = [
        {"id": "q7", "has_artifact": True},
        {"id": "q8", "has_artifact": True},
        {"id": "q9", "has_artifact": True},
    ]
    summary = _summarize(results, questions, _base_config())
    assert summary["artifact_generation_success_rate"] == 1.0


def test_artifact_generation_success_rate_reflects_partial_failure():
    questions = [
        {"id": "q7", "expect_artifact_type": "ship30"},
        {"id": "q8", "expect_artifact_type": "markdown"},
    ]
    results = [
        {"id": "q7", "has_artifact": True},
        {"id": "q8", "has_artifact": False},
    ]
    summary = _summarize(results, questions, _base_config())
    assert summary["artifact_generation_success_rate"] == 0.5


def test_artifact_generation_success_rate_is_none_when_no_artifact_questions():
    questions = [{"id": "q1", "expect_sources": True}]
    results = [{"id": "q1", "has_artifact": False}]
    summary = _summarize(results, questions, _base_config())
    assert summary["artifact_generation_success_rate"] is None


def test_retrieval_hit_rate_only_considers_non_abstained_questions():
    questions = [{"id": "q1"}, {"id": "q2"}]
    results = [
        {"id": "q1", "abstained": False, "source_count": 3},
        {"id": "q2", "abstained": True, "source_count": 0},
    ]
    summary = _summarize(results, questions, _base_config())
    assert summary["retrieval_hit_rate"] == 1.0


def test_assertion_pass_rate_counts_only_check_suffixed_fields():
    questions = [{"id": "q1"}]
    results = [{"id": "q1", "abstain_check": "pass", "sources_check": "FAIL", "latency_ms": 123.0}]
    summary = _summarize(results, questions, _base_config())
    assert summary["assertion_checks_total"] == 2
    assert summary["assertion_checks_passed"] == 1
    assert summary["assertion_pass_rate"] == 0.5


def test_word_count_strips_markdown_punctuation():
    assert word_count("# Title\n\nSome **bold** text here.") == 5
