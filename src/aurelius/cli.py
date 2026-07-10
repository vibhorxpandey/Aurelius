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
    parser.add_argument("--no-save", action="store_true", help="Do not write draft/report files.")
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
