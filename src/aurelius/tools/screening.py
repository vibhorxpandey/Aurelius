"""Topic screening: keep Aurelius pointed at evidence-grounded research.

Aurelius only produces work whose claims can be checked against empirical, quantitative,
web-verifiable sources. Interpretive or speculative domains are out of scope because the
fact-checking loop cannot certify them.

In host-driven mode the connected model makes the final call; these helpers give it the
policy and a fast keyword heuristic to lean on.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

RESTRICTED_DOMAINS: List[Dict[str, str]] = [
    {
        "name": "Humanities",
        "why": "Interpretive work (literature, philosophy, art criticism, history-as-interpretation) "
        "cannot be certified against empirical sources.",
    },
    {
        "name": "Theoretical Physics",
        "why": "Speculative theory (e.g. string theory, untested cosmology) has no empirical data to verify against.",
    },
    {
        "name": "Qualitative Sociology",
        "why": "Interpretive/ethnographic work without quantitative data cannot be fact-checked.",
    },
]

# Lightweight signals only. This is advisory; the model owns the final judgement.
_RESTRICTED_HINTS = {
    "Humanities": [
        r"\bphenomenolog", r"\bhermeneutic", r"\bexisten", r"\bliterary\b", r"\bpoetry\b",
        r"\bnovel\b", r"\bphilosoph", r"\baesthetic", r"\bmoral philosophy\b", r"\btheology\b",
        r"\bart criticism\b", r"\bliterature\b",
    ],
    "Theoretical Physics": [
        r"\bstring theory\b", r"\bmultiverse\b", r"\bquantum gravity\b", r"\bsupersymmetry\b",
        r"\bspeculative cosmolog", r"\bmetaphysic",
    ],
    "Qualitative Sociology": [
        r"\bethnograph", r"\bhermeneutic\b", r"\bphenomenological interview", r"\blived experience\b",
        r"\bnarrative inquiry\b",
    ],
}


def get_research_policy() -> Dict[str, Any]:
    """Return Aurelius's admission policy so the model can screen a topic itself."""
    return {
        "accept_if": "The topic can be investigated with empirical, quantitative, or web-verifiable "
        "evidence (economics, public health, climate science, engineering, biology, applied data analysis, etc.).",
        "reject_if": "The topic is primarily interpretive, speculative, or normative with no empirical grounding.",
        "restricted_domains": RESTRICTED_DOMAINS,
        "how_to_apply": "Classify the topic's primary domain. If it belongs to a restricted domain, decline "
        "and explain why. Otherwise proceed to drafting and fact-checking.",
    }


def screen_topic(topic: str) -> Dict[str, Any]:
    """Advisory screen of a research topic against the restricted-domain policy.

    Args:
        topic: The research topic to evaluate.

    Returns a dict with `likely_restricted` (bool), `matched_domain` (or None), the full
    `policy`, and `advice`. The connected model should make the final accept/reject
    decision using the policy — this heuristic only flags obvious cases fast.
    """
    text = topic.lower()
    matched = None
    for domain, patterns in _RESTRICTED_HINTS.items():
        if any(re.search(p, text) for p in patterns):
            matched = domain
            break

    if matched:
        advice = (
            f"Heuristic suggests this topic may fall under the restricted domain '{matched}'. "
            "Review the policy and decline if it is primarily interpretive/speculative; otherwise, "
            "if it can be grounded in empirical evidence, you may proceed."
        )
    else:
        advice = (
            "No restricted-domain keywords detected. Confirm the topic can be grounded in "
            "empirical/web-verifiable evidence, then proceed to draft and fact-check."
        )

    return {
        "topic": topic,
        "likely_restricted": matched is not None,
        "matched_domain": matched,
        "policy": get_research_policy(),
        "advice": advice,
    }
