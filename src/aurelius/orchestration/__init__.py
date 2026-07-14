"""Aurelius orchestration layer (Phase 1): a lightweight, dependency-free DAG engine plus
the research graph, agent swarm coordinator, and workflow manager.

This package ``__init__`` intentionally imports only the leaf modules (``state``, ``graph``)
that have no dependency on :mod:`aurelius.agents`. The higher-level modules — ``swarm``,
``research_graph``, ``workflow_manager`` — pull in the agents (which in turn import
``orchestration.state``), so importing them here would create a partial-import cycle. Import
those from their submodules directly, e.g.::

    from aurelius.orchestration.workflow_manager import ResearchWorkflowManager
"""
from .graph import Graph, GraphError, Paused
from .state import ResearchState, new_state, new_session_id, record

__all__ = [
    "Graph",
    "GraphError",
    "Paused",
    "ResearchState",
    "new_state",
    "new_session_id",
    "record",
]
