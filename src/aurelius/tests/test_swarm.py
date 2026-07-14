"""Swarm coordinator tests — parallel execution + correct merge semantics."""
from __future__ import annotations

from aurelius.agents.base import ResearchAgent
from aurelius.orchestration.state import new_state
from aurelius.orchestration.swarm import AgentSwarmCoordinator


class _WriterAgent(ResearchAgent):
    def __init__(self, name, key, value):
        super().__init__(name, f"write {key}")
        self.key, self.value = key, value

    def execute(self, state):
        state[self.key] = self.value
        return self.log(state, "write", self.value)


class _BoomAgent(ResearchAgent):
    def __init__(self):
        super().__init__("Boom", "always fails")

    def execute(self, state):
        raise RuntimeError("kaboom")


def test_parallel_merge_disjoint_keys():
    coord = AgentSwarmCoordinator()
    agents = [
        _WriterAgent("A", "hypothesis", "H"),
        _WriterAgent("B", "gaps", ["g1"]),
    ]
    out = coord.run_parallel(new_state("t"), agents)
    assert out["hypothesis"] == "H"
    assert out["gaps"] == ["g1"]
    # both agents' audit entries are merged
    actions = [e["agent"] for e in out["audit_trail"]]
    assert "A" in actions and "B" in actions


def test_stale_copy_does_not_clobber():
    # 'A' sets literature_summary; 'B' never touches it. B's deep copy still has the old
    # empty value, but the merge must NOT write that stale value back over A's.
    coord = AgentSwarmCoordinator()
    st = new_state("t")
    st["literature_summary"] = "seed"
    agents = [_WriterAgent("A", "literature_summary", "fresh"), _WriterAgent("B", "gaps", ["g"])]
    out = coord.run_parallel(st, agents)
    assert out["literature_summary"] == "fresh"
    assert out["gaps"] == ["g"]


def test_failed_agent_is_isolated():
    coord = AgentSwarmCoordinator()
    out = coord.run_parallel(new_state("t"), [_WriterAgent("A", "hypothesis", "H"), _BoomAgent()])
    assert out["hypothesis"] == "H"  # good agent still contributes
    assert any(e.get("metadata", {}).get("failed") for e in out["audit_trail"])
