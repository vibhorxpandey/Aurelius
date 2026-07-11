"""Mermaid diagram scaffolds: flowcharts, architecture diagrams, sequence diagrams.

Returns Mermaid syntax only (no rendering, no external dependency) — GitHub, Claude,
and most Markdown viewers render Mermaid fenced code blocks directly.
"""
from __future__ import annotations

from typing import Any, Dict

DIAGRAM_TYPES = ("flowchart", "architecture", "sequence")

_FLOWCHART_TEMPLATE = """%% Topic: {topic}
flowchart TD
    A[Start] --> B{{Decision point}}
    B -->|Yes| C[Do the thing]
    B -->|No| D[Do something else]
    C --> E[End]
    D --> E
"""

_ARCHITECTURE_TEMPLATE = """%% Topic: {topic}
%% Architecture diagram (flowchart + subgraph for max viewer compatibility;
%% C4Context syntax exists in Mermaid but isn't reliably supported by GitHub's
%% renderer, so it's not used as the default here).
flowchart LR
    subgraph Client
        A[User / App]
    end
    subgraph Backend
        B[API Layer]
        C[(Database)]
    end
    A -->|request| B
    B -->|reads/writes| C
    B -->|response| A
"""

_SEQUENCE_TEMPLATE = """%% Topic: {topic}
sequenceDiagram
    participant U as User
    participant S as Service
    participant D as Database
    U->>S: Request
    activate S
    S->>D: Query
    D-->>S: Result
    S-->>U: Response
    deactivate S
"""

_GUIDANCE = {
    "flowchart": (
        "Mermaid flowchart syntax: `flowchart TD` (top-down) or `LR` (left-right). "
        "Node shapes: [] rectangle, {} decision diamond, (()) circle, ([]) stadium. "
        "Edges: --> solid, -.-> dashed, ==> thick; label with -->|text|. "
        "Group related nodes with `subgraph name ... end`."
    ),
    "architecture": (
        "Use `flowchart`/`graph` with `subgraph` blocks to group components (client, "
        "backend, data layer, etc.); label edges with -->|protocol/action|. Use `direction LR` "
        "inside a subgraph to control its internal layout. Avoid C4Context unless you have "
        "confirmed your target viewer supports it -- GitHub/most markdown viewers do not."
    ),
    "sequence": (
        "Mermaid sequence syntax: `participant X as Label`. Solid sync call: ->>; dashed "
        "return/async: -->>. Wrap conditional paths in `alt ... else ... end` or `opt ... end`. "
        "Use `activate`/`deactivate` (or +/- suffix on the arrow) to show a lifeline is busy."
    ),
}


def diagram_template(diagram_type: str, description: str) -> Dict[str, Any]:
    """Return a Mermaid syntax scaffold for a diagram; you fill in the specifics.

    Embed the completed Mermaid in a ```mermaid fenced code block wherever you save it
    (e.g. inside content passed to save_draft) — GitHub, Claude, and most Markdown
    viewers render it inline.

    Args:
        diagram_type: one of "flowchart", "architecture", "sequence".
        description: what the diagram should depict (seeded into a comment in the scaffold).

    Returns {"ok": bool, "diagram_type": str, "mermaid": str|None, "guidance": str|None,
             "error": str|None}
    """
    if diagram_type not in DIAGRAM_TYPES:
        return {
            "ok": False,
            "diagram_type": diagram_type,
            "mermaid": None,
            "guidance": None,
            "error": f"Unknown diagram_type '{diagram_type}'. Choose one of {DIAGRAM_TYPES}.",
        }
    templates = {
        "flowchart": _FLOWCHART_TEMPLATE,
        "architecture": _ARCHITECTURE_TEMPLATE,
        "sequence": _SEQUENCE_TEMPLATE,
    }
    mermaid = templates[diagram_type].format(topic=description)
    return {
        "ok": True,
        "diagram_type": diagram_type,
        "mermaid": mermaid,
        "guidance": _GUIDANCE[diagram_type],
        "error": None,
    }
