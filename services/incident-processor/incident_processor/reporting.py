"""Console and CSV reporting for incident analysis."""

from __future__ import annotations

import csv
from io import StringIO

from .constants import RULES, SCORE_LABELS
from .models import AnalysisResult


def format_console_report(result: AnalysisResult, source_file: str) -> str:
    data = result.to_dict()
    lines = [
        "=" * 60,
        "  TRACKFLOW - INCIDENT REPORT ANALYSIS",
        f"  Source file: {source_file}",
        "=" * 60,
        "",
        f"TOTAL RECORDS IN FILE .......... {result.total_records}",
        f"  - Valid records ................ {result.valid_records}",
        f"  - Invalid / incomplete .......... {result.invalid_records}",
        "",
        "INVALID RECORDS BREAKDOWN",
    ]

    nonzero_rules = [
        rule
        for rule in data["invalid_rules"]
        if isinstance(rule, dict) and int(rule["count"]) > 0
    ]
    if nonzero_rules:
        for rule in nonzero_rules:
            lines.append(f"  - {str(rule['label']):<31} {rule['count']}")
    else:
        lines.append("  - None .......................... 0")

    lines.extend(["", "BREAKDOWN BY CATEGORY (valid records)"])
    for item in data["categories"]:
        if isinstance(item, dict):
            lines.append(
                f"  - {str(item['code']):<31} {item['count']:>3}  ({item['percentage']}%)"
            )

    lines.extend(["", "BREAKDOWN BY STATUS (valid records)"])
    for item in data["statuses"]:
        if isinstance(item, dict):
            lines.append(
                f"  - {str(item['code']):<31} {item['count']:>3}  ({item['percentage']}%)"
            )

    lines.extend(["", "BREAKDOWN BY COUNTRY (valid records)"])
    for item in data["countries"]:
        if isinstance(item, dict):
            lines.append(
                f"  - {str(item['code']):<31} {item['count']:>3}  ({item['percentage']}%)"
            )

    satisfaction = data["satisfaction"]
    if not isinstance(satisfaction, dict):
        raise TypeError("Unexpected satisfaction result shape")

    lines.extend(
        [
            "",
            "SATISFACTION INDEX (closed incidents)",
            f"  Scored incidents: {satisfaction['scored_incidents']} of {satisfaction['closed_incidents']}",
            f"  Average score: {satisfaction['average_score']} / 5.00",
        ]
    )
    for item in satisfaction["scores"]:
        if isinstance(item, dict):
            score = int(item["score"])
            label = SCORE_LABELS[score]
            lines.append(f"  - Score {score} ({label}) {item['count']:>8}")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


def build_export_csv(result: AnalysisResult) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["section", "metric", "value", "percentage"])
    writer.writeheader()

    rows = _export_rows(result)
    writer.writerows(rows)
    return output.getvalue()


def _export_rows(result: AnalysisResult) -> list[dict[str, str | int]]:
    # Row order is part of the export contract: summary, invalid rule counters,
    # category, status, country, satisfaction — mirroring the console report so
    # the CSV is deterministic and diffable between runs.
    data = result.to_dict()
    rows: list[dict[str, str | int]] = [
        {"section": "summary", "metric": "total_records", "value": result.total_records, "percentage": ""},
        {"section": "summary", "metric": "valid_records", "value": result.valid_records, "percentage": ""},
        {"section": "summary", "metric": "invalid_records", "value": result.invalid_records, "percentage": ""},
    ]

    for rule in RULES:
        rows.append(
            {
                "section": "invalid_records",
                "metric": rule.code,
                "value": result.invalid_rule_counts.get(rule.code, 0),
                "percentage": "",
            }
        )

    for item in data["categories"]:
        if isinstance(item, dict):
            rows.append(
                {
                    "section": "category",
                    "metric": str(item["code"]),
                    "value": int(item["count"]),
                    "percentage": str(item["percentage"]),
                }
            )

    for item in data["statuses"]:
        if isinstance(item, dict):
            rows.append(
                {
                    "section": "status",
                    "metric": str(item["code"]),
                    "value": int(item["count"]),
                    "percentage": str(item["percentage"]),
                }
            )

    for item in data["countries"]:
        if isinstance(item, dict):
            rows.append(
                {
                    "section": "country",
                    "metric": str(item["code"]),
                    "value": int(item["count"]),
                    "percentage": str(item["percentage"]),
                }
            )

    satisfaction = data["satisfaction"]
    if not isinstance(satisfaction, dict):
        raise TypeError("Unexpected satisfaction result shape")

    rows.extend(
        [
            {
                "section": "satisfaction",
                "metric": "scored_incidents",
                "value": int(satisfaction["scored_incidents"]),
                "percentage": "",
            },
            {
                "section": "satisfaction",
                "metric": "closed_incidents",
                "value": int(satisfaction["closed_incidents"]),
                "percentage": "",
            },
            {
                "section": "satisfaction",
                "metric": "average_score",
                "value": str(satisfaction["average_score"]),
                "percentage": "",
            },
        ]
    )
    for item in satisfaction["scores"]:
        if isinstance(item, dict):
            rows.append(
                {
                    "section": "satisfaction",
                    "metric": f"score_{item['score']}",
                    "value": int(item["count"]),
                    "percentage": "",
                }
            )

    return rows

