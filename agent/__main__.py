"""CLI entry point for running the UnderCover Agent on the queue or a single claim."""

import argparse
import sys

from agent import main


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for running the queue or a single claim."""
    parser = argparse.ArgumentParser(description="Run the UnderCover Agent.")
    parser.add_argument(
        "--cap",
        type=int,
        default=None,
        help="Maximum number of waiting claims to process in this run.",
    )
    parser.add_argument(
        "--claim",
        type=str,
        default=None,
        help="Run the agent on a single named claim ID (such as CLM-1001).",
    )
    parser.add_argument(
        "--thread",
        type=str,
        default="cli-run",
        help="Thread identifier for the run.",
    )
    return parser.parse_args(argv)


def main_cli(argv: list[str] | None = None) -> int:
    """Execute the CLI command and print the agent's summary."""
    args = parse_args(argv)
    if args.claim:
        output = main.run(args.claim, f"{args.thread}-{args.claim}")
    else:
        output = main.run_queue(thread_id=args.thread, cap=args.cap)
    print(output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main_cli())
