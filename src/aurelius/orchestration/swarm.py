"""AgentSwarmCoordinator — run several agents in parallel and merge their results.

Used for the hypothesis-generation stage, where the Literature Miner, Pattern Discovery,
and Theory Generator agents can work concurrently (ARCHITECTURE.md §1.3). Each agent runs
on its own deep copy of the state (so there is no shared-mutation race); afterward the
coordinator merges each agent's produced keys and appends its audit entries in a
deterministic order.
"""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from .state import ResearchState, record
from ..agents.base import ResearchAgent


class AgentSwarmCoordinator:
    def __init__(self) -> None:
        self.agents: Dict[str, ResearchAgent] = {}

    def register_agent(self, agent: ResearchAgent) -> None:
        self.agents[agent.name] = agent

    def run_parallel(self, state: ResearchState, agents: List[ResearchAgent]) -> ResearchState:
        """Execute ``agents`` concurrently on copies of ``state`` and merge results.

        Merge policy: an agent contributes only the keys it actually changed relative to the
        base state (so a parallel agent's stale copy of a key never clobbers another agent's
        write); audit entries from every agent are appended, ordered by name for reproducibility.
        """
        base_len = len(state.get("audit_trail", []))
        base_snapshot = {k: copy.deepcopy(v) for k, v in state.items() if k != "audit_trail"}
        outputs: Dict[str, ResearchState] = {}

        with ThreadPoolExecutor(max_workers=max(1, len(agents))) as executor:
            futures = {
                executor.submit(agent.execute, copy.deepcopy(state)): agent.name
                for agent in agents
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    outputs[name] = future.result()
                except Exception as exc:  # keep the swarm alive if one agent fails
                    record(state, name, "error", str(exc), {"failed": True})

        for name in sorted(outputs):  # deterministic merge order
            result = outputs[name]
            for key, value in result.items():
                if key == "audit_trail":
                    continue
                if key in base_snapshot and value == base_snapshot[key]:
                    continue  # this agent did not change the key
                state[key] = value  # type: ignore[literal-required]
            state.setdefault("audit_trail", []).extend(result.get("audit_trail", [])[base_len:])

        return state

    def run_registered(self, state: ResearchState) -> ResearchState:
        """Run every registered agent in parallel (convenience wrapper)."""
        return self.run_parallel(state, list(self.agents.values()))
