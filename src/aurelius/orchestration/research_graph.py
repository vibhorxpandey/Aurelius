"""Assemble the Phase-1 research DAG from agent nodes.

Stage order follows ARCHITECTURE.md §1.1, adapted so data dependencies are respected:
literature mining runs *before* the parallel hypothesis swarm (theory + pattern discovery),
which both consume the literature summary. A conditional edge after screening routes a
rejected hypothesis straight to the proof-of-rigor/finish stage instead of drafting.

Nodes are agent instances (each is ``Callable[[state], state]``) plus one swarm node and one
router. Later-phase stages are honest placeholders from :mod:`agents.placeholders`.
"""
from __future__ import annotations

from typing import List, Optional

from ..agents import placeholders
from ..agents.execution import (
    CodeGeneratorAgent,
    ExperimentDesignerAgent,
    ResultAggregatorAgent,
    SandboxExecutorAgent,
)
from ..agents.hypothesis import (
    HypothesisValidatorAgent,
    LiteratureMinerAgent,
    PatternDiscoveryAgent,
    TheoryGeneratorAgent,
)
from ..agents.publication import (
    DraftPaperAgent,
    LatexFormatterAgent,
    LivingDocVersionerAgent,
    ProofOfRigorAgent,
)
from ..agents.verification import (
    AdversarialReviewerAgent,
    CitationVerifierAgent,
    MethodologyAuditorAgent,
)
from .graph import Graph
from .state import ResearchState
from .swarm import AgentSwarmCoordinator

# Public, ordered list of stage (node) names — handy for tests, docs, and breakpoints.
STAGES: List[str] = [
    "mine_literature",
    "generate_hypotheses",
    "screen_hypotheses",
    "design_experiment",
    "generate_code",
    "execute_sandbox",
    "aggregate_results",
    "audit_methodology",
    "verify_citations",
    "check_compliance",
    "adversarial_review",
    "draft_paper",
    "format_latex",
    "proof_of_rigor",
    "publish_preprints",
    "update_living_doc",
    "patent_freedom",
]


def build_research_graph(
    model: str = "gpt-4o-mini-2024-07-18",
    provider: Optional[str] = None,
    *,
    save: bool = True,
    enable_sandbox: bool = False,
) -> Graph:
    """Construct the compiled research DAG. ``model``/``provider`` are threaded to every
    LLM-backed agent; ``save`` controls whether the draft is written to disk;
    ``enable_sandbox`` opts into real Docker execution of the generated analysis code."""
    kw = {"model": model, "provider": provider}

    # Stage 1: literature (solo) -> hypothesis swarm (parallel) -> screen.
    swarm = AgentSwarmCoordinator()
    theory = TheoryGeneratorAgent(**kw)
    pattern = PatternDiscoveryAgent(**kw)

    def generate_hypotheses(state: ResearchState) -> ResearchState:
        return swarm.run_parallel(state, [theory, pattern])

    g = Graph()
    g.add_node("mine_literature", LiteratureMinerAgent(**kw))
    g.add_node("generate_hypotheses", generate_hypotheses)
    g.add_node("screen_hypotheses", HypothesisValidatorAgent(**kw))
    g.add_node("design_experiment", ExperimentDesignerAgent(**kw))
    g.add_node("generate_code", CodeGeneratorAgent(**kw))
    g.add_node("execute_sandbox", SandboxExecutorAgent(enable=enable_sandbox, **kw))
    g.add_node("aggregate_results", ResultAggregatorAgent(**kw))
    g.add_node("audit_methodology", MethodologyAuditorAgent(**kw))
    g.add_node("verify_citations", CitationVerifierAgent(**kw))
    g.add_node("check_compliance", placeholders.compliance_checker())
    g.add_node("adversarial_review", AdversarialReviewerAgent(**kw))
    g.add_node("draft_paper", DraftPaperAgent(save=save, **kw))
    g.add_node("format_latex", LatexFormatterAgent(**kw))
    g.add_node("proof_of_rigor", ProofOfRigorAgent(**kw))
    g.add_node("publish_preprints", placeholders.preprint_publisher())
    g.add_node("update_living_doc", LivingDocVersionerAgent(**kw))
    g.add_node("patent_freedom", placeholders.patent_freedom())

    # Linear edges for the happy path.
    linear = [
        ("mine_literature", "generate_hypotheses"),
        ("generate_hypotheses", "screen_hypotheses"),
        ("design_experiment", "generate_code"),
        ("generate_code", "execute_sandbox"),
        ("execute_sandbox", "aggregate_results"),
        ("aggregate_results", "audit_methodology"),
        ("audit_methodology", "verify_citations"),
        ("verify_citations", "check_compliance"),
        ("check_compliance", "adversarial_review"),
        ("adversarial_review", "draft_paper"),
        ("draft_paper", "format_latex"),
        ("format_latex", "proof_of_rigor"),
        ("proof_of_rigor", "publish_preprints"),
        ("publish_preprints", "update_living_doc"),
        ("update_living_doc", "patent_freedom"),
    ]
    for src, dst in linear:
        g.add_edge(src, dst)

    # Conditional: a rejected hypothesis skips experiment/drafting and jumps to attestation.
    def after_screen(state: ResearchState) -> str:
        return "design_experiment" if state.get("approved", True) else "proof_of_rigor"

    g.add_conditional_edge("screen_hypotheses", after_screen)

    g.set_entry("mine_literature")
    g.set_finish("patent_freedom")
    return g
