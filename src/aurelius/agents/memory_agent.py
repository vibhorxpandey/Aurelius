"""EpisodicMemoryAgent — the swarm's long-term memory (Phase 6).

Two modes, wired as the first and last nodes of the research graph:
  * ``recall``: before literature mining, fetch past episodes relevant to the topic and put
    their lessons in ``state['memory_recall']`` so downstream agents (and the model reading
    the state) can avoid repeating failures.
  * ``record``: after everything else (including rejected runs — failures are the most
    valuable lessons), append this run's outcome to the episode store.
"""
from __future__ import annotations

from ..memory import episodic
from ..orchestration.state import ResearchState
from .base import ResearchAgent


class EpisodicMemoryAgent(ResearchAgent):
    def __init__(self, mode: str = "recall", **kwargs) -> None:
        if mode not in ("recall", "record"):
            raise ValueError(f"mode must be 'recall' or 'record', got {mode!r}")
        super().__init__(
            name="Episodic Memory",
            role=("Recall lessons from past research sessions" if mode == "recall"
                  else "Record this session's outcome for future runs"),
            **kwargs,
        )
        self.mode = mode

    def execute(self, state: ResearchState) -> ResearchState:
        if self.mode == "recall":
            episodes = episodic.recall_episodes(state.get("topic", ""), k=3)
            state["memory_recall"] = episodes
            lessons = [l for ep in episodes for l in ep.get("lessons", [])]
            summary = (f"{len(episodes)} relevant past session(s); lessons: "
                       + ("; ".join(lessons[:3]) if lessons else "none recorded")
                       ) if episodes else "No relevant past sessions."
            return self.log(state, "recall_memory", summary, {"episodes": len(episodes)})

        episode = episodic.record_episode(state)
        return self.log(state, "record_memory",
                        f"Episode recorded ({len(episode['lessons'])} lesson(s)).",
                        {"session_id": episode["session_id"], "lessons": episode["lessons"]})
