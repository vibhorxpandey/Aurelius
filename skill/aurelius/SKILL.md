---
name: aurelius
description: Produce fact-checked academic research drafts using the Aurelius MCP tools. Use whenever the user asks to research a topic, write a paper/literature review, or verify claims and citations against real web sources. Screens the topic, drafts with standard academic structure, and verifies every citation and key claim before presenting it.
---

# Aurelius: fact-checked research

Aurelius turns you into a rigorous research assistant that **never presents an unverified
citation or statistic**. It provides MCP tools; you do the reasoning and drafting, and you
use the tools to ground every claim in real web sources.

## When to use
Any request to research a topic, draft a paper / literature review / research summary, or
fact-check claims and citations.

## The workflow (follow in order)

### 1. Screen the topic
Call `screen_topic(topic)`. Read the returned `policy`. Aurelius only handles topics that
can be grounded in **empirical, quantitative, web-verifiable** evidence. If the topic is
primarily interpretive/speculative (Humanities, Theoretical Physics, Qualitative Sociology),
**decline** and explain why, using the policy. Otherwise continue.

### 2. Draft
Optionally call `draft_outline(topic)` for the standard structure (Abstract, Introduction,
Methods, Results, Discussion, Conclusion, References). Write the draft yourself. Rules:
- Do **not** invent data, statistics, or citations.
- Include real, specific citations (authors, year, title) you intend to verify.

### 3. Fact-check EVERY claim (the important part)
- For each **citation**, call `verify_citation("<full citation>")`. Read the evidence.
  If `found` is false or the reputable results don't match, treat it as **unverified**.
- For each load-bearing **factual/statistical claim**, call
  `web_search("<claim as a query>", academic_only=true)` and confirm the sources agree.
- Remove or correct anything the evidence does not support. Do not rationalize a citation
  that didn't surface — drop it or replace it with one you verified.

### 4. Save and report
- Call `save_draft(content)` with the final Markdown draft.
- Call `save_report(content)` with a report whose **first line is exactly**
  `STATUS: VERIFIED` or `STATUS: REJECTED`, followed by an itemized list of every claim/
  citation you checked, the evidence, and your verdict.
- If any item failed, revise the draft (back to step 3) before finalizing.

### 5. Present
Summarize for the user: the topic verdict, what you verified, anything you removed as
unverifiable, and the saved file paths. Never claim something is verified that you did not
actually check with a tool.

## Fully autonomous alternative
If the user wants Aurelius to drive its own model end-to-end (and has set an LLM API key),
call `autonomous_research(topic, model=...)` instead of doing the steps manually. Prefer the
manual workflow above when you (the host model) are already capable — it needs no extra key.

## Requirements
- `web_search` / `verify_citation` need `TAVILY_API_KEY` in the server environment. If a tool
  returns an error about the missing key, tell the user how to set it (https://tavily.com).
