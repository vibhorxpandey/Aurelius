"""Verification agents (Stages 4-5).

CitationVerifier reuses the existing retraction-aware ledger; MethodologyAuditor runs the
static p-hacking/data-dredging checks; AdversarialReviewer plays hostile peer reviewer."""
from .citation_verifier_agent import CitationVerifierAgent
from .methodology_auditor_agent import MethodologyAuditorAgent
from .adversarial_reviewer_agent import AdversarialReviewerAgent

__all__ = ["CitationVerifierAgent", "MethodologyAuditorAgent", "AdversarialReviewerAgent"]
