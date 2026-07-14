<p align="center">
  <img src="assets/aurelius-banner.jpg" alt="Aurelius — a fact-checked research MCP server" width="100%">
</p>

# Aurelius

[![PyPI version](https://img.shields.io/pypi/v/aurelius-mcp.svg)](https://pypi.org/project/aurelius-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/aurelius-mcp.svg)](https://pypi.org/project/aurelius-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-server-blue.svg)](https://modelcontextprotocol.io)

**A fact-checked research MCP server.** Aurelius gives any MCP-capable app — Claude
(Desktop / Code / claude.ai), Gemini CLI, Cursor, and (via a remote deployment) ChatGPT —
a set of research tools that **verify every citation against real scholarly databases**
(OpenAlex, Crossref — DOI-backed and retraction-aware) **and every claim against live web
sources** before presenting it. No more hallucinated papers, no more silently-cited
retracted studies.

Aurelius grew out of a multi-agent research framework and distills its best idea into a
portable tool server: **screen a topic → draft → fact-check → revise**.

---

## Why this design solves the "API cost" problem

By default Aurelius runs in **host-driven mode**: the app you connect it to (Claude, Gemini,
etc.) uses *its own* model to reason and write, and Aurelius just supplies the research and
fact-checking tools. That means **Aurelius needs no LLM API key of its own** — the tokens are
covered by your existing Claude/Gemini/ChatGPT subscription. Citation verification runs
against [OpenAlex](https://openalex.org) and [Crossref](https://www.crossref.org) — both
free, both keyless. The only optional key is [Tavily](https://tavily.com), used for general
`web_search` and as a fallback when a citation isn't indexed in either scholarly database
(free tier available).

There's also an optional **autonomous mode** (`autonomous_research` / `aurelius-research`)
where Aurelius drives its own LLM — that one needs an LLM API key with quota.

---

## Install

```bash
pip install aurelius-mcp
```

> The bare name `aurelius` was already taken on PyPI, so the package ships as
> **`aurelius-mcp`**. The import name (`import aurelius`) and the CLI command (`aurelius`)
> are unchanged.

This provides two commands:
- `aurelius` — launch the MCP server (stdio). This is what MCP clients run.
- `aurelius-research "<topic>"` — run one autonomous research job from the terminal.

> **If `aurelius` isn't found** (the pip scripts dir may not be on your PATH — common on
> Windows), use the equivalent module form anywhere a `command` is expected:
> `"command": "python", "args": ["-m", "aurelius"]`.

## Get a Tavily key (optional — for general web search)

Citation verification (`verify_citation`, `verify_claims`) needs **no key** — it runs against
the free, keyless OpenAlex and Crossref APIs. A Tavily key is only needed for `web_search`
(general factual-claim evidence) and as a fallback when a citation isn't indexed in either
scholarly database. Create a free key at <https://tavily.com> and expose it as
`TAVILY_API_KEY` (see the config snippets below, which inject it into the server's environment).

---

## Connect it to your app (local / stdio)

### Claude Desktop
Edit `claude_desktop_config.json` (Settings → Developer → Edit Config):
```json
{
  "mcpServers": {
    "aurelius": {
      "command": "aurelius",
      "env": { "TAVILY_API_KEY": "tvly-your-key" }
    }
  }
}
```
Restart Claude Desktop. See [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json).

### Claude Code
```bash
claude mcp add aurelius --env TAVILY_API_KEY=tvly-your-key -- aurelius
```

### Cursor
Add to `~/.cursor/mcp.json` (or the project `.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "aurelius": { "command": "aurelius", "env": { "TAVILY_API_KEY": "tvly-your-key" } }
  }
}
```

### Gemini CLI
Add to `~/.gemini/settings.json`:
```json
{
  "mcpServers": {
    "aurelius": { "command": "aurelius", "env": { "TAVILY_API_KEY": "tvly-your-key" } }
  }
}
```

Then just ask: *"Use Aurelius to research the historical correlation between GDP growth and
unemployment, and verify every citation."*

---

## Seeing it catch a bad citation

A real run on *"the historical correlation between GDP growth and unemployment (Okun's law)"*:
Claude drafted the paper, then called `verify_citation` on every reference.

| Citation | Verdict |
|---|---|
| Okun, A. M. (1962). *Potential GNP: Its Measurement and Significance.* | ✅ Verified — corroborated by arXiv and Federal Reserve sources |
| Knotek, E. S. II (2007). *How Useful is Okun's Law?* | ✅ Verified — Federal Reserve Bank of Kansas City |
| A third citation with a misattributed author | ✏️ Caught and corrected before the draft was finalized |

Nothing unverifiable made it into the final draft. That's the whole point.

## Seeing it catch a retracted paper

`verify_citation` doesn't just check that a paper exists — it checks OpenAlex's live
retraction registry. A real call against the (in)famous Wakefield MMR-autism paper:

```python
verify_citation("Wakefield, A. J. et al. (1998). Ileal-lymphoid-nodular hyperplasia, "
                 "non-specific colitis, and pervasive developmental disorder in children.")
```
```json
{
  "verdict": "retracted",
  "is_retracted": true,
  "confidence": "high",
  "source": "openalex",
  "matched_work": {
    "title": "RETRACTED: Ileal-lymphoid-nodular hyperplasia, non-specific colitis, ...",
    "doi": "10.1016/s0140-6736(97)11096-0",
    "year": 1998
  },
  "notes": "Retracted work — flagged by openalex. Do not cite."
}
```

`is_retracted` is always a top-level field — impossible for a host model to miss or
rationalize past. A scholarly index can return several records for the same paper (the
original, a retraction notice, clean-looking duplicates); Aurelius specifically resolves
ties in favor of surfacing the retraction rather than picking whichever record looks cleanest.

## Seeing it catch a *mis-attributed* citation

A title match alone is not a verification. Aurelius corroborates the cited author and year
against the matched record, so it catches the subtle case a title-only checker waves through:

```python
verify_citation("Okun, A. M. (1962). Potential GNP: Its Measurement and Significance.")
```
```json
{
  "verdict": "unverified",
  "author_match": false,
  "match_score": 1.0,
  "matched_work": { "authors": ["Charles I. Plosser", "G. William Schwert"], "year": 1979 },
  "notes": "Found a work with this title but different authors (found: Plosser, Schwert; cited: Okun) — likely not the paper you cited."
}
```

The title matches perfectly (1.00), but the only indexed record with that title is a *1979*
paper by *Plosser & Schwert* — not Okun's 1962 original. A title-only checker reports ✓;
Aurelius reports the truth and hands back the `corrected_citation` for the record it actually
found. When a citation carries a DOI or arXiv id, it's looked up directly for an exact match.

---

## Tools

| Tool | What it does | Needs |
|------|--------------|-------|
| `screen_topic(topic)` | Screen a topic against the restricted-domain policy | — |
| `get_research_policy()` | Return the accept/reject policy | — |
| `draft_outline(topic)` | Standard academic (Markdown) outline scaffold | — |
| `plan_paper_length(target_pages, …)` | Section-by-section word budget for long-form papers | — |
| `verify_citation(citation)` | Verify against OpenAlex/Crossref/arXiv/Semantic Scholar — DOI-precise, retraction- & author-aware; returns a corrected citation + BibTeX | — (Tavily optional, fallback only) |
| `verify_claims(claims)` | Batch-verify citations/claims into a scored Evidence Ledger | — (Tavily optional, fallback only) |
| `verify_bibliography(text)` | Verify a whole References block; returns a scored ledger + cleaned BibTeX | — (Tavily optional, fallback only) |
| `verify_stat(claim, …)` | Verify a statistic ('GDP grew 2.5% in 2023') against World Bank data | — (Tavily optional, fallback only) |
| `web_search(query, …)` | Search the web for evidence about a factual claim | Tavily key |
| `polish_prose(content, …)` | Style/readability pass on *already-verified* content | — (LLM key only if `use_llm=True`) |
| `diagram_template(diagram_type, …)` | Mermaid scaffold: flowchart / architecture / sequence | — |
| `latex_outline(topic)` | Compile-ready LaTeX article skeleton + BibTeX stub | — |
| `save_draft(content, filename, append)` | Save (or append to) the Markdown draft | — |
| `save_latex(content, filename)` | Save `.tex` / `.bib` source | — |
| `save_report(content)` | Save the verification report | — |
| `autonomous_research(topic, model, …)` | Run the whole linear loop itself | LLM key |
| `autonomous_research_graph(topic, …)` | Run the multi-stage **agent DAG** (orchestration layer) — audit-trailed, checkpointed | LLM key (verification stays keyless) |

Outputs are written to `~/aurelius_output/` in your home directory (override with
`AURELIUS_OUTPUT_DIR`) — never to the process's current working directory, since MCP
clients often launch the server from a location you can't write to.

### Long-form papers (20–80+ pages)
Call `plan_paper_length(target_pages=40)` for a section-by-section word-count budget, then
draft and `verify_claims` one section at a time, appending each with
`save_draft(content, filename, append=True)` so the host model never has to resend the whole
accumulated document. See [`SKILL.md`](skill/aurelius/SKILL.md) for the full workflow.

### A note on `polish_prose`
It's a **readability pass on already-verified content** — it fixes stiff, repetitive LLM
phrasing (hedging chains, transition-word stacking, tricolon padding) while preserving every
citation, number, and claim verbatim. It is explicitly **not** an AI-detector-evasion tool;
pairing that with long-form academic paper generation would enable academic dishonesty, which
is out of scope for a project whose entire premise is showing verifiable receipts.

## The Claude skill

[`skill/aurelius/SKILL.md`](skill/aurelius/SKILL.md) teaches a host model the exact
screen → plan → draft → verify → polish → save workflow, including the long-form
(section-by-section) path. Drop it into your Claude Code/Agent skills so the model uses the
tools rigorously.

---

## Autonomous mode (optional, needs an LLM key)

```bash
export OPENAI_API_KEY=sk-...          # or ANTHROPIC_API_KEY / GOOGLE_API_KEY
export TAVILY_API_KEY=tvly-...
aurelius-research "Health effects of microplastics in drinking water" --model gpt-4o-mini-2024-07-18 --rounds 2
```

Provider is auto-detected from the model name (`gpt-*` → OpenAI, `claude-*` → Anthropic,
`gemini-*` → Google).

### Orchestration mode — the multi-stage agent DAG (`--graph`)

Beyond the linear loop, Aurelius can run a **staged research DAG driven by a swarm of
specialized agents** (literature mining → a parallel hypothesis swarm → feasibility screening
→ experiment design/code → citation verification → adversarial review → drafting → LaTeX →
proof-of-rigor). Every agent action is logged to an audit trail and each stage is
checkpointed under `~/aurelius_output/sessions/`, so a run is fully inspectable and resumable.

```bash
aurelius-research "Effect of sleep duration on reaction time" --graph
```

Or call the `autonomous_research_graph` MCP tool from any client. It's built in-house — **no
LangGraph/LangChain** — reusing the same retraction-aware citation verification as the rest of
Aurelius.

**Code sandbox & p-hacking audit (Phase 2).** The DAG statically audits the generated analysis
code for questionable-research-practice signals (uncorrected multiple comparisons, missing
random seed, post-hoc outlier removal, optional stopping, HARKing, selective reporting) and
reports a risk score. Add `--sandbox` to *also execute* that code in a hardened, network-less
Docker container (CPU/mem/pids caps, read-only fs, dropped capabilities, non-root, timeout) —
opt-in because the code is model-written, and a graceful skip if Docker isn't present:
```bash
aurelius-research "your topic" --graph --sandbox
```

**Cryptographic Proof-of-Rigor (Phase 3).** Each run emits a signed, tamper-evident proof
bundle: a SHA-256 content hash of the evidence ledger + full audit trail, signed with ed25519
(or HMAC if you set `AURELIUS_PROOF_HMAC_SECRET`), written to `~/aurelius_output/proofs/` and
independently checkable with `aurelius.proof.verify_proof(...)`. Optional [IPFS pinning](https://pinata.cloud)
(set `PINATA_JWT`) and optional on-chain anchoring (`pip install aurelius-mcp[chain]` + set
`AURELIUS_CHAIN_RPC` / `AURELIUS_CHAIN_PRIVATE_KEY`) layer on top; both are graceful no-ops when
unconfigured. `check_compliance`, `publish_preprints`, and `patent_freedom` remain honest
placeholders — see [`ARCHITECTURE.md`](ARCHITECTURE.md) for the roadmap.

---

## Platform support (honest status)

| Platform | Status |
|----------|--------|
| Claude Desktop / Code | ✅ Local stdio |
| Gemini CLI, Cursor | ✅ Local stdio |
| ChatGPT | ⚠️ Needs a remote (HTTP/SSE) deployment — on the roadmap |
| Perplexity | ❌ No user-added MCP servers yet |

## License
MIT
