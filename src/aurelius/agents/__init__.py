"""Aurelius research agents (Phase 1).

Each agent is a ``Callable[[state], state]`` subclass of :class:`base.ResearchAgent`, so an
agent instance can be dropped directly into the DAG as a node. Load-bearing agents are fully
implemented; later-phase stages are honest placeholders (see :mod:`agents.placeholders`).
"""
from .base import PlaceholderAgent, ResearchAgent

__all__ = ["ResearchAgent", "PlaceholderAgent"]
