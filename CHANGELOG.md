# Changelog

All notable changes to `aurelius-mcp` are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [0.5.0]

Phases 2 & 3 of the [architecture roadmap](ARCHITECTURE.md): a containerized code sandbox with
p-hacking detection, and a cryptographic Proof-of-Rigor. Runtime install stays `mcp` + `httpx`;
on-chain anchoring is an opt-in `[chain]` extra.

### Added — Phase 2 (sandbox + methodology)
- **Static methodology auditor** (`sandbox/methodology.py`, dependency-free): flags p-hacking /
  data-dredging signals — uncorrected multiple comparisons, missing random seed, post-hoc
  outlier removal, optional stopping, HARKing, selective reporting — with a risk score. Wired
  as the real `MethodologyAuditorAgent` (replaces the placeholder).
- **Hardened Docker sandbox** (`sandbox/docker_runner.py`): executes the generated analysis
  code in a locked-down container (`--network none`, CPU/mem/pids caps, read-only fs,
  `--cap-drop ALL`, non-root, wall-clock timeout). Shells out to the `docker` CLI — no new
  dependency. **Opt-in per run** (`--sandbox` / `enable_sandbox=True`) since the code is
  model-written; degrades to an honest skip when Docker is absent. Plus a `ResultAggregatorAgent`.

### Added — Phase 3 (cryptographic proof)
- **Signed Proof-of-Rigor** (`proof/rigor.py`): canonicalizes the evidence ledger + audit
  trail, produces a SHA-256 **content hash** (tamper-evident, content-addressed) and a
  **signature** — HMAC-SHA256 if `AURELIUS_PROOF_HMAC_SECRET` is set, else ed25519 via
  `cryptography` if available, else hash-only. `verify_proof()` re-checks hash + signature.
- **Optional IPFS pinning** (`proof/ipfs.py`, Pinata over httpx) and **optional blockchain
  anchoring** (`proof/anchor.py`: always writes a local append-only anchor log; additionally
  anchors the hash on an EVM chain when `web3` + `AURELIUS_CHAIN_RPC`/`AURELIUS_CHAIN_PRIVATE_KEY`
  are configured). `ProofOfRigorAgent` upgraded from a text summary to the full signed bundle;
  real `LivingDocVersionerAgent` keeps an append-only, content-hash-keyed version history.

