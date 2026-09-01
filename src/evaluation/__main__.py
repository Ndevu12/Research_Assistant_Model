# -*- coding: utf-8 -*-
"""Run the golden-set evaluation from the command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from .harness import format_report, format_report_json, run_golden_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate ranking quality against the golden dataset",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Path to a golden dataset YAML (default: evals/golden_set.yaml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full report as JSON (per-query metrics plus means)",
    )
    args = parser.parse_args()

    report = run_golden_evaluation(dataset_path=args.dataset)
    print(format_report_json(report) if args.json else format_report(report))


if __name__ == "__main__":
    main()
