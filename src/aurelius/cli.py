"""`aurelius-research` — run one autonomous research job from the terminal.

Example:
    aurelius-research "The historical correlation between GDP growth and unemployment" \
        --model gpt-4o-mini-2024-07-18 --rounds 2
"""
from __future__ import annotations

import argparse
import sys

from .autonomous.pipeline import run_autonomous_research


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aurelius-research",
        description="Run an autonomous, fact-checked research draft (requires an LLM API key).",
    )
    parser.add_argument("topic", help="The research topic to investigate.")
    parser.add_argument("--model", default="gpt-4o-mini-2024-07-18", help="LLM model name.")
    parser.add_argument("--provider", default=None, choices=["openai", "anthropic", "google"],
                        help="Force a provider (otherwise auto-detected from the model name).")
    parser.add_argument("--rounds", type=int, default=2, help="Max draft/fact-check revision rounds.")
    parser.add_argument("--graph", action="store_true",
                        help="Run the multi-stage agent DAG (orchestration layer) instead of "
                             "the linear loop. Logs an audit trail and checkpoints each stage.")
    parser.add_argument("--no-save", action="store_true", help="Do not write draft/report files.")
    args = parser.parse_args()

    if args.graph:
        _run_graph(args)
        return

    result = run_autonomous_research(
        args.topic,
        model=args.model,
        provider=args.provider,
        max_rounds=args.rounds,
        save=not args.no_save,
    )

    print(result["reason"])
    if not result["approved"]:
        sys.exit(1)

    status = "VERIFIED" if result["verified"] else "UNVERIFIED (revision budget exhausted)"
    print(f"Rounds: {result['rounds']} | Final status: {status}")
    if result.get("files"):
        for label, path in result["files"].items():
            print(f"  {label}: {path}")


def _run_graph(args) -> None:
    """Run the DAG path and print a compact stage-by-stage summary."""
    # Imported lazily so the default linear path never pays the orchestration import cost.
    from .orchestration.workflow_manager import run_research_graph

    result = run_research_graph(
        args.topic, model=args.model, provider=args.provider, save=not args.no_save
    )
    state = result["final_state"]
    print(f"Status: {result['status']} | Session: {result['session_id']}")
    if not state.get("approved", True):
        print(f"Rejected at screening: {state.get('screen_reason','')}")
        sys.exit(1)
    report = result.get("verification_report", {})
    print(f"Verification score: {report.get('verification_score', 0.0):.0%} "
          f"({report.get('counts', {}).get('total', 0)} items checked)")
    print(f"Audit-trail entries: {len(result['audit_trail'])}")
    print(f"Checkpoint: {result['checkpoint']}")


if __name__ == "__main__":
    main()
