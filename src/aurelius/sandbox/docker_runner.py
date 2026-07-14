"""Run untrusted, model-generated analysis code inside a hardened Docker container.

This is the opt-in, security-sensitive half of Phase 2. Because the code is written by an
LLM, execution is **off by default** (the agent only calls this when explicitly enabled) and
the container is locked down hard:

  --network none            no network access
  --memory / --cpus         resource caps
  --pids-limit              fork-bomb protection
  --read-only + tmpfs       immutable root filesystem, writable only /tmp
  --cap-drop ALL            no Linux capabilities
  --security-opt no-new-privileges
  --user 65534:65534        run as `nobody`
  timeout                   hard wall-clock kill

We shell out to the `docker` CLI (no Python `docker` SDK) so Aurelius keeps its dependency
footprint at mcp + httpx. If Docker isn't installed/running, this degrades to a clear,
honest "unavailable" result instead of raising — the caller records a skip.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

DEFAULT_IMAGE = "python:3.11-slim"


def docker_available() -> bool:
    """True if the docker CLI exists and its daemon answers. Best-effort, fast, never raises."""
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def run_in_docker(
    code: str,
    *,
    image: str = DEFAULT_IMAGE,
    timeout: int = 30,
    memory: str = "256m",
    cpus: str = "1.0",
    pids_limit: int = 128,
) -> Dict[str, Any]:
    """Execute `code` as a Python script in a hardened, network-less container.

    Returns {"ok", "available", "backend", "exit_code", "stdout", "stderr", "timed_out",
             "image", "note"}. ``ok`` is True only if Docker ran the code and it exited 0.
    """
    base = {"backend": "docker", "image": image, "stdout": "", "stderr": "", "exit_code": None,
            "timed_out": False}

    if not docker_available():
        return {**base, "ok": False, "available": False,
                "note": "Docker not available (CLI missing or daemon not running); execution skipped."}

    with tempfile.TemporaryDirectory(prefix="aurelius_sbx_") as tmp:
        script = Path(tmp) / "script.py"
        script.write_text(code, encoding="utf-8")
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", memory, "--memory-swap", memory,
            "--cpus", cpus,
            "--pids-limit", str(pids_limit),
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", "65534:65534",
            "-v", f"{tmp}:/work:ro", "-w", "/work",
            image, "python", "script.py",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            return {**base, "ok": False, "available": True, "timed_out": True,
                    "stdout": (e.stdout or "") if isinstance(e.stdout, str) else "",
                    "note": f"Execution exceeded {timeout}s wall-clock limit and was killed."}
        except (subprocess.SubprocessError, OSError) as e:
            return {**base, "ok": False, "available": True, "note": f"Docker invocation failed: {e}"}

    return {
        **base,
        "available": True,
        "ok": r.returncode == 0,
        "exit_code": r.returncode,
        "stdout": r.stdout[-8000:],
        "stderr": r.stderr[-4000:],
        "note": "Executed in hardened container (no network, capped resources)."
                if r.returncode == 0 else "Container ran but the script exited non-zero.",
    }
