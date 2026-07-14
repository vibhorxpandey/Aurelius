"""Agent tests with a mocked LLM and stubbed tools — no key, no network."""
from __future__ import annotations

import pytest

from aurelius.agents.base import PlaceholderAgent
from aurelius.agents.hypothesis import (
    HypothesisValidatorAgent,
    LiteratureMinerAgent,
    PatternDiscoveryAgent,
    TheoryGeneratorAgent,
)
from aurelius.agents.verification import CitationVerifierAgent
from aurelius.orchestration.state import new_state


@pytest.fixture
def state():
    return new_state("Impact of dietary fiber on glucose metabolism")


def test_literature_miner_summarizes(monkeypatch, state):
    monkeypatch.setattr(
        "aurelius.agents.hypothesis.literature_miner_agent.search.web_search",
        lambda *a, **k: {"ok": True, "results": [
            {"title": "Fiber and glucose", "url": "http://x", "content": "lowers glucose"}
        ]},
    )
    monkeypatch.setattr(LiteratureMinerAgent, "_llm", lambda self, *a, **k: "A summary.")
    out = LiteratureMinerAgent().execute(state)
    assert out["literature_summary"] == "A summary."
    assert out["candidate_citations"] == ["Fiber and glucose"]
    assert any(e["action"] == "mine_literature" for e in out["audit_trail"])


def test_literature_miner_no_llm_no_key(monkeypatch, state):
    monkeypatch.setattr(
        "aurelius.agents.hypothesis.literature_miner_agent.search.web_search",
        lambda *a, **k: {"ok": False, "results": []},
    )
    monkeypatch.setattr(LiteratureMinerAgent, "_llm", lambda self, *a, **k: None)
    out = LiteratureMinerAgent().execute(state)
    assert "unavailable" in out["literature_summary"].lower()  # graceful degradation


def test_theory_generator_selects_best(monkeypatch, state):
    monkeypatch.setattr(
        TheoryGeneratorAgent, "_llm",
        lambda self, *a, **k: '[{"statement":"H1","feasibility":9,"originality":8},'
                              '{"statement":"H2","feasibility":2,"originality":2}]',
    )
    out = TheoryGeneratorAgent().execute(state)
    assert out["hypothesis"] == "H1"
    assert len(out["alternative_hypotheses"]) == 2


def test_theory_generator_fallback_without_llm(monkeypatch, state):
    monkeypatch.setattr(TheoryGeneratorAgent, "_llm", lambda self, *a, **k: None)
    out = TheoryGeneratorAgent().execute(state)
    assert out["hypothesis"]  # non-empty deterministic fallback


def test_validator_rejects_restricted_topic():
    st = new_state("A phenomenological reading of existential poetry")
    out = HypothesisValidatorAgent().execute(st)
    assert out["approved"] is False
    assert "restricted" in out["screen_reason"].lower()


def test_validator_accepts_empirical_topic(monkeypatch, state):
    monkeypatch.setattr(HypothesisValidatorAgent, "_llm", lambda self, *a, **k: None)
    out = HypothesisValidatorAgent().execute(state)
    assert out["approved"] is True


def test_citation_verifier_reuses_ledger(monkeypatch, state):
    called = {}

    def fake_verify_claims(items):
        called["items"] = items
        return {
            "ledger": [{"claim": items[0], "verdict": "verified"}],
            "verification_score": 1.0,
            "counts": {"verified": 1, "total": 1},
            "markdown": "STATUS: VERIFIED",
        }

    monkeypatch.setattr(
        "aurelius.agents.verification.citation_verifier_agent.ledger.verify_claims",
        fake_verify_claims,
    )
    state["candidate_citations"] = ["Okun 1962"]
    out = CitationVerifierAgent().execute(state)
    assert out["verification_report"]["verification_score"] == 1.0
    assert out["evidence_ledger"][0]["verdict"] == "verified"
    assert "Okun 1962" in called["items"]  # delegated to the existing tool


def test_placeholder_passes_state_through():
    st = new_state("t")
    agent = PlaceholderAgent("Sandbox", "run code", "Phase 2")
    out = agent.execute(st)
    entry = out["audit_trail"][-1]
    assert entry["action"] == "skipped"
    assert entry["metadata"]["placeholder"] is True


def test_pattern_discovery_parses_bullets(monkeypatch, state):
    monkeypatch.setattr(
        PatternDiscoveryAgent, "_llm",
        lambda self, *a, **k: "- gap one\n- gap two\nnot a bullet",
    )
    out = PatternDiscoveryAgent().execute(state)
    assert out["gaps"] == ["gap one", "gap two"]
