"""Multilingual literature synthesis (Phase 6).

Searches the global literature across languages using OpenAlex's language filter — keyless
and real (OpenAlex indexes CNKI-/Wanfang-adjacent scholarship with DOIs, plus Spanish,
German, Japanese, etc. venues). When an LLM key is configured, the query is translated into
each target language first for much better recall; without one, the original query is used
as-is (OpenAlex matches English-language titles/abstracts of foreign-language works, so
results still surface — just fewer).

The paywalled Chinese databases themselves (CNKI, Wanfang) have no public APIs; OpenAlex's
open index is the honest, reproducible proxy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from ..autonomous import llm

OPENALEX_URL = "https://api.openalex.org/works"

LANGUAGE_NAMES = {
    "zh": "Chinese", "es": "Spanish", "de": "German", "ja": "Japanese", "fr": "French",
    "pt": "Portuguese", "ru": "Russian", "ko": "Korean", "ar": "Arabic", "hi": "Hindi",
}

DEFAULT_LANGUAGES = ["zh", "es", "de", "ja"]


def _translate(query: str, lang: str, model: str, provider: Optional[str]) -> str:
    """Translate the query for better native-language recall; fall back to the original."""
    name = LANGUAGE_NAMES.get(lang, lang)
    try:
        out = llm.complete(
            "You translate academic search queries precisely. Reply with ONLY the translation.",
            f"Translate this scholarly search query into {name}: {query}",
            model, provider, temperature=0.0, max_tokens=120,
        )
        return (out or "").strip() or query
    except llm.LLMError:
        return query


def _openalex_search(query: str, lang: str, per_lang: int) -> List[Dict[str, Any]]:
    params = {
        "search": query,
        "filter": f"language:{lang}",
        "per-page": max(1, min(int(per_lang), 10)),
        "select": "display_name,publication_year,doi,language,cited_by_count",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(OPENALEX_URL, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    return [
        {
            "title": w.get("display_name"),
            "year": w.get("publication_year"),
            "doi": w.get("doi"),
            "language": w.get("language"),
            "cited_by_count": w.get("cited_by_count"),
        }
        for w in data.get("results", [])
    ]


def multilingual_search(
    query: str,
    languages: Optional[List[str]] = None,
    per_lang: int = 3,
    model: str = "gpt-4o-mini-2024-07-18",
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Search the scholarly literature across languages via OpenAlex (keyless).

    Args:
        query: The research question/topic (any language).
        languages: ISO 639-1 codes to cover (default: zh, es, de, ja).
        per_lang: Results per language (1-10).
        model/provider: Used only for query translation when an LLM key is configured;
            otherwise the untranslated query is used (still returns results).

    Returns {"ok", "query", "translated": bool, "by_language": {lang: {"query", "results"}},
             "total_results", "note"}.
    """
    langs = [l for l in (languages or DEFAULT_LANGUAGES) if l] or DEFAULT_LANGUAGES
    by_language: Dict[str, Any] = {}
    translated_any = False
    total = 0

    for lang in langs:
        q = _translate(query, lang, model, provider)
        if q != query:
            translated_any = True
        results = _openalex_search(q, lang, per_lang)
        by_language[lang] = {"query": q, "results": results}
        total += len(results)

    note = (
        f"Searched {len(langs)} language(s) via OpenAlex"
        + ("" if translated_any else
           " (queries untranslated - set an LLM key for native-language recall)")
        + "."
    )
    return {"ok": True, "query": query, "translated": translated_any,
            "by_language": by_language, "total_results": total, "note": note}
