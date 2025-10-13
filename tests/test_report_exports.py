import json
from pathlib import Path
from xml.etree import ElementTree as ET

from modules.report_generator import generate_sarif_report, generate_junit_report


SAMPLE_PROFILE = {
    "id": "base-linux",
    "profile_name": "Базовый профиль Linux",
    "description": "Минимальный базовый профиль",
    "schema_version": "1.1",
}

SAMPLE_SUMMARY = {
    "score": 82.5,
    "coverage": 0.96,
    "checks_total": 3,
}

SAMPLE_HOST = {
    "hostname": "golden-image",
    "ip": "192.0.2.10",
}

SAMPLE_RESULTS = [
    {
        "id": "CHK-001",
        "name": "Critical config is present",
        "module": "system",
        "severity": "high",
        "result": "FAIL",
        "reason": "File /etc/secure not found",
        "remediation": "Создайте файл /etc/secure и задайте права 600",
        "duration": 0.45,
        "stderr": "ls: cannot access '/etc/secure': No such file or directory",
    },
    {
        "id": "CHK-002",
        "name": "SSH banner configured",
        "module": "network",
        "severity": "medium",
        "result": "WARN",
        "reason": "Banner is set but does not match policy",
        "duration": 0.21,
    },
    {
        "id": "CHK-003",
        "name": "Chrony service enabled",
        "module": "services",
        "severity": "low",
        "result": "PASS",
        "duration": 0.12,
        "output": "chronyd enabled",
    },
]


def test_generate_sarif_report(tmp_path):
    output = tmp_path / "report.sarif"
    generate_sarif_report(
        SAMPLE_PROFILE,
        SAMPLE_RESULTS,
        str(output),
        summary=SAMPLE_SUMMARY,
        host_info=SAMPLE_HOST,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == "2.1.0"
    assert payload["runs"]

    run = payload["runs"][0]
    driver = run["tool"]["driver"]
    rule_ids = {rule["id"] for rule in driver["rules"]}
    assert "CHK-001" in rule_ids
    assert any(rule.get("help") for rule in driver["rules"])  # remediation exported

    sarif_result = next(res for res in run["results"] if res["ruleId"] == "CHK-001")
    assert sarif_result["level"] == "error"
    assert sarif_result["properties"]["status"] == "FAIL"
    assert "module" in sarif_result["properties"]
    assert run["properties"]["summary"]["checks_total"] == 3


def test_generate_junit_report(tmp_path):
    output = tmp_path / "report.junit.xml"
    generate_junit_report(
        SAMPLE_PROFILE,
        SAMPLE_RESULTS,
        str(output),
        summary=SAMPLE_SUMMARY,
        host_info=SAMPLE_HOST,
    )

    tree = ET.parse(Path(output))
    suite = tree.getroot()
    assert suite.tag == "testsuite"
    assert suite.attrib["tests"] == "3"
    assert suite.attrib["failures"] == "1"
    assert suite.attrib["skipped"] == "1"

    cases = {case.attrib["name"]: case for case in suite.findall("testcase")}
    failing_case = cases["Critical config is present"]
    failure_node = failing_case.find("failure")
    assert failure_node is not None
    assert "Создайте файл" in failure_node.text

    warn_case = cases["SSH banner configured"]
    assert warn_case.find("skipped") is not None

    pass_case = cases["Chrony service enabled"]
    system_out = pass_case.find("system-out")
    assert system_out is not None
    assert "chronyd enabled" in system_out.text
