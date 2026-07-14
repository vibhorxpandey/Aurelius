"""Agent-level tests for the Phase 2/3 agents (mocked LLM, hermetic output dir)."""
from __future__ import annotations

import pytest

from aurelius.agents.publication import ProofOfRigorAgent
from aurelius.agents.verification import MethodologyAuditorAgent
from aurelius.orchestration.state import new_state
from aurelius.proof import verify_proof


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv("AURELIUS_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr("aurelius.autonomous.llm.complete", lambda *a, **k: "no further concerns")


def test_methodology_auditor_populates_report():
    st = new_state("t")
    st["experiment_code"] = "for col in columns:\n    t, p = ttest_ind(a[col], b[col])\n"
    out = MethodologyAuditorAgent().execute(st)
    r = out["methodology_report"]
    assert "risk" in r and "findings" in r
    assert out["audit_trail"][-1]["action"] == "audit_methodology"


def test_proof_of_rigor_agent_produces_verifiable_proof():
    st = new_state("Effect of sleep on memory")
    st["hypothesis"] = "more sleep improves recall"
    st["evidence_ledger"] = [{"claim": "study A", "verdict": "verified"}]
    st["verification_report"] = {"verification_score": 1.0, "counts": {"total": 1}}
    out = ProofOfRigorAgent().execute(st)

    proof = out["proof"]
    assert len(proof["content_hash"]) == 64
    assert verify_proof(proof)["valid"] is True
    # graceful no-ops when unconfigured
    assert proof["ipfs"]["pinned"] is False
    assert proof["anchor"]["backend"] == "local"
    assert "content hash" in out["proof_of_rigor"].lower()
