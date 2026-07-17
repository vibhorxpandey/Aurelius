# Contributing to Aurelius

Thanks for your interest in contributing. This document explains how to set up a development environment, run tests, and make contributions that are easy to review.

Getting started
- Fork the repo and create a branch named `feature/<short-desc>` or `fix/<short-desc>`.
- Keep changes focused and add tests for new behavior.

Development environment

1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
.\.venv\Scripts\activate  # Windows
```

2. Install the package in editable mode with dev extras:

```bash
pip install -e ".[dev]"
```

3. Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

Testing

- Run the full test suite:

```bash
python -m pytest -q
```

- Run a single test file:

```bash
python -m pytest src/aurelius/tests/test_graph.py -q
```

Code style

- The project uses Black + Ruff + isort. Pre-commit should enforce formatting locally.
- Before opening a PR, run:

```bash
pre-commit run --all-files
```

Branching & PRs

- Use topic branches (feature/..., fix/..., chore/...).
- Open a PR against `main` with a clear description and the PR checklist completed.

Review process

- Small, focused PRs are faster to review.
- Add tests and documentation for behavioural changes.
- If your change touches security-sensitive code (sandboxing, proofs, chain anchoring), add a note in the PR's Security section and contact the maintainers.

Code of Conduct

By participating in this project you agree to follow the Code of Conduct in CODE_OF_CONDUCT.md.

Thank you for helping improve Aurelius!