### Fixed
- Proof payload now deep-copies the audit trail so the attestation snapshots state at
  build time (the agent's own post-signing audit-log append no longer invalidates the hash).

### Notes
- New optional extra: `pip install aurelius-mcp[chain]` for on-chain anchoring. The on-chain
  path sends a real gas-costing transaction and is left unexercised in CI — validate on a
  testnet (e.g. Polygon Amoy) before mainnet. 39 tests pass.

## [0.4.0]

Phase 1 of the [architecture roadmap](ARCHITECTURE.md): an orchestration layer that runs a
multi-stage agent swarm instead of a single linear loop — built in-house, with **no new
runtime dependencies** (still just `mcp` + `httpx`; no LangGraph/LangChain).

### Added
- **`autonomous_research_graph(topic, …)` MCP tool** and **`aurelius-research … --graph`
  CLI flag** — run a 16-stage research DAG (literature mining → parallel hypothesis swarm →
  feasibility screening → experiment design/code → citation verification → adversarial review
  → drafting → LaTeX → proof-of-rigor), logging every agent action to an audit trail and
  checkpointing each stage under `<output_dir>/sessions/`.
- **In-house DAG engine** (`orchestration/graph.py`) with conditional routing, human-in-the-
  loop breakpoints, and JSON checkpoint/resume — a dependency-free stand-in for LangGraph.
- **Agent framework** (`agents/`): a `ResearchAgent` base plus implemented hypothesis,
  execution, verification, and publication agents. `CitationVerifierAgent` reuses the existing
  retraction-aware `verify_claims`; later-phase stages (sandbox, p-hacking audit, preprint
  publishing, patent-freedom, IPFS versioning) are honest no-op placeholders.
- **Agent swarm coordinator** (`orchestration/swarm.py`) for parallel hypothesis generation,
  and a **workflow manager** (`orchestration/workflow_manager.py`) for sessions/checkpoints.
- 20 new tests (engine, agents with a mocked LLM, swarm merge semantics, full-DAG dry run).

### Notes
- The existing linear `autonomous_research` tool and all fact-checking tools are unchanged and
  fully backward-compatible. The reasoning agents need an LLM key; citation verification stays
  keyless and degrades gracefully when no key is configured.

## [0.3.0]

Deeper, more precise verification (8 → 16 tools).

### Fixed
- **Citation matching no longer relies on title alone.** `verify_citation` now corroborates
  the cited first-author surname and year against the matched record, so a same-titled work
  by different authors is honestly flagged `unverified` instead of a false ✓. (This was a real
  bug: "Okun, A. M. (1962). Potential GNP…" matched a 1979 Plosser & Schwert record and was
  reported verified with high confidence.)
- Extended the OpenAlex filter sanitizer to strip `?`/`*` (wildcard chars that caused HTTP 400
  on titles ending in a question mark).

### Added
- **DOI / arXiv-id direct lookup** — when a citation carries an identifier, it's looked up
  exactly (OpenAlex → Crossref by DOI; arXiv by id), skipping fuzzy title matching.
- **Corrected citations** — `verify_citation` returns a `corrected_citation` and a `bibtex`
  entry built from authoritative metadata, plus `author_match` / `year_match` flags.
- **Broader coverage** — arXiv and Semantic Scholar added to the source chain, so preprints
  and working papers that OpenAlex/Crossref miss now resolve.
- **`verify_bibliography(text)`** — verify a whole References block at once; returns a scored
  ledger, a cleaned `corrected_bibtex`, and `corrected_references`.
- **`verify_stat(claim, …)`** — verify a numeric/statistical claim against World Bank primary
  data (keyless), with a graceful web-search fallback; returns verified / contradicted /
  unverified with the actual value.
- Optional `SEMANTIC_SCHOLAR_API_KEY` (raises rate limits; the API works keyless).

## [0.2.0]

Scholarly-grade verification and a much larger tool surface (8 → 14 tools).

### Added
- **Scholarly citation verification** — `verify_citation` now checks
  [OpenAlex](https://openalex.org) and [Crossref](https://www.crossref.org) (free,
  keyless, DOI-backed) instead of a naive web-keyword heuristic, and is
  **retraction-aware**: a retracted paper is surfaced via a top-level `is_retracted`
  flag and never quietly treated as verified. Tavily becomes an optional fallback for
  works not indexed in either database.
- **`verify_claims`** — batch-verify a mixed list of citations and factual claims into
  a scored **Evidence Ledger** (per-item verdicts + sources, a document-level
  verification score, and a `save_report`-ready Markdown summary with unverified /
  retracted items struck through).
- **`plan_paper_length`** + **`save_draft(append=True)`** — section-by-section word
  budgeting and incremental saving for long-form (20–80+ page) papers, so a host model
  never has to resend the whole accumulated draft.
- **`polish_prose`** — a readability pass on already-verified content (style guidelines
  by default; optional BYO-key LLM rewrite). Explicitly not an AI-detector-evasion tool.
- **`diagram_template`** — Mermaid scaffolds for flowchart / architecture / sequence
  diagrams.
- **`latex_outline`** + **`save_latex`** — a compile-ready LaTeX article skeleton and a
  BibTeX stub, with a generic `.tex`/`.bib` save.

### Fixed
- OpenAlex's `filter=` syntax rejects unescaped commas in title-search text (very common
  in real titles) — titles are now sanitized before querying.
- Retraction tie-breaking: a scholarly index can return both a retracted record and a
  clean duplicate of the same paper; matching now favors surfacing the retraction.
- Emoji in generated Markdown crashed non-UTF-8 (Windows cp1252) consoles — the Evidence
  Ledger now uses ASCII bracket markers.
- `__version__` in the package no longer drifts behind `pyproject.toml`.

## [0.1.2]

### Fixed
- Output is written to `~/aurelius_output/` (home directory) instead of a
  cwd-relative path. MCP clients such as Claude Desktop launch the server with the
  working directory set to a protected location (e.g. `C:\Windows\System32`), which made
  `save_draft` / `save_report` fail with a permission error.

## [0.1.0]

Initial release: a host-driven, fact-checked research MCP server with topic screening,
web-search evidence, draft/report saving, and an optional autonomous (BYO-key) mode.

> Note: 0.1.1 was an internal version bump (repository URLs, author metadata) that was
> superseded by 0.1.2 before publication and never released to PyPI.

[0.2.0]: https://pypi.org/project/aurelius-mcp/0.2.0/
[0.1.2]: https://pypi.org/project/aurelius-mcp/0.1.2/
[0.1.0]: https://pypi.org/project/aurelius-mcp/0.1.0/
