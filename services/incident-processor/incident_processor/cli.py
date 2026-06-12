"""Command-line interface for TrackFlow incident analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from .analysis import analyze_csv_file
from .models import IncidentCsvError
from .reporting import build_export_csv, format_console_report


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = argparse.ArgumentParser(description="Analyze a TrackFlow incident CSV export.")
    parser.add_argument("csv_path", help="Path to the incident CSV file.")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)
    try:
        result = analyze_csv_file(csv_path)
    except IncidentCsvError as exc:
        print(f"Error: {exc.code}", file=stderr)
        return 1

    print(format_console_report(result, csv_path.name), file=stdout)
    print("", file=stdout)
    print("Export results to CSV? [y / n]:", end=" ", file=stdout, flush=True)
    answer = stdin.readline().strip().lower()
    if answer == "y":
        export_path = csv_path.with_name(f"{csv_path.stem}-analysis.csv")
        export_path.write_text(build_export_csv(result), encoding="utf-8")
        print(f"Exported aggregate metrics to {export_path}", file=stdout)

    return 0


def entrypoint() -> None:
    raise SystemExit(main())

