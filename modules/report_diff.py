from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

_STATUS_RANK: Dict[str, int] = {"PASS": 0, "WARN": 1, "FAIL": 2, "UNDEF": 3, "ERROR": 3}


def _canonical_status(value: Any) -> str:
    if value is None:
        return "UNDEF"
    text = str(value).strip().upper()
    if not text:
        return "UNDEF"
    if text in {"OK", "SUCCESS"}:
        return "PASS"
    if text in {"WARNING", "WARN"}:
        return "WARN"
    if text in {"FAILED", "FAIL", "ERROR"}:
        return "FAIL"
    if text in {"UNDEFINED", "UNKNOWN"}:
        return "UNDEF"
    return text


def _status_rank(status: str) -> int:
    return _STATUS_RANK.get(status, 3)


def _result_key(record: Mapping[str, Any], fallback_index: int) -> str:
    check_id = record.get("id") or record.get("check_id")
    if check_id:
        return str(check_id)
    name = record.get("name")
    if name:
        return f"name:{name}"
    return f"idx:{fallback_index}"


def _flatten_results(payload: Mapping[str, Any]) -> Tuple[List[Mapping[str, Any]], Mapping[str, Any]]:
    if "results" in payload and isinstance(payload["results"], list):
        return payload["results"], payload.get("summary", {})

    modules = payload.get("modules")
    if isinstance(modules, Mapping):
        aggregated: List[Mapping[str, Any]] = []
        for module_checks in modules.values():
            if isinstance(module_checks, list):
                aggregated.extend(item for item in module_checks if isinstance(item, Mapping))
        return aggregated, payload.get("summary", {})

    raise ValueError("Report payload does not contain a 'results' list or 'modules' mapping")


@dataclass
class _DiffEntry:
    id: str
    name: str
    before: str
    after: str
    severity: str | None = None
    reason: str | None = None
    previous_reason: str | None = None

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "before": self.before,
            "after": self.after,
        }
        if self.severity is not None:
            payload["severity"] = self.severity
        if self.reason:
            payload["reason"] = self.reason
        if self.previous_reason:
            payload["previous_reason"] = self.previous_reason
        return payload


