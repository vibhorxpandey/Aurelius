"""Honest placeholders for capabilities deliberately not (yet) implemented.

Each returns a :class:`PlaceholderAgent` that passes state through unchanged and records an
explicit 'skipped' entry. After Phases 1-6 only one in-graph placeholder remains:

* ``compliance_checker`` — HIPAA/GDPR/IRB screening needs domain-specific legal rulesets;
  a regex heuristic would give false confidence on exactly the questions where being wrong
  is most costly.

Decentralized-funding integration (the other Phase 5 bullet) is deliberately **out of
scope**, not merely unimplemented: there is no standard DeSci funding protocol to integrate
against, and Aurelius's value is the verification/trust layer, not fund-raising plumbing.
"""
from __future__ import annotations

from .base import PlaceholderAgent


def compliance_checker() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Compliance Checker", "HIPAA/GDPR/ethics screening", "future work"
    )
