"""Honest placeholders for capabilities that belong to Phases 2-5.

Each returns a :class:`PlaceholderAgent` that passes state through unchanged and records an
explicit 'skipped' entry naming the phase that will implement it. They keep the research DAG
shape complete (so the full pipeline runs end-to-end) without ever pretending to do work
Aurelius cannot yet do. When a phase lands, replace the corresponding factory with a real
agent module — the graph wiring in ``research_graph`` need not change.
"""
from __future__ import annotations

from .base import PlaceholderAgent

# Phase 2's sandbox_executor, result_aggregator, methodology_auditor and Phase 3's
# proof_of_rigor / living_doc_versioner are now fully implemented (see agents.execution,
# agents.verification, agents.publication). The remaining placeholders below are Phase 4-5.


def compliance_checker() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Compliance Checker", "HIPAA/GDPR/ethics screening", "Phase 2"
    )


def preprint_publisher() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Preprint Publisher", "Publish to arXiv/bioRxiv/medRxiv", "Phase 4"
    )


def patent_freedom() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Patent Freedom", "USPTO/WIPO freedom-to-operate cross-reference", "Phase 5"
    )
