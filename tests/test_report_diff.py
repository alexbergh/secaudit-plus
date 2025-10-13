import json
from pathlib import Path

from modules.report_diff import compare_reports, format_report_diff


BEFORE_REPORT = {
    "results": [
        {
            "id": "CHK-001",
            "name": "SSH root login",
            "module": "network",
            "severity": "high",
            "result": "PASS",
        },
        {
            "id": "CHK-002",
            "name": "Auditd enabled",
            "module": "system",
            "severity": "medium",
            "result": "FAIL",
            "reason": "service disabled",
        },
    ],
    "summary": {
        "score": 80.0,
        "status_counts": {"PASS": 1, "FAIL": 1},
    },
}


AFTER_REPORT = {
    "results": [
        {
            "id": "CHK-001",
            "name": "SSH root login",
            "module": "network",
            "severity": "high",
            "result": "FAIL",
            "reason": "PermitRootLogin yes",
        },
        {
            "id": "CHK-002",
            "name": "Auditd enabled",
            "module": "system",
            "severity": "medium",
            "result": "PASS",
        },
        {
            "id": "CHK-003",
            "name": "Chrony running",
            "module": "services",
            "severity": "low",
            "result": "WARN",
            "reason": "using fallback NTP",
        },
    ],
    "summary": {
        "score": 70.0,
        "status_counts": {"PASS": 1, "FAIL": 1, "WARN": 1},
    },
}


def test_compare_reports_detects_changes(tmp_path: Path) -> None:
    before_path = tmp_path / "before.json"
    before_path.write_text(json.dumps(BEFORE_REPORT), encoding="utf-8")
    after_path = tmp_path / "after.json"
    after_path.write_text(json.dumps(AFTER_REPORT), encoding="utf-8")

    diff = compare_reports(before_path, after_path)

    assert diff["summary"]["regressions"] == 1
    assert diff["summary"]["improvements"] == 1
    assert diff["summary"]["new"] == 1
    assert diff["summary"]["removed"] == 0
    assert diff["summary"]["unchanged"] == 0

    regression = diff["regressions"][0]
    assert regression["id"] == "CHK-001"
    assert regression["before"] == "PASS"
    assert regression["after"] == "FAIL"
    assert "PermitRootLogin" in regression["reason"]

    improvement = diff["improvements"][0]
    assert improvement["id"] == "CHK-002"
    assert improvement["before"] == "FAIL"
    assert improvement["after"] == "PASS"

    formatted = format_report_diff(diff)
    assert "Regressions" in formatted
    assert "CHK-001" in formatted
    assert "Score: 80.0" in formatted

    diff_fail_only = compare_reports(before_path, after_path, fail_only=True)
    assert diff_fail_only["summary"]["new"] == 0
    assert diff_fail_only["summary"]["regressions"] == 1
