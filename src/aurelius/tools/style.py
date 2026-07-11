"""Prose-quality polishing for already fact-checked content.

This is a style pass for readability, NOT a tool for evading AI-content detectors.
It must run strictly after fact-checking, on already-verified content, and must never
alter a citation, number, or factual claim — only sentence-level phrasing. Pairing an
"AI humanizer" with long-form academic paper generation would enable passing
AI-written research off as human-written for submission; that is out of scope for
Aurelius by design, whose entire premise is showing verifiable receipts, not hiding
provenance.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import get_llm_key
from ..autonomous.llm import complete, detect_provider

PROSE_GUIDELINES = [
    "Vary sentence length and structure; avoid runs of same-length, same-shape sentences.",
    "Cut repetitive transition-word stacking ('Furthermore,' 'Moreover,' 'Additionally,' back to back).",
    "Prefer active voice and concrete verbs over nominalizations ('the analysis demonstrates' -> 'shows').",
    "Remove formulaic hedging chains ('It is important to note that it could be argued that...').",
    "Avoid tricolon padding ('robust, comprehensive, and rigorous') used as filler rather than meaning.",
    "Vary paragraph rhythm: not every paragraph needs a topic sentence plus three supporting sentences.",
    "Trim throat-clearing openers ('In today's world,' 'It goes without saying that').",
    "Keep terminology consistent for the SAME concept; vary only incidental phrasing, not technical terms.",
    "MUST preserve verbatim: every citation, number, statistic, date, proper noun, and factual claim.",
    "Do not add, remove, or soften any claim's substance -- this is a phrasing pass only.",
]

CHECKLIST = [
    "Every number/statistic in the rewrite matches the original exactly.",
    "Every citation (author/year/title) in the rewrite matches the original exactly.",
    "No new claims were introduced; no claims were softened or dropped.",
]

_SYSTEM_PROMPT = (
    "You improve prose style and readability of ALREADY FACT-CHECKED academic writing. "
    "You NEVER change a citation, number, statistic, date, or factual claim -- you only vary "
    "sentence structure, cut repetitive phrasing, and improve rhythm. If you are unsure whether "
    "a change would alter meaning, leave the sentence as-is."
)


def polish_prose(
    content: str,
    use_llm: bool = False,
    model: str = "gpt-4o-mini-2024-07-18",
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Return style guidelines for improving `content`'s prose, applied only AFTER
    fact-checking. Optionally applies them itself via a BYO-key LLM call.

    Default (use_llm=False, recommended): returns guidelines + a preservation checklist
    for YOU (the host model, already loaded with full document context) to apply.
    Optional (use_llm=True): Aurelius rewrites it itself via a configured LLM key,
    falling back to guidelines-only if no key is set or the call fails -- never raises.

    Args:
        content: The already-verified draft text to polish.
        use_llm: If True, attempt an LLM rewrite instead of returning guidelines only.
        model: Model to use for the optional LLM rewrite.
        provider: Force a provider ('openai'|'anthropic'|'google'); auto-detected from
            `model` if omitted.

    Returns {"ok": True, "mode": "guidelines"|"llm_rewrite", "guidelines": [...],
             "checklist": [...], "rewritten": str|None, "notes": str}
    """
    if not use_llm:
        return {
            "ok": True,
            "mode": "guidelines",
            "guidelines": PROSE_GUIDELINES,
            "checklist": CHECKLIST,
            "rewritten": None,
            "notes": "Apply these guidelines to `content` yourself, then check the checklist "
                     "before saving. No LLM call was made (use_llm=False).",
        }

    resolved_provider = (provider or detect_provider(model)).lower()
    key = get_llm_key(resolved_provider)
    if not key:
        return {
            "ok": True,
            "mode": "guidelines",
            "guidelines": PROSE_GUIDELINES,
            "checklist": CHECKLIST,
            "rewritten": None,
            "notes": f"use_llm=True but no API key found for provider '{resolved_provider}'; "
                     "falling back to guidelines-only. Set the provider's key, or apply the "
                     "guidelines yourself.",
        }

    user_prompt = (
        "Rewrite the prose below applying these guidelines:\n"
        + "\n".join(f"- {g}" for g in PROSE_GUIDELINES)
        + f"\n\n=== CONTENT ===\n{content}\n=== END CONTENT ===\n\nReturn ONLY the rewritten text."
    )
    try:
        rewritten = complete(
            _SYSTEM_PROMPT, user_prompt, model, resolved_provider, key,
            temperature=0.4, max_tokens=8192,
        )
    except Exception as e:  # noqa: BLE001 - never let a style pass crash the caller
        return {
            "ok": True,
            "mode": "guidelines",
            "guidelines": PROSE_GUIDELINES,
            "checklist": CHECKLIST,
            "rewritten": None,
            "notes": f"LLM call failed ({type(e).__name__}: {e}); falling back to guidelines-only.",
        }

    return {
        "ok": True,
        "mode": "llm_rewrite",
        "guidelines": PROSE_GUIDELINES,
        "checklist": CHECKLIST,
        "rewritten": rewritten,
        "notes": "Verify the checklist against `rewritten` before saving -- an LLM rewrite can "
                 "still drift on numbers/citations despite instructions.",
    }
