"""Phase 6 — multilingual search (mocked OpenAlex) and episodic memory."""
from __future__ import annotations

import pytest

from aurelius.agents.memory_agent import EpisodicMemoryAgent
from aurelius.memory import episodic
from aurelius.orchestration.state import new_state
from aurelius.tools import multilingual


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv("AURELIUS_OUTPUT_DIR", str(tmp_path))


# --- multilingual -----------------------------------------------------------------
def test_multilingual_search_merges_languages(monkeypatch):
    monkeypatch.setattr(multilingual, "_translate", lambda q, lang, m, p: f"{q}-{lang}")
    monkeypatch.setattr(multilingual, "_openalex_search",
                        lambda q, lang, n: [{"title": f"work-{lang}", "language": lang}])
    r = multilingual.multilingual_search("glucose", languages=["zh", "es"])
    assert r["ok"] and r["total_results"] == 2 and r["translated"] is True
    assert r["by_language"]["zh"]["query"] == "glucose-zh"


def test_multilingual_untranslated_without_llm(monkeypatch):
    monkeypatch.setattr(multilingual, "_openalex_search", lambda q, lang, n: [])

    # Force the no-key path regardless of the host environment (a real OPENAI_API_KEY in
    # the user's env must not turn this into a live network call).
    def no_key(*a, **k):
        raise multilingual.llm.LLMError("no key")

    monkeypatch.setattr(multilingual.llm, "complete", no_key)
    r = multilingual.multilingual_search("glucose", languages=["zh"])
    assert r["translated"] is False and "untranslated" in r["note"]


# --- episodic memory ---------------------------------------------------------------
def _finished_state(topic, score=1.0, approved=True):
    st = new_state(topic)
    st["hypothesis"] = f"H about {topic}"
    st["approved"] = approved
    st["verification_report"] = {"verification_score": score,
                                 "counts": {"total": 2, "verified": int(2 * score), "retracted": 0}}
    return st


def test_record_then_recall_ranks_by_relevance():
    episodic.record_episode(_finished_state("caffeine and reaction time"))
    episodic.record_episode(_finished_state("solar panel efficiency"))
    hits = episodic.recall_episodes("effect of caffeine on typing", k=2)
    assert hits and "caffeine" in hits[0]["topic"]


def test_lessons_capture_failure():
    st = _finished_state("weak topic", score=0.0)
    ep = episodic.record_episode(st)
    assert any("failed verification" in l for l in ep["lessons"])


def test_rejected_run_recorded_as_lesson():
    st = _finished_state("banned topic", approved=False)
    st["screen_reason"] = "restricted domain"
    ep = episodic.record_episode(st)
    assert any("rejected" in l.lower() for l in ep["lessons"])


def test_recall_empty_store():
    assert episodic.recall_episodes("anything") == []


def test_memory_agent_roundtrip():
    st = _finished_state("sleep and memory consolidation")
    EpisodicMemoryAgent(mode="record").execute(st)

    st2 = new_state("sleep duration and recall")
    out = EpisodicMemoryAgent(mode="recall").execute(st2)
    assert out["memory_recall"] and "sleep" in out["memory_recall"][0]["topic"]
    assert out["audit_trail"][-1]["action"] == "recall_memory"


def test_memory_agent_rejects_bad_mode():
    with pytest.raises(ValueError):
        EpisodicMemoryAgent(mode="forget")
