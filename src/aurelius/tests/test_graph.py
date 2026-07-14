"""Engine tests — pure Python, no LLM key or network needed."""
from __future__ import annotations

import json

from aurelius.orchestration.graph import Graph, Paused
from aurelius.orchestration.state import new_state, record


def _node(name):
    def fn(state):
        record(state, name, "ran")
        state.setdefault("visited", []).append(name)
        return state
    return fn


def _linear_graph():
    g = Graph()
    for n in ("a", "b", "c"):
        g.add_node(n, _node(n))
    g.add_edge("a", "b").add_edge("b", "c")
    g.set_entry("a").set_finish("c")
    return g


def test_linear_order_and_audit_trail():
    g = _linear_graph()
    state = g.invoke(new_state("t"))
    assert state["visited"] == ["a", "b", "c"]
    # one audit entry per node
    agents = [e["agent"] for e in state["audit_trail"]]
    assert agents == ["a", "b", "c"]


def test_checkpoint_written(tmp_path):
    g = _linear_graph()
    cp = tmp_path / "s.json"
    g.invoke(new_state("t"), checkpoint_path=cp)
    assert cp.exists()
    data = json.loads(cp.read_text(encoding="utf-8"))
    assert data["completed_node"] == "c"
    assert data["next_node"] is None
    assert data["state"]["visited"] == ["a", "b", "c"]


def test_conditional_edge_routes():
    g = Graph()
    for n in ("start", "left", "right"):
        g.add_node(n, _node(n))
    g.add_conditional_edge("start", lambda s: "right" if s.get("go_right") else "left")
    g.set_entry("start").set_finish("left")  # finish is nominal; both branches end themselves
    g.add_edge("right", "left")
    out = g.invoke(new_state("t"))  # go_right unset -> left
    assert out["visited"] == ["start", "left"]


def test_breakpoint_pauses_and_resumes(tmp_path):
    g = _linear_graph()
    cp = tmp_path / "s.json"
    paused = g.invoke(new_state("t"), checkpoint_path=cp, breakpoints=frozenset({"b"}))
    assert isinstance(paused, Paused)
    assert paused.next_node == "b"
    assert paused.state["visited"] == ["a"]  # b not yet executed

    final = g.resume(cp, approval=True, breakpoints=frozenset({"b"}))
    assert not isinstance(final, Paused)
    assert final["visited"] == ["a", "b", "c"]


def test_breakpoint_rejection_stops(tmp_path):
    g = _linear_graph()
    cp = tmp_path / "s.json"
    g.invoke(new_state("t"), checkpoint_path=cp, breakpoints=frozenset({"b"}))
    stopped = g.resume(cp, approval=False, breakpoints=frozenset({"b"}))
    assert stopped["visited"] == ["a"]  # never proceeded past the breakpoint
