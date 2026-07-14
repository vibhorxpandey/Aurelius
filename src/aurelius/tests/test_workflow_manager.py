"""Full-DAG dry run with a mocked LLM and stubbed network — reaches the finish node,
populates the audit trail + evidence ledger, and writes a session checkpoint."""
from __future__ import annotations

import json

import pytest

from aurelius.orchestration.workflow_manager import ResearchWorkflowManager, run_research_graph


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    # Hermetic output dir (checkpoints + any saved files land here, not the real home).
    monkeypatch.setenv("AURELIUS_OUTPUT_DIR", str(tmp_path))
    # No network: stub the two tools that would call out.
    monkeypatch.setattr(
        "aurelius.agents.hypothesis.literature_miner_agent.search.web_search",
        lambda *a, **k: {"ok": True, "results": [
            {"title": "Relevant paper (2020)", "url": "http://x", "content": "finding"}]},
    )
    monkeypatch.setattr(
        "aurelius.agents.verification.citation_verifier_agent.ledger.verify_claims",
        lambda items: {
            "ledger": [{"claim": items[0], "verdict": "verified"}],
            "verification_score": 1.0,
            "counts": {"verified": 1, "total": 1, "retracted": 0, "unverified": 0},
            "markdown": "STATUS: VERIFIED",
        },
    )
    # No key: every agent's LLM call returns canned text.
    monkeypatch.setattr("aurelius.autonomous.llm.complete", lambda *a, **k: "Mock LLM output.")


def test_full_dag_reaches_finish_and_checkpoints():
    result = run_research_graph("Effect of sleep duration on reaction time", save=False)
    assert result["status"] == "completed"
    state = result["final_state"]

    # Reached the terminal stage and every stage logged something.
    agents_run = {e["agent"] for e in result["audit_trail"]}
    assert {"Literature Miner", "Citation Verifier", "Proof of Rigor", "Patent Freedom"} <= agents_run

    # Load-bearing outputs are populated.
    assert state["literature_summary"]
    assert state["hypothesis"]
    assert state["evidence_ledger"]
    assert state["proof_of_rigor"]
    assert result["verification_report"]["verification_score"] == 1.0

    # A resumable checkpoint was written for the session.
    cp = result["checkpoint"]
    data = json.loads(open(cp, encoding="utf-8").read())
    assert data["completed_node"] == "patent_freedom"
    assert data["next_node"] is None


def test_rejected_topic_short_circuits():
    result = run_research_graph("An existential hermeneutic reading of lived experience", save=False)
    state = result["final_state"]
    assert state["approved"] is False
    agents_run = {e["agent"] for e in result["audit_trail"]}
    # It screened out and jumped to attestation without designing an experiment.
    assert "Experiment Designer" not in agents_run
    assert "Proof of Rigor" in agents_run


def test_breakpoint_pauses_then_resumes():
    manager = ResearchWorkflowManager(save=False)
    manager.add_human_breakpoint("verify_citations")
    paused = manager.run("Effect of caffeine on typing speed")
    assert paused["status"] == "paused"
    assert paused["next_node"] == "verify_citations"

    resumed = manager.resume(paused["session_id"], approval=True)
    assert resumed["status"] == "completed"
    assert resumed["final_state"]["evidence_ledger"]
