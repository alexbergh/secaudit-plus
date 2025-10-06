import json
import textwrap
from pathlib import Path

import pytest

from modules.audit_runner import _apply_assert, run_checks
from modules.cli import parse_tag_filters


def test_apply_assert_int_lte_pass_and_fail():
    ok, reason = _apply_assert("current: 5", 0, 10, "int_lte", (0,))
    assert ok == "PASS"
    assert "<=" in reason

    status, reason = _apply_assert("value=42", 0, 10, "int_lte", (0,))
    assert status == "FAIL"
    assert ">" in reason


def test_apply_assert_version_gte():
    stdout = "OpenSSH_9.3p1"
    status, reason = _apply_assert(stdout, 0, "9.0", "version_gte", (0,))
    assert status == "PASS"
    assert "9.3" in reason

    status, reason = _apply_assert("tool 1.2", 0, "2.0", "version_gte", (0,))
    assert status == "FAIL"
    assert "1.2" in reason


def test_apply_assert_jsonpath_value():
    payload = json.dumps({"meta": {"enabled": True, "threshold": 5}})
    status, reason = _apply_assert(
        payload,
        0,
        {"path": "$.meta.threshold", "value": 5},
        "jsonpath",
        (0,),
    )
    assert status == "PASS"
    assert "jsonpath value" in reason

    status, reason = _apply_assert(
        payload,
        0,
        {"path": "$.meta.enabled", "value": False},
        "jsonpath",
        (0,),
    )
    assert status == "FAIL"
    assert "mismatch" in reason


def test_apply_assert_jsonpath_contains_and_bad_path():
    payload = json.dumps({"items": [{"name": "alpha"}, {"name": "beta"}]})
    status, reason = _apply_assert(
        payload,
        0,
        {"path": "$.items[*].name", "contains": "beta"},
        "jsonpath",
        (0,),
    )
    assert status == "PASS"
    assert "contains" in reason

    status, reason = _apply_assert(
        payload,
        0,
        {"path": "items.name", "exists": True},
        "jsonpath",
        (0,),
    )
    assert status == "FAIL"
    assert "bad jsonpath" in reason


def test_apply_assert_set_allowlist(tmp_path: Path):
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("alpha\nbeta\n#comment\n", encoding="utf-8")

    stdout = "alpha\nbeta\n"
    status, reason = _apply_assert(stdout, 0, str(allowlist), "set_allowlist", (0,))
    assert status == "PASS"
    assert "allowlist" in reason.lower() or "subset" in reason.lower()

    stdout = "alpha\ngamma\n"
    status, reason = _apply_assert(stdout, 0, str(allowlist), "set_allowlist", (0,))
    assert status == "FAIL"
    assert "unexpected" in reason


def test_parse_tag_filters_roundtrip():
    filters = parse_tag_filters(["FSTEC=УПД.7", "cis=5.2"])
    assert filters == {"fstec": "упд.7", "cis": "5.2"}

    with pytest.raises(ValueError):
        parse_tag_filters(["invalid-filter"])


def test_run_checks_evidence(tmp_path: Path):
    profile = {
        "checks": [
            {
                "id": "demo/id",
                "name": "Echo test",
                "module": "system",
                "command": "printf 'yes'",
                "expect": "yes",
                "assert_type": "exact",
                "severity": "low",
                "tags": {"fstec": ["TEST"]},
            }
        ]
    }

    outcome = run_checks(profile, selected_modules=["SYSTEM"], evidence_dir=tmp_path)
    results = outcome.results
    summary = outcome.summary

    assert len(results) == 1

    result = results[0]
    assert result["result"] == "PASS"
    assert result["evidence"]

    evidence_path = Path(result["evidence"])
    assert evidence_path.exists()
    content = evidence_path.read_text(encoding="utf-8")
    assert "Command" in content and "yes" in content
    assert evidence_path.name.startswith("demo_id")

    assert summary["score"] == pytest.approx(100.0)
    assert summary["status_counts"]["PASS"] == 1


def test_run_checks_extends_and_variables(tmp_path: Path):
    parent_yaml = textwrap.dedent(
        """
        schema_version: 1
        profile_name: parent
        description: Parent profile
        vars:
          defaults:
            FOO: parent
            BAR: base
        checks:
          - id: parent-check
            module: system
            command: "printf '{{ FOO }}'"
            expect: "{{ FOO }}"
        """
    )
    parent_path = tmp_path / "parent.yml"
    parent_path.write_text(parent_yaml, encoding="utf-8")

    profile = {
        "schema_version": 1,
        "profile_name": "child",
        "description": "Child profile",
        "extends": [parent_path.name],
        "vars": {
            "levels": {
                "strict": {"BAR": "strict-value"},
            }
        },
        "checks": [
            {
                "id": "child-check",
                "module": "system",
                "command": "printf '{{ BAR }}'",
                "expect": "{{ BAR }}",
            }
        ],
    }

    outcome = run_checks(
        profile,
        level="strict",
        variables_override={"FOO": "override"},
        profile_path=tmp_path / "child.yml",
    )

    results = {entry["id"]: entry for entry in outcome.results}

    assert results["parent-check"]["result"] == "PASS"
    assert results["parent-check"]["output"].strip() == "override"

    assert results["child-check"]["result"] == "PASS"
    assert results["child-check"]["output"].strip() == "strict-value"

    assert outcome.summary["status_counts"]["PASS"] == 2


def test_run_checks_fact_caching(monkeypatch):
    calls = []

    def fake_run_bash(command: str, timeout: int, rc_ok):  # type: ignore[override]
        calls.append(command)

        class _Result:
            returncode = 0
            stdout = "cached"
            stderr = ""

        return _Result()

    monkeypatch.setattr("modules.audit_runner.run_bash", fake_run_bash)

    profile = {
        "schema_version": 1,
        "profile_name": "cache",
        "description": "",
        "facts": [
            {"id": "shared", "command": "printf 'cached'", "cache": True},
            {"id": "duplicate", "command": "printf 'cached'", "cache": True},
        ],
        "checks": [
            {
                "id": "fact-check",
                "module": "system",
                "use_fact": "shared",
                "asserts": [{"contains": "cached"}],
            }
        ],
    }

    outcome = run_checks(profile)

    assert calls == ["printf 'cached'"]

    result = outcome.results[0]
    assert result["result"] == "PASS"
    assert result["cached"] is True
    assert result["fact"] == "shared"
    assert "cached" in result["output"]
