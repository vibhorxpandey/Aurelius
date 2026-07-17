# ADR 0001 — In-house DAG vs LangGraph

Status: accepted

Context

The original design considered using LangGraph/LangChain for orchestrating multi-agent research DAGs. However, adding those SDKs would increase runtime dependencies and expose coupling to upstream API/behavior changes.

Decision

We implement a lightweight, in-house DAG and agent orchestration engine using only the Python standard library and minimal HTTP clients. This keeps the runtime footprint small (mcp + httpx) and allows fine-grained control over audit trails, checkpointing, and testability.

Consequences

- Pros: smaller install, simpler dependency surface, greater control over behavior and testing.
- Cons: reimplementing patterns provided by mature SDKs; additional maintenance burden.

