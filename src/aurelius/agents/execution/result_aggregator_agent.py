"""ResultAggregatorAgent — normalize the sandbox output into a compact result summary.

Lightweight by design: it condenses the raw container stdout/stderr/exit status into a
short, state-friendly summary (and optionally an LLM interpretation) so downstream agents
(drafting, proof-of-rigor) can reference the execution outcome without carrying kilobytes
of logs.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ..base import ResearchAgent

_SYSTEM = "You concisely interpret the output of a data-analysis script for a research write-up."


class ResultAggregatorAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Result Aggregator",
            role="Summarize and validate the sandbox execution result",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        result = state.get("sandbox_result", {}) or {}
        if not result.get("ran"):
            return self.log(state, "skipped", "No sandbox result to aggregate.", {})

        stdout = (result.get("stdout") or "").strip()
        status = "success" if result.get("ok") else ("timeout" if result.get("timed_out") else "error")
        interpretation = self._llm(
            _SYSTEM,
            f"The analysis script finished with status '{status}'. Output:\n{stdout[:2000]}\n\n"
            "In 2-3 sentences, summarize what the script computed and whether it produced a "
            "usable result. Do not invent numbers not present in the output.",
            temperature=0.2, max_tokens=300,
        )
        state.setdefault("sandbox_result", {})["summary"] = interpretation or (
            f"Execution {status}; {len(stdout.splitlines())} line(s) of output."
        )
        return self.log(state, "aggregate_results", state["sandbox_result"]["summary"], {"status": status})
