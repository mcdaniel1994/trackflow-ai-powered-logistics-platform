from __future__ import annotations

from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient

from incident_processor.analysis import analyze_csv_bytes
from incident_processor.cli import main
from incident_processor.main import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sample-incidents.csv"


def test_cli_outputs_expected_metrics_without_email_leakage():
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main([str(FIXTURE)], stdin=StringIO("n\n"), stdout=stdout, stderr=stderr)
    output = stdout.getvalue()

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "TOTAL RECORDS IN FILE .......... 100" in output
    assert "Valid records ................ 95" in output
    assert "Average score: 3.06 / 5.00" in output
    assert "@example.com" not in output


def test_cli_and_api_share_equivalent_analysis_results():
    core_payload = analyze_csv_bytes(FIXTURE.read_bytes()).to_dict()
    client = TestClient(create_app())

    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/incidents/analyze",
            files={"file": ("sample-incidents.csv", handle, "text/csv")},
        )

    assert response.status_code == 200
    assert response.json() == core_payload

