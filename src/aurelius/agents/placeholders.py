"""Honest placeholders for capabilities that belong to Phases 2-5.

Each returns a :class:`PlaceholderAgent` that passes state through unchanged and records an
explicit 'skipped' entry naming the phase that will implement it. They keep the research DAG
shape complete (so the full pipeline runs end-to-end) without ever pretending to do work
Aurelius cannot yet do. When a phase lands, replace the corresponding factory with a real
agent module — the graph wiring in ``research_graph`` need not change.
"""
from __future__ import annotations

from .base import PlaceholderAgent


def sandbox_executor() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Sandbox Executor", "Execute analysis code in an isolated container", "Phase 2"
    )


def result_aggregator() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Result Aggregator", "Collect and validate sandbox results", "Phase 2"
    )


def methodology_auditor() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Methodology Auditor", "Detect p-hacking / data-dredging", "Phase 2"
    )


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


def living_doc_versioner() -> PlaceholderAgent:
    return PlaceholderAgent(
        "Living Doc Versioner", "Git/IPFS-backed versioned living document", "Phase 3"
    )
