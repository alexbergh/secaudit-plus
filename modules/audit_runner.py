# modules/audit_runner.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from secaudit.exceptions import MissingDependencyError

try:
    import yaml  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - runtime guard
    yaml = None  # type: ignore
    _YAML_IMPORT_ERROR = exc
else:  # pragma: no cover - exercised indirectly
    _YAML_IMPORT_ERROR = None
from json import JSONDecodeError
from packaging import version

from modules.bash_executor import run_bash, CommandError  # <= используем мягкий исполнитель


# ───────────────────────── Загрузка профиля ─────────────────────────

def load_profile(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Profile not found: {p}")
    if yaml is None:
        raise MissingDependencyError(
            package="PyYAML",
            import_name="yaml",
            instructions="pip install -r requirements.txt",
            original=_YAML_IMPORT_ERROR,
        )
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}  # type: ignore[union-attr]
    # Минимальная нормализация
    data.setdefault("profile_name", str(p.stem))
    data.setdefault("description", "")
    data.setdefault("checks", [])
    return data


# ───────────────────────── Исполнение проверок ─────────────────────────

def run_checks(
    profile: Dict[str, Any],
    selected_modules: List[str] | None = None,
    evidence_dir: str | Path | None = None,
) -> List[Dict[str, Any]]:
    """
    Выполняет проверки из профиля, опционально фильтруя по модулям и
    сохраняя выводы команд в каталоге доказательств.
    """

    module_filters = [m.lower() for m in (selected_modules or [])]
    evidence_path: Optional[Path] = None
    if evidence_dir:
        evidence_path = Path(evidence_dir)
        evidence_path.mkdir(parents=True, exist_ok=True)

    out: List[Dict[str, Any]] = []

    for check in profile.get("checks", []):
        module = str(check.get("module", "core"))
        if module_filters and module.lower() not in module_filters:
            continue

        res = _execute_check(check, evidence_path)
        out.append(res)

    return out


