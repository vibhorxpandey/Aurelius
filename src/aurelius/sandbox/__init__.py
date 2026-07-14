"""Phase 2 — containerized execution + static methodology auditing.

``methodology.audit_methodology`` is dependency-free and always runs. ``docker_runner`` is
the opt-in, hardened execution path (shells out to the docker CLI; degrades gracefully when
Docker is unavailable)."""
from .docker_runner import DEFAULT_IMAGE, docker_available, run_in_docker
from .methodology import audit_methodology

__all__ = ["audit_methodology", "docker_available", "run_in_docker", "DEFAULT_IMAGE"]