def _index_results(results: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    indexed: Dict[str, Mapping[str, Any]] = {}
    for idx, record in enumerate(results):
        if not isinstance(record, Mapping):
            continue
        key = _result_key(record, idx)
        indexed[key] = record
    return indexed


def compare_reports(before_path: str | Path, after_path: str | Path, *, fail_only: bool = False) -> Dict[str, Any]:
    before_payload = json.loads(Path(before_path).read_text(encoding="utf-8"))
    after_payload = json.loads(Path(after_path).read_text(encoding="utf-8"))

    before_results, before_summary = _flatten_results(before_payload)
    after_results, after_summary = _flatten_results(after_payload)

    before_index = _index_results(before_results)
    after_index = _index_results(after_results)

    regressions: List[_DiffEntry] = []
    improvements: List[_DiffEntry] = []
    new_checks: List[_DiffEntry] = []
    removed_checks: List[_DiffEntry] = []
    unchanged = 0

    for key, after_record in after_index.items():
        after_status = _canonical_status(after_record.get("result"))
        before_record = before_index.pop(key, None)
        if before_record is None:
            if fail_only and after_status not in {"FAIL", "UNDEF"}:
                continue
            new_checks.append(
                _DiffEntry(
                    id=str(after_record.get("id") or after_record.get("name") or key),
                    name=str(after_record.get("name") or after_record.get("id") or key),
                    before="<missing>",
                    after=after_status,
                    severity=after_record.get("severity"),
                    reason=after_record.get("reason"),
                )
            )
            continue

        before_status = _canonical_status(before_record.get("result"))
        before_rank = _status_rank(before_status)
        after_rank = _status_rank(after_status)

        if after_rank > before_rank:
            if fail_only and after_status not in {"FAIL", "UNDEF"}:
                continue
            regressions.append(
                _DiffEntry(
                    id=str(after_record.get("id") or after_record.get("name") or key),
                    name=str(after_record.get("name") or before_record.get("name") or key),
                    before=before_status,
                    after=after_status,
                    severity=after_record.get("severity") or before_record.get("severity"),
                    reason=after_record.get("reason"),
                    previous_reason=before_record.get("reason"),
                )
            )
        elif after_rank < before_rank:
            improvements.append(
                _DiffEntry(
                    id=str(after_record.get("id") or after_record.get("name") or key),
                    name=str(after_record.get("name") or before_record.get("name") or key),
                    before=before_status,
                    after=after_status,
                    severity=after_record.get("severity") or before_record.get("severity"),
                    reason=after_record.get("reason"),
                    previous_reason=before_record.get("reason"),
                )
            )
        else:
            unchanged += 1

    for key, before_record in before_index.items():
        before_status = _canonical_status(before_record.get("result"))
        if fail_only and before_status not in {"FAIL", "UNDEF"}:
            continue
        removed_checks.append(
            _DiffEntry(
                id=str(before_record.get("id") or before_record.get("name") or key),
                name=str(before_record.get("name") or before_record.get("id") or key),
                before=before_status,
                after="<removed>",
                severity=before_record.get("severity"),
                reason=before_record.get("reason"),
            )
        )

    summary: Dict[str, Any] = {
        "before_score": before_summary.get("score"),
        "after_score": after_summary.get("score"),
        "before_status_counts": before_summary.get("status_counts"),
        "after_status_counts": after_summary.get("status_counts"),
        "regressions": len(regressions),
        "improvements": len(improvements),
        "new": len(new_checks),
        "removed": len(removed_checks),
        "unchanged": unchanged,
    }
    if summary["before_score"] is not None and summary["after_score"] is not None:
        try:
            summary["score_delta"] = summary["after_score"] - summary["before_score"]
        except TypeError:
            pass

    return {
        "summary": summary,
        "regressions": [entry.as_dict() for entry in regressions],
        "improvements": [entry.as_dict() for entry in improvements],
        "new": [entry.as_dict() for entry in new_checks],
        "removed": [entry.as_dict() for entry in removed_checks],
    }


def format_report_diff(diff: Mapping[str, Any]) -> str:
    lines: List[str] = []
    summary = diff.get("summary", {})
    if summary:
        before_score = summary.get("before_score")
        after_score = summary.get("after_score")
        if before_score is not None or after_score is not None:
            lines.append(f"Score: {before_score} → {after_score} (Δ {summary.get('score_delta')})")
        lines.append(
            "Totals: "
            f"regressions={summary.get('regressions', 0)}, "
            f"improvements={summary.get('improvements', 0)}, "
            f"new={summary.get('new', 0)}, "
            f"removed={summary.get('removed', 0)}, "
            f"unchanged={summary.get('unchanged', 0)}"
        )

    def _render_section(title: str, items: Iterable[Mapping[str, Any]]) -> None:
        items = list(items)
        if not items:
            return
        lines.append(f"\n{title} ({len(items)}):")
        for entry in items:
            cid = entry.get("id")
            name = entry.get("name")
            before = entry.get("before")
            after = entry.get("after")
            severity = entry.get("severity")
            descriptor = f"{cid}: {before} → {after}"
            if severity:
                descriptor += f" [{severity}]"
            if name and name != cid:
                descriptor += f" — {name}"
            lines.append(f"  - {descriptor}")
            if entry.get("reason") and after == "FAIL":
                lines.append(f"      reason: {entry['reason']}")
            previous = entry.get("previous_reason")
            if previous and before == "FAIL" and previous != entry.get("reason"):
                lines.append(f"      was: {previous}")

    _render_section("Regressions", diff.get("regressions", []))
    _render_section("Improvements", diff.get("improvements", []))
    _render_section("New checks", diff.get("new", []))
    _render_section("Removed checks", diff.get("removed", []))

    return "\n".join(lines) if lines else "No differences detected."
