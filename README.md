# Aurelius

**A fact-checked research MCP server.** Aurelius gives any MCP-capable app — Claude
(Desktop / Code / claude.ai), Gemini CLI, Cursor, and (via a remote deployment) ChatGPT —
a set of research tools that **verify every citation and claim against live web sources**
before presenting it. No more hallucinated papers.

Aurelius grew out of a multi-agent research framework and distills its best idea into a
portable tool server: **screen a topic → draft → fact-check → revise**.

---

## Why this design solves the "API cost" problem

By default Aurelius runs in **host-driven mode**: the app you connect it to (Claude, Gemini,
etc.) uses *its own* model to reason and write, and Aurelius just supplies the research and
fact-checking tools. That means **Aurelius needs no LLM API key of its own** — the tokens are
covered by your existing Claude/Gemini/ChatGPT subscription. The only optional key is
[Tavily](https://tavily.com) for web search (free tier available).

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

## Get a Tavily key (for web search / verification)

Create a free key at <https://tavily.com> and expose it as `TAVILY_API_KEY` (see the config
snippets below, which inject it into the server's environment).

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

## Tools

| Tool | What it does | Needs |
|------|--------------|-------|
| `screen_topic(topic)` | Screen a topic against the restricted-domain policy | — |
| `get_research_policy()` | Return the accept/reject policy | — |
| `draft_outline(topic)` | Standard academic outline scaffold | — |
| `web_search(query, …)` | Search the web for evidence | Tavily key |
| `verify_citation(citation)` | Check a citation exists in reputable sources | Tavily key |
| `save_draft(content)` | Save the Markdown draft | — |
| `save_report(content)` | Save the verification report | — |
| `autonomous_research(topic, model, …)` | Run the whole loop itself | LLM key |

Outputs are written to `./aurelius_output/` (override with `AURELIUS_OUTPUT_DIR`).

## The Claude skill

[`skill/aurelius/SKILL.md`](skill/aurelius/SKILL.md) teaches a host model the exact
screen → draft → verify → save workflow. Drop it into your Claude Code/Agent skills so the
model uses the tools rigorously.

---

## Autonomous mode (optional, needs an LLM key)

```bash
export OPENAI_API_KEY=sk-...          # or ANTHROPIC_API_KEY / GOOGLE_API_KEY
export TAVILY_API_KEY=tvly-...
aurelius-research "Health effects of microplastics in drinking water" --model gpt-4o-mini-2024-07-18 --rounds 2
```

Provider is auto-detected from the model name (`gpt-*` → OpenAI, `claude-*` → Anthropic,
`gemini-*` → Google).

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