def _execute_check(check: Dict[str, Any], evidence_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Запускает одну проверку через run_bash и применяет assert-логику.
    Поддерживаем assert_type: exact | contains | not_contains | regexp |
    exit_code | jsonpath | version_gte | int_lte.
    """

    cmd: str = check["command"]
    expect_raw: Any = check.get("expect")
    assert_type: str = str(check.get("assert_type", "exact")).lower()
    timeout: int = int(check.get("timeout", 10))
    rc_ok_raw = check.get("rc_ok", (0, 1))
    try:
        rc_ok = tuple(int(x) for x in rc_ok_raw)  # type: ignore[arg-type]
    except TypeError:
        rc_ok = (0, 1)

    try:
        exec_res = run_bash(cmd, timeout=timeout, rc_ok=rc_ok)
        rc, stdout, stderr = exec_res.returncode, exec_res.stdout, exec_res.stderr
    except CommandError as e:
        rc = e.returncode if e.returncode is not None else 1
        stdout = getattr(e, "stdout", "")
        stderr = e.stderr
        evidence_file = _write_evidence(evidence_dir, check, stdout, stderr or "", rc)
        return {
            "id": check.get("id", ""),
            "name": check.get("name", ""),
            "module": check.get("module", "core"),
            "severity": check.get("severity", "low"),
            "tags": check.get("tags", {}),
            "command": cmd,
            "assert_type": assert_type,
            "expect": expect_raw,
            "rc": rc,
            "output": stdout if stdout else (stderr or "").strip(),
            "stderr": stderr,
            "result": "FAIL",
            "reason": str(e),
            "evidence": str(evidence_file) if evidence_file else None,
        }

    status, verdict_detail = _apply_assert(stdout, rc, expect_raw, assert_type, rc_ok)

    if rc == 124 and status == "FAIL":
        status = "UNDEF"
        if not verdict_detail:
            verdict_detail = "timeout"

    evidence_file = _write_evidence(evidence_dir, check, stdout, stderr or "", rc)

    return {
        "id": check.get("id", ""),
        "name": check.get("name", ""),
        "module": check.get("module", "core"),
        "severity": check.get("severity", "low"),
        "tags": check.get("tags", {}),
        "command": cmd,
        "assert_type": assert_type,
        "expect": expect_raw,
        "rc": rc,
        "output": stdout if stdout else (stderr or "").strip(),
        "stderr": stderr,
        "result": status,
        "reason": verdict_detail,
        "evidence": str(evidence_file) if evidence_file else None,
    }


def _parse_jsonpath(expr: str) -> List[Any]:
    """Простейший парсер JSONPath-подобных выражений."""

    if not expr:
        raise ValueError("empty expression")
    expr = expr.strip()
    if not expr.startswith("$"):
        raise ValueError("expression must start with '$'")

    tokens: List[Any] = []
    i = 1
    length = len(expr)
    while i < length:
        char = expr[i]
        if char.isspace():
            i += 1
            continue
        if char == '.':
            i += 1
            start = i
            while i < length and expr[i] not in '.[':
                i += 1
            if start == i:
                raise ValueError("empty attribute name")
            token = expr[start:i].strip()
            if not token:
                raise ValueError("empty attribute name")
            tokens.append(token)
            continue
        if char == '[':
            i += 1
            if i >= length:
                raise ValueError("unterminated '[' segment")
            if expr[i] in "'\"":
                quote = expr[i]
                i += 1
                start = i
                while i < length and expr[i] != quote:
                    if expr[i] == "\\" and i + 1 < length:
                        i += 2
                    else:
                        i += 1
                if i >= length:
                    raise ValueError("unterminated quoted token")
                token = expr[start:i]
                i += 1
                while i < length and expr[i].isspace():
                    i += 1
                if i >= length or expr[i] != ']':
                    raise ValueError("missing closing bracket")
                i += 1
                tokens.append(token)
                continue
            start = i
            while i < length and expr[i] != ']':
                i += 1
            if i >= length:
                raise ValueError("missing closing bracket")
            token = expr[start:i].strip()
            i += 1
            if not token:
                raise ValueError("empty bracket token")
            if token == "*":
                tokens.append("*")
            elif re.fullmatch(r"-?\d+", token):
                tokens.append(int(token))
            else:
                tokens.append(token)
            continue
        raise ValueError(f"unexpected character '{char}'")
    return tokens


def _jsonpath_values(data: Any, expr: str) -> List[Any]:
    """Возвращает список значений по упрощённому JSONPath."""

    tokens = _parse_jsonpath(expr)
    current: List[Any] = [data]
    for token in tokens:
        next_values: List[Any] = []
        for item in current:
            if token == "*":
                if isinstance(item, dict):
                    next_values.extend(item.values())
                elif isinstance(item, (list, tuple)):
                    next_values.extend(list(item))
                continue
            if isinstance(token, int):
                if isinstance(item, (list, tuple)):
                    idx = token
                    if -len(item) <= idx < len(item):
                        next_values.append(item[idx])
                continue
            if isinstance(item, dict) and token in item:
                next_values.append(item[token])
        current = next_values
    return current


def _apply_assert(stdout: str, rc: int, expect: Any, assert_type: str, rc_ok: Tuple[int, ...]) -> Tuple[str, str]:
    """
    Возвращает кортеж (result, reason).
    result: PASS|FAIL по проверке (до обработки таймаута в _execute_check)
    reason: краткое пояснение
    """

    out = stdout.strip()

    if rc not in rc_ok:
        return "FAIL", f"rc={rc} not in {rc_ok}"

    if assert_type == "exact":
        expected = "" if expect is None else str(expect)
        return ("PASS", "exact match") if out == expected else ("FAIL", f"got '{out}' != expect '{expected}'")

    if assert_type == "contains":
        needle = "" if expect is None else str(expect)
        return ("PASS", "contains") if needle in out else ("FAIL", f"'{needle}' not found")

    if assert_type == "not_contains":
        needle = "" if expect is None else str(expect)
        return ("PASS", "not contains") if needle not in out else ("FAIL", f"'{needle}' unexpectedly found")

    if assert_type == "regexp":
        pattern = "" if expect is None else str(expect)
        try:
            pat = re.compile(pattern, re.MULTILINE)
        except re.error as e:
            return "FAIL", f"bad regexp: {e}"
        return ("PASS", "regexp match") if pat.search(out) else ("FAIL", "regexp no match")

    if assert_type == "exit_code":
        if expect in (None, ""):
            return ("PASS", "rc==0") if rc == 0 else ("FAIL", f"rc={rc}")
        expect_str = str(expect)
        if expect_str.isdigit():
            return ("PASS", "rc==expect") if int(expect_str) == rc else ("FAIL", f"rc={rc} != {expect_str}")
        try:
            pat = re.compile(expect_str)
            return ("PASS", "rc~regexp") if pat.fullmatch(str(rc)) else ("FAIL", f"rc={rc} !~ /{expect_str}/")
        except re.error as e:
            return "FAIL", f"bad rc regexp: {e}"

    if assert_type == "jsonpath":
        if not isinstance(expect, dict):
            return "FAIL", "jsonpath expect must be mapping"
        path_expr = expect.get("path")
        if not isinstance(path_expr, str) or not path_expr.strip():
            return "FAIL", "jsonpath requires 'path'"
        try:
            data = json.loads(stdout)
        except JSONDecodeError as exc:
            return "FAIL", f"json decode error: {exc.msg}"
        try:
            matches = _jsonpath_values(data, path_expr)
        except ValueError as exc:
            return "FAIL", f"bad jsonpath: {exc}"
        if "value" in expect:
            expected_value = expect.get("value")
            if any(match == expected_value for match in matches):
                return "PASS", "jsonpath value match"
            return "FAIL", "jsonpath value mismatch"
        if "contains" in expect:
            target = expect.get("contains")
            for match in matches:
                if isinstance(match, (list, tuple, set)) and target in match:
                    return "PASS", "jsonpath contains"
                if isinstance(match, str) and str(target) in match:
                    return "PASS", "jsonpath contains"
            return "FAIL", "jsonpath contains mismatch"
        exists_flag = expect.get("exists", True)
        if exists_flag:
            return ("PASS", "jsonpath exists") if matches else ("FAIL", "jsonpath no match")
        return ("PASS", "jsonpath absent") if not matches else ("FAIL", "jsonpath should be absent")

    if assert_type == "version_gte":
        if expect in (None, ""):
            return "FAIL", "version_gte requires expect"
        expected_version = str(expect).strip()
        try:
            expected_parsed = version.parse(expected_version)
        except Exception as exc:  # pragma: no cover - defensive
            return "FAIL", f"bad version expect: {exc}"
        match = re.search(r"\d+(?:\.\d+)*", out)
        if not match:
            return "FAIL", "no version found"
        actual_str = match.group(0)
        try:
            actual_parsed = version.parse(actual_str)
        except Exception as exc:  # pragma: no cover - defensive
            return "FAIL", f"bad version output: {exc}"
        if actual_parsed >= expected_parsed:
            return "PASS", f"version {actual_str} >= {expected_version}"
        return "FAIL", f"version {actual_str} < {expected_version}"

    if assert_type == "int_lte":
        if expect in (None, ""):
            return "FAIL", "int_lte requires expect"
        try:
            threshold = int(expect)
        except (TypeError, ValueError):
            return "FAIL", "invalid int expect"
        match = re.search(r"-?\d+", out)
        if not match:
            return "FAIL", "no integer found"
        actual = int(match.group(0))
        if actual <= threshold:
            return "PASS", f"{actual} <= {threshold}"
        return "FAIL", f"{actual} > {threshold}"

    if assert_type == "set_allowlist":
        if expect in (None, ""):
            return "FAIL", "set_allowlist requires file path"
        allowlist_path = Path(str(expect)).expanduser()
        if not allowlist_path.exists():
            return "FAIL", f"allowlist not found: {allowlist_path}"
        try:
            allowed_raw = allowlist_path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - defensive
            return "FAIL", f"allowlist read error: {exc}"
        allowed = {
            line.strip()
            for line in allowed_raw.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        actual = {line.strip() for line in out.splitlines() if line.strip()}
        unexpected = sorted(actual - allowed)
        if unexpected:
            preview = ", ".join(unexpected[:5])
            if len(unexpected) > 5:
                preview += ", …"
            return "FAIL", f"unexpected entries: {preview}"
        missing = sorted(allowed - actual)
        if missing:
            preview = ", ".join(missing[:5])
            if len(missing) > 5:
                preview += ", …"
            return "PASS", f"subset (missing: {preview})"
        return "PASS", "allowlist match"

    return "FAIL", f"unsupported assert_type '{assert_type}'"


def _sanitize_check_id(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value or "check")
    return sanitized[:80] if sanitized else "check"


def _write_evidence(
    evidence_dir: Optional[Path],
    check: Dict[str, Any],
    stdout: str,
    stderr: str,
    rc: int,
) -> Optional[Path]:
    if evidence_dir is None:
        return None

    base_name = _sanitize_check_id(str(check.get("id") or check.get("name") or "check"))
    path = evidence_dir / f"{base_name}.txt"
    counter = 1
    while path.exists():
        path = evidence_dir / f"{base_name}_{counter}.txt"
        counter += 1

    with path.open("w", encoding="utf-8") as handle:
        handle.write(f"# Check: {check.get('id', '')}\n")
        handle.write(f"# Name: {check.get('name', '')}\n")
        handle.write(f"# Module: {check.get('module', 'core')}\n")
        handle.write(f"# Command: {check.get('command', '')}\n")
        handle.write(f"# Return code: {rc}\n\n")
        if stdout:
            handle.write("[stdout]\n")
            handle.write(stdout.rstrip("\n") + "\n")
        if stderr:
            handle.write("\n[stderr]\n")
            handle.write(stderr.rstrip("\n") + "\n")

    return path
