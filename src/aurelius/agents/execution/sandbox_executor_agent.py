"""SandboxExecutorAgent — run the generated analysis code in a hardened Docker container.

Executing model-written code is inherently risky, so this agent runs it **only when
explicitly enabled** (``enable=True`` / the workflow's ``enable_sandbox`` flag). When
disabled, or when Docker isn't available, it records an honest skip and passes state
through unchanged — the pipeline still completes.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ...sandbox import docker_runner
from ..base import ResearchAgent


class SandboxExecutorAgent(ResearchAgent):
    def __init__(self, enable: bool = False, timeout: int = 30, **kwargs) -> None:
        super().__init__(
            name="Sandbox Executor",
            role="Execute analysis code in an isolated, hardened container",
            **kwargs,
        )
        self.enable = enable
        self.timeout = timeout

    def execute(self, state: ResearchState) -> ResearchState:
        code = state.get("experiment_code", "")
        if not self.enable:
            state["sandbox_result"] = {"ran": False, "reason": "disabled"}
            return self.log(state, "skipped",
                            "Sandbox execution disabled — pass enable_sandbox=True / --sandbox to run.",
                            {"enabled": False})
        if not code or code.strip().startswith("# ("):
            state["sandbox_result"] = {"ran": False, "reason": "no code"}
            return self.log(state, "skipped", "No analysis code to execute.", {"enabled": True})

        result = docker_runner.run_in_docker(code, timeout=self.timeout)
        state["sandbox_result"] = {"ran": result.get("available", False), **result}
        action = "execute_sandbox" if result.get("available") else "skipped"
        return self.log(state, action, result.get("note", ""),
                        {"ok": result.get("ok"), "exit_code": result.get("exit_code"),
                         "timed_out": result.get("timed_out")})
