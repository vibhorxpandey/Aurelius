"""Episodic memory (Phase 6): remember past research sessions, learn from outcomes.

Every completed run is recorded as an *episode* — topic, hypothesis, verification score,
methodology risk, approval/verification outcome, and derived one-line *lessons* — in an
append-only JSONL store (`<output_dir>/memory/episodes.jsonl`). At the start of a new run,
``recall_episodes`` surfaces the most relevant past episodes by token overlap (deliberately
no embedding dependency), so the swarm can avoid repeating failures and build on successes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from ..config import get_output_dir
from ..orchestration.state import ResearchState, now_iso

_STOPWORDS = {"a", "an", "the", "of", "in", "on", "for", "and", "to", "is", "with", "effect",
              "impact", "study", "between", "does", "how"}


def _store_path() -> Path:
    return get_output_dir() / "memory" / "episodes.jsonl"


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOPWORDS}


def _derive_lessons(state: ResearchState) -> List[str]:
    """Turn a run's outcome into short, reusable lessons."""
    lessons: List[str] = []
    if not state.get("approved", True):
        lessons.append(f"Topic rejected at screening: {state.get('screen_reason', 'policy')}")
    vr = state.get("verification_report", {}) or {}
    score = vr.get("verification_score")
    counts = vr.get("counts") or {}
    if score is not None:
        if counts.get("retracted"):
            lessons.append(f"{counts['retracted']} retracted source(s) surfaced - re-verify "
                           "this literature area carefully.")
        if score < 0.5 and counts.get("total"):
            lessons.append("Most claims failed verification - sources in this area are thin; "
                           "mine literature more broadly before hypothesizing.")
        elif score == 1.0 and counts.get("total"):
            lessons.append("All claims verified - the mined sources for this area are reliable.")
    mr = state.get("methodology_report", {}) or {}
    if mr.get("risk") == "high":
        lessons.append("Methodology risk was HIGH: " +
                       ", ".join(f.get("signal", "") for f in mr.get("findings", [])[:3]))
    return lessons


def record_episode(state: ResearchState) -> Dict[str, Any]:
    """Append this run's episode to the store and return it."""
    vr = state.get("verification_report", {}) or {}
    episode = {
        "ts": now_iso(),
        "session_id": state.get("session_id", ""),
        "topic": state.get("topic", ""),
        "hypothesis": state.get("hypothesis", ""),
        "approved": state.get("approved", True),
        "verification_score": vr.get("verification_score"),
        "methodology_risk": (state.get("methodology_report", {}) or {}).get("risk"),
        "proof_content_hash": (state.get("proof", {}) or {}).get("content_hash"),
        "lessons": _derive_lessons(state),
    }
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(episode, default=str) + "\n")
    return episode


def recall_episodes(topic: str, k: int = 3) -> List[Dict[str, Any]]:
    """Return up to `k` past episodes most relevant to `topic` (token-overlap ranking)."""
    path = _store_path()
    if not path.exists():
        return []
    query = _tokens(topic)
    if not query:
        return []

    scored: List[tuple] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            ep = json.loads(line)
        except ValueError:
            continue
        overlap = len(query & _tokens(ep.get("topic", "") + " " + ep.get("hypothesis", "")))
        if overlap > 0:
            scored.append((overlap, ep.get("ts", ""), ep))

    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [ep for _, _, ep in scored[: max(1, int(k))]]
