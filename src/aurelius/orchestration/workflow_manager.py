"""High-level orchestrator: build the graph, run a session, checkpoint, resume.

The manager owns session identity and the checkpoint location
(``<output_dir>/sessions/<session_id>.json``), registers human breakpoints, and normalizes
the result into the ``{status, session_id, final_state, audit_trail}`` shape the MCP tool and
CLI return.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..config import get_output_dir
from .graph import Paused
from .research_graph import build_research_graph
from .state import ResearchState, new_state, new_session_id


class ResearchWorkflowManager:
    def __init__(
        self,
        researcher_id: str = "local",
        model: str = "gpt-4o-mini-2024-07-18",
        provider: Optional[str] = None,
        *,
        save: bool = True,
        enable_sandbox: bool = False,
    ) -> None:
        self.researcher_id = researcher_id
        self.model = model
        self.provider = provider
        self.graph = build_research_graph(model, provider, save=save, enable_sandbox=enable_sandbox)
        self.breakpoints: Set[str] = set()

    def add_human_breakpoint(self, stage: str) -> None:
        """Pause the workflow *before* ``stage`` runs, awaiting a human ``resume``."""
        self.breakpoints.add(stage)

    def checkpoint_path(self, session_id: str) -> Path:
        return get_output_dir() / "sessions" / f"{session_id}.json"

    def run(
        self, topic: str, metadata: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a research session end-to-end (or until a breakpoint)."""
        session_id = session_id or new_session_id()
        state = new_state(topic, self.researcher_id, session_id, metadata)
        cp = self.checkpoint_path(session_id)
        result = self.graph.invoke(
            state, checkpoint_path=cp, breakpoints=frozenset(self.breakpoints)
        )
        return self._normalize(result, session_id, cp)

    def resume(self, session_id: str, approval: bool = True) -> Dict[str, Any]:
        """Resume a paused/checkpointed session by id."""
        cp = self.checkpoint_path(session_id)
        result = self.graph.resume(
            cp, approval=approval, breakpoints=frozenset(self.breakpoints)
        )
        return self._normalize(result, session_id, cp)

    @staticmethod
    def _normalize(result: Any, session_id: str, cp: Path) -> Dict[str, Any]:
        if isinstance(result, Paused):
            return {
                "status": "paused",
                "session_id": session_id,
                "next_node": result.next_node,
                "checkpoint": str(cp),
                "final_state": result.state,
                "audit_trail": result.state.get("audit_trail", []),
            }
        state: ResearchState = result
        return {
            "status": "completed",
            "session_id": session_id,
            "checkpoint": str(cp),
            "approved": state.get("approved", True),
            "verification_report": state.get("verification_report", {}),
            "final_state": state,
            "audit_trail": state.get("audit_trail", []),
        }


def run_research_graph(
    topic: str,
    model: str = "gpt-4o-mini-2024-07-18",
    provider: Optional[str] = None,
    breakpoints: Optional[List[str]] = None,
    *,
    save: bool = True,
    enable_sandbox: bool = False,
) -> Dict[str, Any]:
    """One-call entry point for the MCP tool and CLI: build a manager, register any
    breakpoints, and run one research session over the DAG."""
    manager = ResearchWorkflowManager(
        model=model, provider=provider, save=save, enable_sandbox=enable_sandbox
    )
    for stage in breakpoints or []:
        manager.add_human_breakpoint(stage)
    return manager.run(topic)
