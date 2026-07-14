"""Base class for all research agents.

Mirrors ARCHITECTURE.md §1.2 but deliberately **without LangChain**: an agent's ``model``
is just a model-name string handed to Aurelius's own ``autonomous.llm.complete`` (plain
REST, multi-provider). Agents degrade gracefully when no LLM key is configured — ``_llm``
returns ``None`` instead of raising — so the whole graph is runnable and unit-testable with
a mocked ``complete`` and no API key at all.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..autonomous import llm
from ..orchestration.state import ResearchState, record

DEFAULT_MODEL = "gpt-4o-mini-2024-07-18"


class ResearchAgent(ABC):
    """Common lifecycle, LLM access, and audit logging for every agent."""

    def __init__(
        self,
        name: str,
        role: str,
        model: str = DEFAULT_MODEL,
        provider: Optional[str] = None,
    ) -> None:
        self.name = name
        self.role = role
        self.model = model
        self.provider = provider
        self.execution_log: List[Dict[str, Any]] = []

    @abstractmethod
    def execute(self, state: ResearchState) -> ResearchState:
        """Do the agent's work and return the (updated) state."""

    # A graph node is any ``Callable[[state], state]`` — so an agent *is* a node.
    def __call__(self, state: ResearchState) -> ResearchState:
        return self.execute(state)

    def _llm(self, system: str, user: str, **kwargs: Any) -> Optional[str]:
        """Call the configured model; return ``None`` (never raise) if unavailable.

        This is what lets an agent run with no key configured: callers treat ``None`` as
        "LLM step skipped" and fall back to deterministic behavior.
        """
        try:
            return llm.complete(system, user, self.model, self.provider, **kwargs)
        except llm.LLMError:
            return None

    def log(
        self,
        state: ResearchState,
        action: str,
        result: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ResearchState:
        """Record an action to both this agent's log and the shared state audit trail."""
        entry = record(state, self.name, action, result, metadata)
        self.execution_log.append(entry)
        return state

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return list(self.execution_log)


class PlaceholderAgent(ResearchAgent):
    """A stage that belongs to a later phase.

    It does no work, but keeps the DAG shape complete and — crucially — records an honest
    'skipped' entry in the audit trail rather than pretending the capability exists.
    """

    def __init__(self, name: str, role: str, phase: str, **kwargs: Any) -> None:
        super().__init__(name, role, **kwargs)
        self.phase = phase

    def execute(self, state: ResearchState) -> ResearchState:
        return self.log(
            state,
            "skipped",
            f"{self.role} is a {self.phase} capability — not implemented in Phase 1.",
            {"phase": self.phase, "placeholder": True},
        )
