---
name: aurelius
description: Produce fact-checked academic research drafts using the Aurelius MCP tools. Use whenever the user asks to research a topic, write a paper/literature review/long-form report, generate a LaTeX document, draw an architecture or flowchart diagram, or verify claims and citations against real scholarly sources. Screens the topic, drafts with standard academic structure, and verifies every citation and key claim (retraction-aware, via OpenAlex/Crossref) before presenting it.
---

# Aurelius: fact-checked research

Aurelius turns you into a rigorous research assistant that **never presents an unverified
citation or statistic**. It provides MCP tools; you do the reasoning and drafting, and you
use the tools to ground every claim in real scholarly and web sources.

## When to use
Any request to research a topic, draft a paper / literature review / long-form report,
write a LaTeX document, generate an architecture/flowchart/sequence diagram, or fact-check
claims and citations.

## The workflow (follow in order)

### 1. Screen the topic
Call `screen_topic(topic)`. Read the returned `policy`. Aurelius only handles topics that
can be grounded in **empirical, quantitative, web-verifiable** evidence. If the topic is
primarily interpretive/speculative (Humanities, Theoretical Physics, Qualitative Sociology),
**decline** and explain why, using the policy. Otherwise continue.

### 2. Plan (long-form papers only)
If the user wants a long paper (roughly 20+ pages), call `plan_paper_length(target_pages=...)`
first. It returns a section-by-section word-count budget (no LLM call — pure arithmetic).
Use it to pace yourself: draft one section at a time rather than attempting the whole
document in a single response.

### 3. Draft
Optionally call `draft_outline(topic)` for the standard Markdown structure (Abstract,
Introduction, Methods, Results, Discussion, Conclusion, References), or `latex_outline(topic)`
if the user wants a LaTeX/.tex deliverable. Write the draft yourself. Rules:
- Do **not** invent data, statistics, or citations.
- Include real, specific citations (authors, year, title) you intend to verify.
- For long-form papers: draft one section, verify it (step 4), append it (step 6), then
  move to the next section — never hold the whole accumulated draft in one response.

### 4. Fact-check EVERY claim (the important part)
- The easiest way: collect every citation and load-bearing claim from the section you just
  wrote into a list and call `verify_claims([...])` once — it auto-routes citations to
  scholarly verification and factual claims to web search, and returns a scored ledger plus
  a ready-to-save report. For a complete References list, call `verify_bibliography(text)`.
- Or check items individually: `verify_citation("<full citation>")` for each citation
  (checked against OpenAlex, Crossref, arXiv, and Semantic Scholar — DOI-precise when the
  citation carries a DOI/arXiv id — and it recovers the real DOI/authors/venue).
- **`is_retracted: true` is an automatic reject, full stop** — regardless of how well-cited
  or plausible the paper otherwise looks. Never cite a retracted work.
- **`author_match: false` means it is probably NOT the paper you cited** — a same-titled work
  by different authors. Treat that as unverified. `verify_citation` returns a
  `corrected_citation` (and `bibtex`) built from authoritative metadata — prefer it, or fix
  the citation, rather than keeping a mis-attributed one.
- For **numeric/statistical claims** (e.g. "US GDP grew 2.5% in 2023"), call
  `verify_stat(claim, country=..., year=..., claimed_value=...)` — it checks the number
  against World Bank data and returns verified / contradicted / unverified with the actual value.
- Remove or correct anything the evidence does not support. Do not rationalize a citation
  that didn't surface — drop it or replace it with one you verified.

### 5. Optional: polish prose (after fact-checking only)
Once a section/draft is fully verified, you may call `polish_prose(content)` for style
guidelines to apply yourself (default, no LLM call), or `polish_prose(content, use_llm=True)`
to have Aurelius rewrite it via a configured LLM key. This is a **readability pass only** —
run the returned `checklist` against the result to confirm every citation, number, and claim
survived verbatim. Never use this to obscure that content is AI-assisted; it exists to fix
stiff, repetitive phrasing, not to evade AI-detection tools.

### 6. Diagrams (as needed)
When a flowchart, architecture, or sequence diagram would help, call
`diagram_template(diagram_type, description)` and complete the returned Mermaid scaffold.
Embed it as a ` ```mermaid ` fenced code block in the Markdown draft — GitHub, Claude, and
most Markdown viewers render it inline.

### 7. Save and report
- Markdown: call `save_draft(content, filename)`. For long-form papers, call it once per
  section with `append=True` (after the first call) so you never resend the whole
  accumulated document — check the returned `bytes` (total file size) against your
  `plan_paper_length` budget to track progress.
- LaTeX: call `save_latex(content, "paper.tex")` for the document and again with a `.bib`
  filename for the bibliography.
- Call `save_report(content)` — or just pass `verify_claims(...)`'s `markdown` field
  straight through — with a report whose **first line is exactly** `STATUS: VERIFIED` or
  `STATUS: REJECTED`, followed by an itemized list of every claim/citation checked.
- If any item failed, revise the draft (back to step 4) before finalizing.

### 8. Present
Summarize for the user: the topic verdict, what you verified (and anything you removed as
unverifiable or retracted), and the saved file paths. Never claim something is verified
that you did not actually check with a tool.

## Fully autonomous alternative
If the user wants Aurelius to drive its own model end-to-end (and has set an LLM API key),
call `autonomous_research(topic, model=...)` instead of doing the steps manually. Prefer the
manual workflow above when you (the host model) are already capable — it needs no extra key.
Note: autonomous mode does not currently support the long-form (20-80 page) workflow —
that's host-driven only, per step 2-3 above.

## Requirements
- `verify_citation` / `verify_claims` check OpenAlex and Crossref first — **no key needed**
  for that path. They fall back to Tavily web search only when a work isn't indexed there,
  so `TAVILY_API_KEY` is optional (needed for `web_search` and the fallback path). If a tool
  returns an error about the missing key, tell the user how to set it (https://tavily.com).
- `polish_prose`'s `use_llm=True` mode and `autonomous_research` need an LLM key
  (OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY) — everything else needs none.
