# Aurelius: Complete Architecture & Roadmap

## Overview

Aurelius is evolving from a **local fact-checking MCP server** into the **definitive decentralized platform for autonomous, end-to-end scientific research, verification, and automated publication**—a zero-trust operating system for 21st-century science.

This document outlines the complete architecture, development phases, and implementation strategy.

---

## Current State ✅

**What exists (shipped in 0.3.0):**
- MCP server with ~16 research + fact-checking tools (OpenAlex, Crossref, arXiv, Semantic
  Scholar, World Bank, Tavily) — DOI-precise, retraction- and author-aware
- Host-driven mode (uses Claude/Gemini's models, no LLM API key needed)
- Evidence Ledger, bibliography verification, numeric/stat checking, LaTeX + diagram scaffolds
- A working *linear* autonomous pipeline (`screen → draft → gather evidence → check → revise`)
- **Phase 1 orchestration layer (0.4.0):** a lightweight in-house DAG + agent swarm — see
  the banner in the Phase 1 section below
- Published on PyPI as `aurelius-mcp`

**Actual repo structure** (the doc originally sketched an `aurelius/mcp_server/…` layout; the
real package lives under `src/aurelius/…` per hatchling `packages = ["src/aurelius"]`):
```
src/aurelius/
├── server.py               # MCP server (stdio) — registers all tools
├── cli.py                  # `aurelius-research` CLI (add --graph for the DAG)
├── config.py               # key/env + output-dir resolution
├── autonomous/             # linear pipeline + SDK-free multi-provider LLM client
│   ├── pipeline.py
│   └── llm.py
├── tools/                  # screening, drafting, scholarly, ledger, numeric, search,
│                           #   style, latex, diagrams
├── orchestration/          # Phase 1 (NEW): graph engine, swarm, research graph, manager
├── agents/                 # Phase 1 (NEW): the agent swarm
└── tests/
```

---

## Phase 1: Orchestration Layer & Agent Swarms ✅ IMPLEMENTED (0.4.0)

> **Implementation note — read this before the code snippets below.** Phase 1 shipped, but
> **without LangGraph or LangChain**. To keep Aurelius's install light (`mcp` + `httpx` only)
> and preserve the SDK-free, multi-provider LLM client in `autonomous/llm.py`, the DAG and
> agent framework are a small in-house engine. The LangGraph/LangChain snippets in this
> section are the *original design sketch*; the shipped code maps to them as follows:
>
> | Design sketch (below)                    | Shipped module (in-house)                          |
> |------------------------------------------|----------------------------------------------------|
> | `StateGraph` / `create_research_graph()` | `orchestration/graph.py` (`Graph`) + `orchestration/research_graph.py` (`build_research_graph`) |
> | `ResearchState` TypedDict                | `orchestration/state.py`                            |
> | `ResearchAgent` (LangChain tools/model)  | `agents/base.py` — `model` is a model-name string used with `llm.complete`, no LangChain |
> | `AgentSwarmCoordinator`                  | `orchestration/swarm.py`                            |
> | `ResearchWorkflowManager` / MemorySaver  | `orchestration/workflow_manager.py` + JSON checkpoints under `<output_dir>/sessions/` |
> | `autonomous_research` MCP tool           | `autonomous_research_graph` tool (linear `autonomous_research` kept for back-compat) |
>
> Load-bearing agents are fully implemented and reuse the existing tools (notably
> `CitationVerifierAgent` → `ledger.verify_claims`). Later-phase stages (sandbox execution,
> p-hacking audit, preprint publishing, patent-freedom, IPFS versioning) are **honest
> placeholders** (`agents/placeholders.py`) that pass state through and log a `skipped` entry.

### Goals
- Build LangGraph-based DAG for end-to-end research workflows
- Implement AI agent swarms for hypothesis generation, execution, verification, and publication
- Create stateful task orchestration with human-in-the-loop breakpoints
- Enable autonomous research mode with multi-agent coordination

### Architecture

#### 1.1 Core Orchestrator (LangGraph)

**File:** `aurelius/orchestration/research_orchestrator.py`

```python
from langgraph.graph import StateGraph
from typing import TypedDict, Annotated

class ResearchState(TypedDict):
    """Central state object for research pipeline."""
    topic: str
    hypothesis: str
    literature_summary: str
    experiment_code: str
    sandbox_result: dict
    verification_report: dict
    paper_draft: str
    evidence_ledger: list
    proof_of_rigor: str
    publication_urls: list
    researcher_id: str
    created_at: str
    metadata: dict

def create_research_graph() -> StateGraph:
    """
    Main DAG orchestrating:
    Stage 1: Hypothesis Generation → Validation
    Stage 2: Experimental Design → Code Generation
    Stage 3: Sandbox Execution → P-hacking Detection
    Stage 4: Verification (Claims, Citations, Ethics)
    Stage 5: Adversarial Review
    Stage 6: Paper Drafting & Formatting
    Stage 7: Publishing (Preprints + Living Docs)
    """
    workflow = StateGraph(ResearchState)
    
    # Stage 1: Hypothesis
    workflow.add_node("generate_hypotheses", hypothesis_generation_node)
    workflow.add_node("screen_hypotheses", hypothesis_validation_node)
    workflow.add_edge("generate_hypotheses", "screen_hypotheses")
    
    # Stage 2: Design & Code
    workflow.add_node("design_experiments", experiment_design_node)
    workflow.add_node("generate_analysis_code", code_generation_node)
    workflow.add_edge("screen_hypotheses", "design_experiments")
    workflow.add_edge("design_experiments", "generate_analysis_code")
    
    # Stage 3: Execute & Audit
    workflow.add_node("execute_in_sandbox", sandbox_execution_node)
    workflow.add_node("detect_p_hacking", p_hacking_detection_node)
    workflow.add_edge("generate_analysis_code", "execute_in_sandbox")
    workflow.add_edge("execute_in_sandbox", "detect_p_hacking")
    
    # Stage 4: Verify
    workflow.add_node("verify_all_claims", claim_verification_node)
    workflow.add_node("verify_citations", citation_verification_node)
    workflow.add_node("ethics_compliance", compliance_check_node)
    workflow.add_edge("detect_p_hacking", "verify_all_claims")
    workflow.add_edge("verify_all_claims", "verify_citations")
    workflow.add_edge("verify_citations", "ethics_compliance")
    
    # Stage 5: Review
    workflow.add_node("adversarial_review", adversarial_review_node)
    workflow.add_edge("ethics_compliance", "adversarial_review")
    
    # Stage 6: Compile
    workflow.add_node("draft_paper", paper_generation_node)
    workflow.add_node("format_latex", latex_formatting_node)
    workflow.add_node("generate_proof_of_rigor", proof_of_rigor_node)
    workflow.add_edge("adversarial_review", "draft_paper")
    workflow.add_edge("draft_paper", "format_latex")
    workflow.add_edge("format_latex", "generate_proof_of_rigor")
    
    # Stage 7: Publish
    workflow.add_node("publish_preprints", preprint_publication_node)
    workflow.add_node("update_living_doc", living_doc_update_node)
    workflow.add_node("patent_freedom_check", patent_freedom_node)
    workflow.add_edge("generate_proof_of_rigor", "publish_preprints")
    workflow.add_edge("publish_preprints", "update_living_doc")
    workflow.add_edge("update_living_doc", "patent_freedom_check")
    
    workflow.set_entry_point("generate_hypotheses")
    workflow.set_finish_point("patent_freedom_check")
    
    return workflow.compile()
```

**Key decisions:**
- Use LangGraph for reproducible, inspectable workflows
- Each node is an agent or tool invocation
- State is immutable—tracks full audit trail
- Supports conditional branching (e.g., retry on failed verification)

---

#### 1.2 AI Agent Swarms

**File structure:**
```
aurelius/agents/
├── __init__.py
├── base_agent.py                    # Base class for all agents
│
├── hypothesis_generation/
│   ├── __init__.py
│   ├── literature_miner_agent.py    # Search & summarize papers
│   ├── pattern_discovery_agent.py   # Find gaps, trends
│   ├── theory_generator_agent.py    # Generate counter-factuals (Tree-of-Thoughts)
│   └── hypothesis_validator_agent.py # Feasibility pre-screening
│
├── research_execution/
│   ├── __init__.py
│   ├── experiment_designer_agent.py  # Design reproducible protocols
│   ├── code_generator_agent.py       # Write analysis code
│   ├── sandbox_executor_agent.py     # Orchestrate container execution
│   └── result_aggregator_agent.py    # Collect & validate results
│
├── verification/
│   ├── __init__.py
│   ├── methodology_auditor_agent.py  # Detect p-hacking/data-dredging
│   ├── citation_verifier_agent.py    # Leverage existing aurelius tools
│   ├── adversarial_reviewer_agent.py # Simulate hostile peer review
│   └── compliance_checker_agent.py   # HIPAA/GDPR/ethics screening
│
└── publication/
    ├── __init__.py
    ├── latex_formatter_agent.py      # Journal-specific templates
    ├── preprint_publisher_agent.py   # arXiv/bioRxiv/medRxiv API
    ├── patent_freedom_agent.py       # USPTO/WIPO cross-reference
    └── living_doc_versioner_agent.py # Git/IPFS version control
```

**Base agent class:**

```python
# aurelius/agents/base_agent.py

from abc import ABC, abstractmethod
from langchain_core.tools import Tool
from typing import Any, Dict, List

class ResearchAgent(ABC):
    """Base class for all research agents."""
    
    def __init__(self, name: str, role: str, model, tools: List[Tool] = None):
        self.name = name
        self.role = role
        self.model = model  # Claude, GPT-4, etc.
        self.tools = tools or []
        self.execution_log = []
    
    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent logic and update state."""
        pass
    
    def log_execution(self, action: str, result: Any, metadata: Dict = None):
        """Audit trail for all agent actions."""
        self.execution_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "result": result,
            "metadata": metadata or {}
        })
    
    def get_audit_trail(self):
        return self.execution_log
```

**Example agent implementation:**

```python
# aurelius/agents/hypothesis_generation/theory_generator_agent.py

from aurelius.agents.base_agent import ResearchAgent
from langchain_core.messages import HumanMessage, AIMessage

class TheoryGeneratorAgent(ResearchAgent):
    """
    Uses Tree-of-Thoughts reasoning to generate and explore counter-factual theories.
    Multi-branch exploration of alternative explanations.
    """
    
    def __init__(self, model):
        super().__init__(
            name="Theory Generator",
            role="Generate and explore counter-factual theories",
            model=model
        )
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Given literature summary & topic, generate multiple theories.
        Use Tree-of-Thoughts: explore multiple reasoning paths.
        """
        topic = state.get("topic")
        literature = state.get("literature_summary")
        
        # Tree-of-Thoughts prompt
        prompt = f"""
        Topic: {topic}
        
        Literature Summary:
        {literature}
        
        Generate 3-5 alternative theories or hypotheses that could explain observed phenomena.
        For each theory:
        1. State the theory clearly
        2. Identify key assumptions
        3. Propose counter-factual scenarios
        4. Rate feasibility (1-10) and originality (1-10)
        5. Identify required data/experiments to test
        
        Use divergent thinking: explore paths others may not have considered.
        """
        
        response = self.model.invoke([HumanMessage(content=prompt)])
        theories = parse_theories(response.content)
        
        self.log_execution("generate_theories", theories)
        
        state["hypothesis"] = select_best_theory(theories)
        state["alternative_hypotheses"] = theories
        
        return state
```

---

#### 1.3 Agent Swarm Coordinator

**File:** `aurelius/orchestration/agent_swarm.py`

```python
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

class AgentSwarmCoordinator:
    """
    Manages multiple agents working in parallel.
    Handles inter-agent communication, state aggregation, conflict resolution.
    """
    
    def __init__(self):
        self.agents: Dict[str, ResearchAgent] = {}
        self.message_bus = []  # Async communication log
    
    def register_agent(self, agent: ResearchAgent):
        """Register an agent to the swarm."""
        self.agents[agent.name] = agent
    
    def run_parallel_hypothesis_generation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run multiple hypothesis-generation agents in parallel.
        Aggregate results and let researcher choose.
        """
        agents = [
            self.agents["Literature Miner"],
            self.agents["Pattern Discovery"],
            self.agents["Theory Generator"]
        ]
        
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(agent.execute, state): agent.name for agent in agents}
            
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    result = future.result()
                    results[agent_name] = result
                except Exception as e:
                    print(f"Agent {agent_name} failed: {e}")
        
        # Aggregate and rank hypotheses
        aggregated = aggregate_swarm_results(results)
        state["all_hypotheses"] = aggregated
        
        return state
    
    def broadcast_message(self, message: Dict[str, Any]):
        """Agents can communicate asynchronously."""
        self.message_bus.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message
        })
```

---

#### 1.4 Workflow Manager

**File:** `aurelius/orchestration/workflow_manager.py`

```python
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage

class ResearchWorkflowManager:
    """
    High-level orchestrator for complete research workflows.
    Handles state persistence, human breakpoints, retry logic.
    """
    
    def __init__(self, researcher_id: str):
        self.researcher_id = researcher_id
        self.memory = MemorySaver()
        self.graph = create_research_graph()
        self.breakpoints = {}
        self.session_id = generate_session_id()
    
    def add_human_breakpoint(self, stage: str, requires_approval: bool = True):
        """
        Pause workflow at a stage for human review/approval.
        Used for critical decisions (methodology, publication strategy).
        """
        self.breakpoints[stage] = {
            "requires_approval": requires_approval,
            "researcher_id": self.researcher_id
        }
    
    def execute_research_workflow(self, topic: str, config: Dict[str, Any]):
        """
        End-to-end research execution.
        topic: research topic
        config: research parameters (budget, timeline, constraints)
        """
        initial_state = {
            "topic": topic,
            "hypothesis": "",
            "literature_summary": "",
            "experiment_code": "",
            "sandbox_result": {},
            "verification_report": {},
            "paper_draft": "",
            "evidence_ledger": [],
            "proof_of_rigor": "",
            "publication_urls": [],
            "researcher_id": self.researcher_id,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": config
        }
        
        # Execute with checkpointing
        config_with_checkpointer = {
            "configurable": {
                "thread_id": self.session_id,
                "checkpoint_ns": f"research_{self.researcher_id}"
            }
        }
        
        final_state = self.graph.invoke(initial_state, config_with_checkpointer)
        
        return final_state
    
    def pause_at_breakpoint(self, stage: str, state: Dict[str, Any]):
        """Pause and request human approval."""
        if stage not in self.breakpoints:
            return
        
        breakpoint_info = self.breakpoints[stage]
        
        # Send notification to researcher
        notify_researcher(
            researcher_id=breakpoint_info["researcher_id"],
            stage=stage,
            context=state,
            requires_approval=breakpoint_info["requires_approval"]
        )
        
        # Wait for response
        approval = wait_for_approval(self.researcher_id, stage, timeout=3600)
        
        return approval
    
    def get_session_history(self):
        """Retrieve full workflow execution history."""
        return self.memory.get(self.session_id)
```

---

### 1.5 Integration with Existing MCP Server

**File:** `aurelius/mcp_server/autonomous_mode.py`

```python
from aurelius.orchestration.workflow_manager import ResearchWorkflowManager

async def autonomous_research(topic: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    MCP tool that triggers autonomous end-to-end research.
    Called by Claude / Gemini / any MCP client.
    
    Example:
        {
            "name": "autonomous_research",
            "arguments": {
                "topic": "Impact of dietary fiber on glucose metabolism",
                "config": {
                    "max_papers": 100,
                    "include_preprints": true,
                    "target_journals": ["Nature", "Cell", "Science"]
                }
            }
        }
    """
    researcher_id = get_caller_identity()  # From MCP context
    
    manager = ResearchWorkflowManager(researcher_id=researcher_id)
    
    # Add breakpoints for critical stages
    manager.add_human_breakpoint("design_experiments", requires_approval=True)
    manager.add_human_breakpoint("verify_citations", requires_approval=False)  # Info only
    
    result = manager.execute_research_workflow(topic, config or {})
    
    return {
        "status": "completed",
        "session_id": manager.session_id,
        "final_state": result,
        "audit_trail": manager.get_session_history()
    }
```

---

### 1.6 Testing & Validation

**File:** `aurelius/tests/test_orchestration.py`

```python
import pytest
from aurelius.orchestration.research_orchestrator import create_research_graph

@pytest.fixture
def research_graph():
    return create_research_graph()

def test_hypothesis_generation_node(research_graph):
    """Test that hypothesis generation produces valid output."""
    state = {
        "topic": "Machine learning in drug discovery",
        "literature_summary": "..."
    }
    # Mock agent execution
    result = research_graph.get_node("generate_hypotheses")(state)
    assert "hypothesis" in result
    assert result["hypothesis"] != ""

def test_full_workflow_execution(research_graph):
    """Test end-to-end workflow with mock data."""
    initial_state = {
        "topic": "Climate impact on agriculture",
        "hypothesis": "",
        ...
    }
    final_state = research_graph.invoke(initial_state)
    
    assert final_state["paper_draft"] != ""
    assert len(final_state["evidence_ledger"]) > 0
    assert final_state["proof_of_rigor"] != ""

def test_agent_swarm_parallel_execution():
    """Test that agents run in parallel without conflicts."""
    coordinator = AgentSwarmCoordinator()
    # ... register agents
    
    results = coordinator.run_parallel_hypothesis_generation(state)
    assert len(results) == 3  # 3 agents
```

---

## Project Structure (Phase 1 — as shipped)

```
src/aurelius/
├── server.py                              # + autonomous_research_graph tool
├── cli.py                                 # + --graph flag
├── autonomous/{pipeline.py, llm.py}       # existing linear mode (reused by agents)
├── tools/                                 # existing tools (reused by agents)
│
├── orchestration/
│   ├── __init__.py                        # light init (state + graph only; see note)
│   ├── state.py                           # ResearchState TypedDict + audit helpers
│   ├── graph.py                           # in-house DAG engine (replaces LangGraph)
│   ├── swarm.py                           # AgentSwarmCoordinator (ThreadPoolExecutor)
│   ├── research_graph.py                  # build_research_graph() — the 16-stage DAG
│   └── workflow_manager.py                # sessions, checkpoints, resume, run_research_graph()
│
├── agents/
│   ├── base.py                            # ResearchAgent ABC + PlaceholderAgent
│   ├── placeholders.py                    # honest Phase 2-5 no-op agents
│   ├── hypothesis/                        # literature_miner, pattern_discovery,
│   │                                      #   theory_generator, hypothesis_validator
│   ├── execution/                         # experiment_designer, code_generator
│   ├── verification/                      # citation_verifier (wraps ledger), adversarial_reviewer
│   └── publication/                       # draft_paper, latex_formatter, proof_of_rigor
│
└── tests/
    ├── test_graph.py                      # engine: order, checkpoint, breakpoint/resume
    ├── test_agents.py                     # agents with mocked LLM (no key)
    ├── test_swarm.py                      # parallel merge semantics
    └── test_workflow_manager.py           # full DAG dry run + rejection + breakpoint
```

---

## Implementation Checklist (Phase 1) — ✅ complete

- [x] **Foundation:** `orchestration/state.py`, in-house `orchestration/graph.py` DAG engine,
  `agents/base.py` base class, `orchestration/swarm.py` coordinator
- [x] **Hypothesis agents:** `LiteratureMinerAgent`, `PatternDiscoveryAgent`,
  `TheoryGeneratorAgent` (Tree-of-Thoughts), `HypothesisValidatorAgent` (reuses `screening`)
- [x] **Execution & verification:** `ExperimentDesignerAgent`, `CodeGeneratorAgent`,
  `CitationVerifierAgent` (wraps `ledger.verify_claims`), `AdversarialReviewerAgent`;
  honest placeholders for sandbox / methodology / compliance / publishing / patent / IPFS
- [x] **Integration & testing:** `autonomous_research_graph` MCP tool + `--graph` CLI flag,
  `ResearchWorkflowManager` with JSON checkpointing, 20 passing tests, docs

---

## Dependencies (Phase 1) — none added

Phase 1 deliberately added **no** runtime dependencies. The DAG engine is standard-library
only; agents call the existing `autonomous/llm.py` (plain `httpx`) rather than LangChain.
Runtime install stays `mcp` + `httpx`; tests use `pytest` (already in the `dev` extra).

---

## Phase 1 Success Criteria

✅ **Functional:** Orchestrator can chain agents through complete workflow
✅ **Observable:** Every agent action is logged with audit trail
✅ **Testable:** Unit tests for each agent and orchestrator
✅ **Documented:** Clear examples of how to run autonomous research
✅ **Integrated:** Works with existing MCP server (backward compatible)

---

## Future Phases

### Phase 2: Containerized Code Sandbox
- Docker isolation for experiment execution
- P-hacking & data-dredging detection
- Methodology validation & reproducibility checks

### Phase 3: Evidence Ledger & Immutable Proof
- IPFS-backed evidence storage
- Blockchain anchoring (Ethereum/Polygon)
- Cryptographic Proof-of-Rigor signatures

### Phase 4: Publication Pipeline
- LaTeX template formatting (journal-specific)
- One-click preprint publishing (arXiv, bioRxiv, medRxiv)
- Living documents with version control

### Phase 5: DeSci Integration
- Patent freedom checks (USPTO, WIPO)
- Decentralized funding protocol integration
- Retraction watchers for cited papers

### Phase 6: Multilingual & Memory
- CNKI, Wanfang, global database synthesis
- Episodic memory for organizational knowledge
- Learning from successes and failures

---

## Running Phase 1

```bash
# Editable install (no extra dependencies needed)
pip install -e ".[dev]"

# Run the orchestration test suite
python -m pytest src/aurelius/tests -q

# Run the multi-stage agent DAG from the terminal (needs an LLM key for the reasoning
# agents; citation verification is keyless)
aurelius-research "Effect of sleep duration on reaction time" --graph

# Or via any MCP client: call the `autonomous_research_graph` tool.
```

**Next Step:** Phase 2 — the containerized code sandbox. Replace the
`sandbox_executor` / `methodology_auditor` placeholders in `agents/placeholders.py` with
real agents; no graph rewiring required.

---

## References

- [OpenAlex API](https://docs.openalex.org)
- [Crossref API](https://github.com/CrossRef/rest-api-doc)
- [Agent Design Patterns](https://lilianweng.github.io/posts/2023-06-23-agent/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) — the original design
  reference; Phase 1 uses an in-house engine instead (see the Phase 1 implementation note)

---

**Status:** Phase 1 (orchestration layer & agent swarm) shipped in 0.4.0 — in-house engine,
no LangGraph/LangChain, backward-compatible with the existing MCP server and linear pipeline.
**Next:** Phase 2 (containerized code sandbox).
