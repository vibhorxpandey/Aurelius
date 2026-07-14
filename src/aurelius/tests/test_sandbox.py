"""Sandbox executor — degradation when Docker is absent, and the enabled path via a stub."""
from __future__ import annotations

from aurelius.agents.execution import SandboxExecutorAgent
from aurelius.orchestration.state import new_state
from aurelius.sandbox import docker_runner


def test_disabled_by_default_skips():
    st = new_state("t")
    st["experiment_code"] = "print(1)"
    out = SandboxExecutorAgent(enable=False).execute(st)
    assert out["sandbox_result"]["ran"] is False
    assert out["audit_trail"][-1]["action"] == "skipped"


def test_enabled_but_no_docker_degrades(monkeypatch):
    # Force docker "unavailable" and confirm run_in_docker returns an honest skip.
    monkeypatch.setattr(docker_runner, "docker_available", lambda: False)
    r = docker_runner.run_in_docker("print(1)")
    assert r["ok"] is False and r["available"] is False and "not available" in r["note"].lower()


def test_enabled_runs_via_stub(monkeypatch):
    st = new_state("t")
    st["experiment_code"] = "print('hello')"
    monkeypatch.setattr(
        "aurelius.agents.execution.sandbox_executor_agent.docker_runner.run_in_docker",
        lambda code, **k: {"ok": True, "available": True, "backend": "docker",
                           "exit_code": 0, "stdout": "hello\n", "stderr": "",
                           "timed_out": False, "note": "ran"},
    )
    out = SandboxExecutorAgent(enable=True).execute(st)
    assert out["sandbox_result"]["ran"] is True
    assert out["sandbox_result"]["stdout"] == "hello\n"
    assert out["audit_trail"][-1]["action"] == "execute_sandbox"


def test_docker_available_false_when_cli_missing(monkeypatch):
    monkeypatch.setattr(docker_runner.shutil, "which", lambda name: None)
    assert docker_runner.docker_available() is False
