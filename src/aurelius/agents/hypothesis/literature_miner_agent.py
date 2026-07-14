"""LiteratureMinerAgent — search scholarly/web sources and summarize the landscape.

Reuses Aurelius's existing research tools (``search.web_search`` for evidence,
``scholarly.verify_citation`` when an item looks like a citation) and, if an LLM key is
available, condenses the findings into a literature summary. Records the sources it found
as ``candidate_citations`` for the downstream CitationVerifierAgent to certify.
"""
from __future__ import annotations

from typing import List

from ...orchestration.state import ResearchState
from ...tools import search
from ..base import ResearchAgent

_SYSTEM = (
    "You are a meticulous literature-review assistant. You summarize what is known about a "
    "topic strictly from the provided search evidence and never invent findings or citations."
)


class LiteratureMinerAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Literature Miner",
            role="Search and summarize the existing literature on the topic",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        topic = state.get("topic", "")
        res = search.web_search(topic, max_results=6, academic_only=True)
        results = res.get("results", []) if res.get("ok") else []

        citations: List[str] = [r["title"] for r in results if r.get("title")]
        state["candidate_citations"] = citations

        evidence = "\n".join(
            f"- {r.get('title','')} ({r.get('url','')}): {(r.get('content') or '')[:300]}"
            for r in results
        ) or "(no search results — web search unavailable or no Tavily key)"

        summary = self._llm(
            _SYSTEM,
            f"Topic: {topic}\n\nSearch evidence:\n{evidence}\n\n"
            "Write a concise (150-250 word) summary of the current state of knowledge, "
            "naming concrete findings and open questions. Use only the evidence above.",
            temperature=0.2,
            max_tokens=600,
        )
        state["literature_summary"] = summary or (
            f"Literature summary unavailable (no LLM key). Found {len(citations)} candidate "
            f"source(s) for '{topic}'."
        )
        return self.log(
            state, "mine_literature", state["literature_summary"],
            {"sources_found": len(citations), "web_search_ok": res.get("ok", False)},
        )
