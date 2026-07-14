"""A minimal, dependency-free DAG engine — the in-house replacement for LangGraph.

Design goals (Phase 1):
  * Nodes are plain ``Callable[[state], state]`` — an agent's ``execute`` or any function.
  * Linear edges plus optional conditional routers (``state -> next_node_name``).
  * Human-in-the-loop **breakpoints**: the graph pauses *before* a named node and returns a
    :class:`Paused` handle so a human can inspect/approve the node's input, then ``resume``.
  * **Checkpointing**: after every node the full state is written to a JSON file, so a
    session can be resumed after a crash or a breakpoint.

No external dependencies: the whole engine is standard-library only, keeping Aurelius's
install to ``mcp`` + ``httpx``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, FrozenSet, Optional, Union

from .state import ResearchState, record

Node = Callable[[ResearchState], ResearchState]
Router = Callable[[ResearchState], Optional[str]]


class Paused:
    """Returned by :meth:`Graph.invoke` when execution stops at a breakpoint.

    ``next_node`` is the not-yet-executed node awaiting approval. Call
    :meth:`Graph.resume` with the checkpoint path to continue.
    """

    def __init__(self, state: ResearchState, next_node: str, checkpoint_path: Optional[str]):
        self.state = state
        self.next_node = next_node
        self.checkpoint_path = checkpoint_path

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Paused(next_node={self.next_node!r})"


class GraphError(RuntimeError):
    pass


class Graph:
    """A small directed graph of state-transforming nodes."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, str] = {}
        self.conditional: Dict[str, Router] = {}
        self.entry: Optional[str] = None
        self.finish: Optional[str] = None

    # --- construction ----------------------------------------------------------
    def add_node(self, name: str, fn: Node) -> "Graph":
        if name in self.nodes:
            raise GraphError(f"Duplicate node: {name}")
        self.nodes[name] = fn
        return self

    def add_edge(self, src: str, dst: str) -> "Graph":
        self.edges[src] = dst
        return self

    def add_conditional_edge(self, src: str, router: Router) -> "Graph":
        """Register a router that decides the next node from state (returns a node name
        or ``None`` to finish). Takes precedence over a plain edge from the same node."""
        self.conditional[src] = router
        return self

    def set_entry(self, name: str) -> "Graph":
        self.entry = name
        return self

    def set_finish(self, name: str) -> "Graph":
        self.finish = name
        return self

    # --- execution -------------------------------------------------------------
    def _next(self, current: str, state: ResearchState) -> Optional[str]:
        if current in self.conditional:
            return self.conditional[current](state)
        return self.edges.get(current)

    def invoke(
        self,
        state: ResearchState,
        *,
        checkpoint_path: Optional[Union[str, Path]] = None,
        breakpoints: FrozenSet[str] = frozenset(),
        _start: Optional[str] = None,
    ) -> Union[ResearchState, Paused]:
        """Walk the graph from entry (or ``_start``) to finish.

        Returns the final state, or a :class:`Paused` handle if a breakpoint is reached.
        """
        if self.entry is None:
            raise GraphError("No entry node set.")
        cp = str(checkpoint_path) if checkpoint_path else None
        current: Optional[str] = _start or self.entry

        while current is not None:
            if current not in self.nodes:
                raise GraphError(f"Unknown node: {current}")

            # Pause *before* a breakpoint node unless it was already approved on resume.
            approved_flag = f"_approved_{current}"
            if current in breakpoints and not state.get(approved_flag):
                record(state, "graph", "breakpoint", current, {"node": current})
                _write_checkpoint(cp, state, completed=None, next_node=current)
                return Paused(state, current, cp)

            state = self.nodes[current](state)
            next_node = None if current == self.finish else self._next(current, state)
            _write_checkpoint(cp, state, completed=current, next_node=next_node)
            current = next_node

        return state

    def resume(
        self,
        checkpoint_path: Union[str, Path],
        *,
        approval: bool = True,
        breakpoints: FrozenSet[str] = frozenset(),
    ) -> Union[ResearchState, Paused]:
        """Resume a session from its checkpoint file.

        If the checkpoint paused at a breakpoint and ``approval`` is True, the pending node
        is marked approved and executed; if ``approval`` is False the session stops there.
        """
        data = json.loads(Path(checkpoint_path).read_text(encoding="utf-8"))
        state: ResearchState = data["state"]
        start = data.get("next_node")
        if start is None:
            return state  # already finished
        if start in breakpoints:
            if not approval:
                record(state, "graph", "breakpoint_rejected", start, {"node": start})
                _write_checkpoint(str(checkpoint_path), state, completed=None, next_node=None)
                return state
            state[f"_approved_{start}"] = True  # type: ignore[literal-required]
        return self.invoke(
            state, checkpoint_path=checkpoint_path, breakpoints=breakpoints, _start=start
        )


def _write_checkpoint(
    path: Optional[str],
    state: ResearchState,
    *,
    completed: Optional[str],
    next_node: Optional[str],
) -> None:
    """Persist a resumable snapshot. Best-effort: never let checkpointing crash a run."""
    if not path:
        return
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"completed_node": completed, "next_node": next_node, "state": state}
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass
