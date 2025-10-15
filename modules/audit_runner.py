# modules/audit_runner.py
from __future__ import annotations

import json
import os
import re
import shlex
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, Iterable

from secaudit.exceptions import MissingDependencyError


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    duration: float
    cpu_time: float
    error: str | None = None
    cached: bool = False
    timed_out: bool = False


@dataclass
class FactResult(CommandResult):
    id: str = ""
    command: str = ""


@dataclass
class AssertSpec:
    type: str
    value: Any = None
    params: Dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    on_fail: str | None = None


@dataclass
class AuditOutcome:
    results: List[Dict[str, Any]]
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    level: str
    variables: Dict[str, str]
    render_context: Dict[str, Any]
    os_release: Dict[str, str]
    base_dir: Path
    evidence_dir: Optional[Path] = None
    facts: Dict[str, FactResult] = field(default_factory=dict)
    command_cache: Dict[Any, CommandResult] = field(default_factory=dict)
    cache_lock: threading.Lock = field(default_factory=threading.Lock)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(os.path.expanduser(str(value)))
    if path.is_absolute():
        return path

    candidates = []
    if base_dir:
        candidates.append(base_dir / path)

    repo_candidate = PROJECT_ROOT / path
    if repo_candidate not in candidates:
        candidates.append(repo_candidate)

    cwd_candidate = Path.cwd() / path
    if cwd_candidate not in candidates:
        candidates.append(cwd_candidate)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0] if candidates else path


def _load_env_file(path: Path, *, optional: bool = False) -> Dict[str, str]:
    result: Dict[str, str] = {}
    try:
        data = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if optional:
            return {}
        raise
    except OSError as exc:
        if optional:
            return {}
        raise RuntimeError(f"Не удалось прочитать файл переменных {path}: {exc}") from exc

    for raw_line in data.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith("\"") and value.endswith("\"")) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        result[key] = value
    return result


def _normalize_os_info(raw: Dict[str, str]) -> Dict[str, Any]:
    os_id = raw.get("ID", "").lower()
    os_like = raw.get("ID_LIKE", "")
    like_tokens = [token.strip().lower() for token in os_like.split() if token.strip()]
    return {
        "id": os_id,
        "version_id": raw.get("VERSION_ID", ""),
        "name": raw.get("NAME", ""),
        "pretty_name": raw.get("PRETTY_NAME", ""),
        "id_like": like_tokens,
        "raw": raw,
    }


def _build_variables(
    profile: Dict[str, Any],
    level: str,
    overrides: Dict[str, str],
    base_dir: Path,
) -> Dict[str, str]:
    vars_section = profile.get("vars", {})
    variables: Dict[str, str] = {}

    if isinstance(vars_section, dict):
        defaults = vars_section.get("defaults", {}) or {}
        if isinstance(defaults, dict):
            for key, value in defaults.items():
                variables[str(key)] = str(value)

        files: Iterable[Any] = vars_section.get("files", []) or []
        optional_files: Iterable[Any] = vars_section.get("optional_files", []) or []

        initial_context = {"level": level, "LEVEL": level}

        for raw_path in files:
            rendered = _render_template_string(str(raw_path), initial_context)
            path = _resolve_path(rendered, base_dir)
            variables.update(_load_env_file(path, optional=False))

        level_map = vars_section.get("levels", {}) or {}
        if isinstance(level_map, dict):
            level_values = level_map.get(level, {}) or {}
            if isinstance(level_values, dict):
                for key, value in level_values.items():
                    variables[str(key)] = str(value)

        for raw_path in optional_files:
            rendered = _render_template_string(str(raw_path), initial_context)
            path = _resolve_path(rendered, base_dir)
            try:
                variables.update(_load_env_file(path, optional=True))
            except FileNotFoundError:
                continue

    include_dir = PROJECT_ROOT / "profiles" / "include"
    default_vars = include_dir / f"vars_{level}.env"
    if default_vars.exists():
        variables.update(_load_env_file(default_vars, optional=True))

    for key, value in overrides.items():
        variables[str(key)] = str(value)

    return variables


TEMPLATE_PATTERN = re.compile(r"{{\s*([^{}]+?)\s*}}")


def _lookup_context_value(context: Dict[str, Any], token: str) -> Any:
    parts = [part.strip() for part in token.replace("[", ".").replace("]", "").split(".") if part.strip()]
    current: Any = context
    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
                continue
            lowered = part.lower()
            uppered = part.upper()
            if lowered in current:
                current = current[lowered]
                continue
            if uppered in current:
                current = current[uppered]
                continue
            return None
        else:
            return None
    return current


def _render_template_string(text: str, context: Dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        value = _lookup_context_value(context, token)
        if value is None:
            return match.group(0)
        return shlex.quote(str(value))

    return TEMPLATE_PATTERN.sub(repl, text)


def _build_render_context(
    variables: Dict[str, str],
    level: str,
    os_release: Dict[str, str],
) -> Dict[str, Any]:
    os_info = _normalize_os_info(os_release)
    context: Dict[str, Any] = {}
    context.update({k: str(v) for k, v in os_release.items()})
    context.update({k: str(v) for k, v in variables.items()})
    upper_vars = {str(k).upper(): str(v) for k, v in variables.items()}
    lower_vars = {str(k).lower(): str(v) for k, v in variables.items()}
    context.update(upper_vars)
    context.update(lower_vars)
    context["vars"] = {k: str(v) for k, v in variables.items()}
    context["level"] = level
    context["LEVEL"] = level
    context["os"] = os_info
    context["OS_ID"] = os_info.get("id", "")
    context["OS_VERSION_ID"] = os_info.get("version_id", "")
    context["env"] = dict(os.environ)
    return context


def _render_profile_data(data: Any, context: Dict[str, Any]) -> Any:
    if isinstance(data, str):
        return _render_template_string(data, context)
    if isinstance(data, list):
        return [_render_profile_data(item, context) for item in data]
    if isinstance(data, dict):
        return {key: _render_profile_data(value, context) for key, value in data.items()}
    return data


def _merge_profiles(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in overlay.items():
        if key == "checks" and isinstance(value, list):
            result.setdefault("checks", [])
            result["checks"].extend(value)
        elif key == "facts" and isinstance(value, list):
            result.setdefault("facts", [])
            result["facts"].extend(value)
        elif key == "vars" and isinstance(value, dict):
            target = result.setdefault("vars", {})
            if isinstance(target, dict):
                target.update(value)
            else:
                result["vars"] = value
        elif key == "meta" and isinstance(value, dict):
            target = result.setdefault("meta", {})
            if isinstance(target, dict):
                target.update(value)
            else:
                result["meta"] = value
        elif key == "extends":
            # already processed
            continue
        else:
            result[key] = value
    return result


def _expand_extends(profile: Dict[str, Any], base_dir: Path, seen: set[Path] | None = None) -> Dict[str, Any]:
    extends = profile.get("extends")
    if not extends:
        return profile
    if not isinstance(extends, (list, tuple)):
        extends = [extends]
    seen = set(seen or set())
    merged: Dict[str, Any] = {"checks": []}
    for ref in extends:
        ref_path = _resolve_path(ref, base_dir)
        if ref_path in seen:
            continue
        seen.add(ref_path)
        if yaml is None:
            raise MissingDependencyError(
                package="PyYAML",
                import_name="yaml",
                instructions="pip install -r requirements.txt",
                original=_YAML_IMPORT_ERROR,
            )
        ref_data = yaml.safe_load(ref_path.read_text(encoding="utf-8")) or {}
        if not isinstance(ref_data, dict):
            continue
        expanded = _expand_extends(ref_data, ref_path.parent, seen)
        merged = _merge_profiles(merged, expanded)
    overlay = dict(profile)
    overlay.pop("extends", None)
    merged = _merge_profiles(merged, overlay)
    return merged


def _prepare_execution_context(
    profile: Dict[str, Any],
    *,
    level: str,
    overrides: Dict[str, str] | None,
    profile_path: str | Path | None,
    evidence_dir: str | Path | None,
) -> tuple[Dict[str, Any], ExecutionContext]:
    base_dir = Path(profile_path).resolve().parent if profile_path else Path.cwd()
    profile = _expand_extends(profile, base_dir)
    os_release = read_os_release()
    variables = _build_variables(profile, level, overrides or {}, base_dir)
    render_context = _build_render_context(variables, level, os_release)
    rendered_profile = _render_profile_data(profile, render_context)

    evidence_path: Optional[Path] = None
    if evidence_dir:
        evidence_path = Path(evidence_dir)
        evidence_path.mkdir(parents=True, exist_ok=True)

    context = ExecutionContext(
        level=level,
        variables={k: str(v) for k, v in variables.items()},
        render_context=render_context,
        os_release=os_release,
        base_dir=base_dir,
        evidence_dir=evidence_path,
    )

    return rendered_profile, context


def _normalize_rc_ok(value: Any) -> Tuple[int, ...]:
    if value is None:
        return (0, 1)
    if isinstance(value, (list, tuple, set)):
        values: List[int] = []
        for item in value:
            try:
                values.append(int(item))
            except (TypeError, ValueError):
                continue
        return tuple(values) if values else (0, 1)
    try:
        return (int(value),)
    except (TypeError, ValueError):
        return (0, 1)


def _run_command(
    command: str,
    *,
    timeout: int,
    rc_ok: Tuple[int, ...],
    context: ExecutionContext,
    cache_enabled: bool = False,
) -> CommandResult:
    cache_key = None
    if cache_enabled:
        cache_key = (command, timeout, rc_ok)
        with context.cache_lock:
            cached = context.command_cache.get(cache_key)
            if cached is not None:
                return replace(cached, cached=True)

    start = time.perf_counter()
    cpu_start = time.process_time()
    try:
        completed = run_bash(command, timeout=timeout, rc_ok=rc_ok)
        rc = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        error = None
        timed_out = False
    except CommandError as exc:
        rc = exc.returncode if exc.returncode is not None else 124
        stdout = getattr(exc, "stdout", "") or ""
        stderr = exc.stderr or ""
        error = str(exc)
        timed_out = exc.returncode is None
    duration = time.perf_counter() - start
    cpu_time = time.process_time() - cpu_start

    result = CommandResult(
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
        duration=duration,
        cpu_time=cpu_time,
        error=error,
        timed_out=timed_out,
    )

    if cache_key is not None:
        with context.cache_lock:
            context.command_cache[cache_key] = result

    return result


def _collect_facts(profile: Dict[str, Any], context: ExecutionContext) -> Dict[str, FactResult]:
    results: Dict[str, FactResult] = {}
    facts = profile.get("facts", []) or []
    if not isinstance(facts, list):
        return results

    for raw_fact in facts:
        if not isinstance(raw_fact, dict):
            continue
        fact_id = str(raw_fact.get("id", "")).strip()
        if not fact_id:
            continue

        command = raw_fact.get("command")
        if not command:
            path_value = raw_fact.get("path")
            if path_value:
                path = _resolve_path(str(path_value), context.base_dir)
                try:
                    stdout = path.read_text(encoding="utf-8")
                    fact_result = FactResult(
                        id=fact_id,
                        command=f"cat {path}",
                        stdout=stdout,
                        stderr="",
                        returncode=0,
                        duration=0.0,
                        cpu_time=0.0,
                    )
                except OSError as exc:
                    fact_result = FactResult(
                        id=fact_id,
                        command=str(path),
                        stdout="",
                        stderr=str(exc),
                        returncode=1,
                        duration=0.0,
                        cpu_time=0.0,
                        error=str(exc),
                    )
                results[fact_id] = fact_result
            continue

        timeout = int(raw_fact.get("timeout", 30))
        rc_ok = _normalize_rc_ok(raw_fact.get("rc_ok", (0, 1)))
        cache_enabled = bool(raw_fact.get("cache", False))
        cmd_result = _run_command(
            str(command),
            timeout=timeout,
            rc_ok=rc_ok,
            context=context,
            cache_enabled=cache_enabled,
        )
        fact_result = FactResult(
            id=fact_id,
            command=str(command),
            stdout=cmd_result.stdout,
            stderr=cmd_result.stderr,
            returncode=cmd_result.returncode,
            duration=cmd_result.duration,
            cpu_time=cmd_result.cpu_time,
            error=cmd_result.error,
            cached=cmd_result.cached,
            timed_out=cmd_result.timed_out,
        )
        results[fact_id] = fact_result

    return results


def _normalize_output(text: str, options: Any) -> str:
    if not text:
        return text
    if not options:
        return text

    config: Dict[str, Any]
    if options is True:
        config = {
            "strip_comments": True,
            "collapse_spaces": True,
            "trim": True,
            "drop_blank": True,
        }
    elif isinstance(options, (list, tuple, set)):
        config = {str(opt): True for opt in options}
    elif isinstance(options, dict):
        config = options
    else:
        return text

    lines = text.splitlines()
    normalized: List[str] = []
    seen: set[str] = set()
    for line in lines:
        if config.get("strip_comments"):
            line = re.sub(r"#.*$", "", line)
        if config.get("trim"):
            line = line.strip()
        if config.get("collapse_spaces") or config.get("unify_whitespace"):
            line = " ".join(line.split())
        if config.get("lowercase"):
            line = line.lower()
        if config.get("uppercase"):
            line = line.upper()
        if config.get("drop_blank") and not line:
            continue
        if config.get("unique"):
            key = line
            if key in seen:
                continue
            seen.add(key)
        normalized.append(line)

    if config.get("sort_unique"):
        normalized = sorted(set(normalized))
    elif config.get("sort"):
        normalized = sorted(normalized)

    return "\n".join(normalized)


VALID_STATUSES = {"PASS", "FAIL", "WARN", "UNDEF", "SKIP"}


def _normalize_status(value: Any, default: Optional[str] = None) -> Optional[str]:
    if value is None:
        return default
    text = str(value).strip().upper()
    if text in VALID_STATUSES:
        return text
    return default


def _parse_assert_entry(entry: Any) -> List[AssertSpec]:
    specs: List[AssertSpec] = []
    if entry is None:
        return specs
    if isinstance(entry, str):
        specs.append(AssertSpec(type="regexp", value=entry))
        return specs
    if not isinstance(entry, dict):
        return specs

    message = entry.get("message")
    on_fail = _normalize_status(entry.get("on_fail"))

    if "type" in entry:
        type_name = str(entry.get("type", "")).strip().lower()
        value = entry.get("value")
        if value is None:
            value = entry.get("expect")
        params = {
            key: val
            for key, val in entry.items()
            if key not in {"type", "value", "expect", "message", "on_fail"}
        }
        specs.append(AssertSpec(type=type_name, value=value, params=params, message=message, on_fail=on_fail))
        return specs

    mapping = {
        "regexp": "regexp",
        "not_regexp": "not_regexp",
        "contains": "contains",
        "not_contains": "not_contains",
        "exact": "exact",
        "exit_code": "exit_code",
        "jsonpath": "jsonpath",
        "version_gte": "version_gte",
        "int_lte": "int_lte",
        "custom_allowlist_file": "allowlist",
        "allowlist": "allowlist",
        "allowlist_file": "allowlist",
        "set_allowlist": "allowlist",
        "custom_denylist_file": "denylist",
        "denylist": "denylist",
    }

    for key, value in entry.items():
        if key in {"message", "on_fail", "mode", "allowlist_mode"}:
            continue
        mapped = mapping.get(key)
        if not mapped:
            continue
        params: Dict[str, Any] = {}
        if mapped == "allowlist":
            params["mode"] = (
                entry.get("mode")
                or entry.get("allowlist_mode")
                or (value.get("mode") if isinstance(value, dict) else None)
                or "subset"
            )
        specs.append(AssertSpec(type=mapped, value=value, params=params, message=message, on_fail=on_fail))

    return specs


def _collect_assertions(check: Dict[str, Any]) -> List[AssertSpec]:
    specs: List[AssertSpec] = []
    raw_asserts = check.get("asserts")
    if isinstance(raw_asserts, list):
        for item in raw_asserts:
            specs.extend(_parse_assert_entry(item))

    else:
        # Поддержка ключей assert, assert_2 и т.п.
        for key, value in sorted(check.items()):
            if not isinstance(key, str):
                continue
            if not key.startswith("assert"):
                continue
            if key == "assert_type":
                continue
            specs.extend(_parse_assert_entry(value))

    if not specs and ("expect" in check or "assert_type" in check):
        specs.append(
            AssertSpec(
                type=str(check.get("assert_type", "exact")).strip().lower(),
                value=check.get("expect"),
            )
        )

    return specs


@dataclass
class _PrioritizedEntry:
    priority: int
    include: bool


class _PrioritizedSet:
    """Helper that keeps only the highest-priority decision for every entry."""

    def __init__(self) -> None:
        self._entries: Dict[str, _PrioritizedEntry] = {}

    def apply(self, value: str, *, priority: int, include: bool) -> None:
        normalized = str(value).strip()
        if not normalized:
            return
        current = self._entries.get(normalized)
        if current is None or priority >= current.priority:
            self._entries[normalized] = _PrioritizedEntry(priority=priority, include=include)

    def finalize(self) -> List[str]:
        return sorted(key for key, entry in self._entries.items() if entry.include)


def _normalize_priority(raw: Any, default: int = 0) -> int:
    try:
        if raw is None:
            return default
        return int(raw)
    except (TypeError, ValueError):
        return default


def _normalize_include_flag(raw: Any, default: bool = True) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text in {"allow", "include", "add", "keep", "true", "1"}:
        return True
    if text in {"deny", "remove", "exclude", "drop", "false", "0", "block"}:
        return False
    return default


def _read_reference_file(value: Any, base_dir: Path) -> Tuple[List[str], Optional[str]]:
    path = _resolve_path(str(value), base_dir)
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], f"reference file not found: {path}"
    except OSError as exc:
        return [], f"reference read error: {exc}"
    entries = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return entries, None


def _load_reference_list(value: Any, base_dir: Path) -> Tuple[List[str], Optional[str]]:
    if value is None:
        return [], "empty reference"

    errors: List[str] = []
    prioritized = _PrioritizedSet()

    def _apply_entries(entries: Iterable[str], *, priority: int, include: bool) -> None:
        for entry in entries:
            prioritized.apply(entry, priority=priority, include=include)

    def _handle_node(node: Any, *, priority: int, include: bool) -> None:
        if node is None:
            return
        if isinstance(node, (list, tuple, set)):
            if node and all(isinstance(item, str) for item in node):
                _apply_entries([str(item).strip() for item in node], priority=priority, include=include)
                return
            for item in node:
                _handle_node(item, priority=priority, include=include)
            return
        if isinstance(node, dict):
            local_priority = _normalize_priority(node.get("priority"), priority)
            local_include = include
            for key in ("include", "effect", "action"):
                if key in node:
                    local_include = _normalize_include_flag(node.get(key), include)
                    break

            if "sources" in node and isinstance(node["sources"], (list, tuple, set)):
                for item in node["sources"]:
                    _handle_node(item, priority=local_priority, include=local_include)
            values_to_include: List[str] = []

            for key in ("values", "allow", "entries"):
                if key in node:
                    raw_values = node[key]
                    if isinstance(raw_values, (list, tuple, set)):
                        values_to_include.extend(str(item).strip() for item in raw_values)
                    elif raw_values is not None:
                        values_to_include.append(str(raw_values).strip())

            if "value" in node and node["value"] is not None:
                values_to_include.append(str(node["value"]).strip())

            file_key = None
            for key in ("file", "path", "allowlist", "denylist"):
                if key in node and node[key]:
                    file_key = node[key]
                    break
            if file_key is not None:
                file_entries, error = _read_reference_file(file_key, base_dir)
                if error:
                    errors.append(error)
                else:
                    values_to_include.extend(file_entries)

            for key in ("remove", "exclude"):
                if key in node:
                    raw_remove = node[key]
                    items = raw_remove if isinstance(raw_remove, (list, tuple, set)) else [raw_remove]
                    for item in items:
                        prioritized.apply(str(item), priority=local_priority, include=False)

            if values_to_include:
                _apply_entries(values_to_include, priority=local_priority, include=local_include)
            return

        if isinstance(node, str):
            entries, error = _read_reference_file(node, base_dir)
            if error:
                errors.append(error)
                return
            _apply_entries(entries, priority=priority, include=include)
            return

        # Fallback: treat as string representation
        prioritized.apply(str(node), priority=priority, include=include)

    _handle_node(value, priority=0, include=True)

    if errors:
        unique_errors = list(dict.fromkeys(errors))
        return [], "; ".join(unique_errors)

    return prioritized.finalize(), None


def _evaluate_single_assert(
    stdout: str,
    rc: int,
    spec: AssertSpec,
    rc_ok: Tuple[int, ...],
    context: ExecutionContext,
) -> Tuple[str, str]:
    assert_type = spec.type
    expect = spec.value
    out = stdout.strip()

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
        except re.error as exc:
            return "FAIL", f"bad regexp: {exc}"
        return ("PASS", "regexp match") if pat.search(out) else ("FAIL", "regexp no match")

    if assert_type == "not_regexp":
        pattern = "" if expect is None else str(expect)
        try:
            pat = re.compile(pattern, re.MULTILINE)
        except re.error as exc:
            return "FAIL", f"bad regexp: {exc}"
        return ("PASS", "regexp not found") if not pat.search(out) else ("FAIL", "pattern matched unexpectedly")

    if assert_type == "exit_code":
        if expect in (None, ""):
            return ("PASS", "rc==0") if rc == 0 else ("FAIL", f"rc={rc}")
        expect_str = str(expect)
        if expect_str.isdigit():
            return ("PASS", "rc==expect") if int(expect_str) == rc else ("FAIL", f"rc={rc} != {expect_str}")
        try:
            pat = re.compile(expect_str)
            return ("PASS", "rc~regexp") if pat.fullmatch(str(rc)) else ("FAIL", f"rc={rc} !~ /{expect_str}/")
        except re.error as exc:
            return "FAIL", f"bad rc regexp: {exc}"

    if assert_type == "jsonpath":
        if not isinstance(expect, dict):
            return "FAIL", "jsonpath expect must be mapping"
        path_expr = expect.get("path")
        if not isinstance(path_expr, str) or not path_expr.strip():
            return "FAIL", "jsonpath requires 'path'"
        try:
            data = json.loads(stdout or "{}")
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

    if assert_type in {"allowlist", "set_allowlist"}:
        values, error = _load_reference_list(expect, context.base_dir)
        if error:
            return "UNDEF", error
        allowed = {line.strip() for line in values if line.strip()}
        actual = {line.strip() for line in stdout.splitlines() if line.strip()}
        mode = str(spec.params.get("mode", "subset")).lower()
        if mode == "exact":
            if actual == allowed:
                return "PASS", "allowlist exact match"
            missing = allowed - actual
            unexpected = actual - allowed
            details = []
            if unexpected:
                preview = ", ".join(sorted(list(unexpected))[:5])
                details.append(f"unexpected: {preview}")
            if missing:
                preview = ", ".join(sorted(list(missing))[:5])
                details.append(f"missing: {preview}")
            return "FAIL", "; ".join(details) or "allowlist mismatch"
        unexpected = actual - allowed
        if unexpected:
            preview = ", ".join(sorted(list(unexpected))[:5])
            return "FAIL", f"unexpected entries: {preview}"
        missing = allowed - actual
        if missing:
            preview = ", ".join(sorted(list(missing))[:5])
            return "WARN", f"missing allowed entries: {preview}"
        return "PASS", "allowlist subset"

    if assert_type == "denylist":
        values, error = _load_reference_list(expect, context.base_dir)
        if error:
            return "UNDEF", error
        deny = {line.strip() for line in values if line.strip()}
        actual = {line.strip() for line in stdout.splitlines() if line.strip()}
        blocked = actual & deny
        if blocked:
            preview = ", ".join(sorted(list(blocked))[:5])
            return "FAIL", f"denylist hit: {preview}"
        return "PASS", "denylist clean"

    return "WARN", f"unsupported assert_type '{assert_type}'"


def _match_condition(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (list, tuple, set)):
        return any(_match_condition(actual, item) for item in expected)
    if isinstance(expected, dict):
        regex = expected.get("regexp")
        if regex:
            try:
                return re.search(regex, str(actual) if actual is not None else "") is not None
            except re.error:
                return False
        equals = expected.get("eq")
        if equals is not None:
            return _match_condition(actual, equals)
    if expected is None:
        return actual in (None, "")
    text = str(expected)
    if text.startswith("~"):
        try:
            return re.search(text[1:], str(actual) if actual is not None else "") is not None
        except re.error:
            return False
    if isinstance(actual, (list, tuple, set)):
        return any(_match_condition(item, expected) for item in actual)
    return str(actual).lower() == text.lower()


def _should_skip_check(check: Dict[str, Any], context: ExecutionContext) -> Tuple[bool, Optional[str]]:
    level_req = check.get("levels") or check.get("level")
    if level_req and not _match_condition(context.level, level_req):
        return True, "level not selected"

    os_id_req = check.get("os_id") or check.get("os")
    if os_id_req and not _match_condition(context.render_context.get("OS_ID", ""), os_id_req):
        return True, "os_id mismatch"

    os_like_req = check.get("os_like")
    if os_like_req:
        os_like = context.render_context.get("os", {}).get("id_like", [])
        if not _match_condition(os_like, os_like_req):
            return True, "os_like mismatch"

    version_req = check.get("os_version_id")
    if version_req and not _match_condition(context.render_context.get("OS_VERSION_ID", ""), version_req):
        return True, "os_version mismatch"

    when = check.get("when")
    if isinstance(when, dict):
        for key, expected in when.items():
            actual = _lookup_context_value(context.render_context, key) if isinstance(key, str) else None
            if not _match_condition(actual, expected):
                return True, f"when:{key}"
    elif isinstance(when, (list, tuple, set)):
        for clause in when:
            if isinstance(clause, dict):
                skip, reason = _should_skip_check({"when": clause}, context)
                if skip:
                    return True, reason

    return False, None


STATUS_PRIORITY = {"SKIP": -1, "PASS": 0, "WARN": 1, "FAIL": 2, "UNDEF": 3}


def _combine_status(current: str, new: str) -> str:
    if current not in STATUS_PRIORITY:
        current = "PASS"
    if new not in STATUS_PRIORITY:
        new = "WARN"
    if current == "SKIP":
        return new
    if new == "SKIP":
        return current
    return new if STATUS_PRIORITY[new] > STATUS_PRIORITY[current] else current


def _make_snippet(text: str, *, max_lines: int = 10, max_chars: int = 800) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    truncated = False
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    snippet = "\n".join(lines)
    if max_chars and len(snippet) > max_chars:
        snippet = snippet[:max_chars]
        truncated = True
    if truncated:
        if not snippet.endswith("…"):
            snippet = snippet.rstrip("\n") + "\n…"
    return snippet

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
from modules.os_detect import read_os_release
from seclib.validator import severity_rank


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
    *,
    profile_path: str | Path | None = None,
    level: str = "baseline",
    variables_override: Dict[str, str] | None = None,
    workers: int = 0,
) -> AuditOutcome:
    """Запускает проверки профиля с учётом уровня строгости и условий."""

    profile_copy = deepcopy(profile)
    rendered_profile, context = _prepare_execution_context(
        profile_copy,
        level=level,
        overrides=variables_override or {},
        profile_path=profile_path,
        evidence_dir=evidence_dir,
    )

    context.facts = _collect_facts(rendered_profile, context)

    checks = rendered_profile.get("checks", []) or []
    if not isinstance(checks, list):
        return AuditOutcome([], {"error": "profile.checks must be a list", "level": level})

    module_filters = [m.lower() for m in (selected_modules or []) if isinstance(m, str)]

    scheduled: List[Tuple[int, Dict[str, Any]]] = []
    results: List[Optional[Dict[str, Any]]] = [None] * len(checks)

    for idx, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        module = str(check.get("module", "core"))
        if module_filters and module.lower() not in module_filters:
            continue
        skip, reason = _should_skip_check(check, context)
        if skip:
            results[idx] = _build_skip_result(check, reason)
            continue
        scheduled.append((idx, check))

    max_workers = workers if isinstance(workers, int) and workers > 0 else min(32, (os.cpu_count() or 2) + 2)
    future_map: Dict[Any, int] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for idx, check in scheduled:
            future = pool.submit(_execute_check, check, context)
            future_map[future] = idx
        for future in as_completed(future_map):
            idx = future_map[future]
            check = checks[idx]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - defensive
                result = _build_error_result(check, context, exc)
            results[idx] = result

    final_results = [res for res in results if res is not None]
    summary = _calculate_summary(final_results, context)
    return AuditOutcome(results=final_results, summary=summary)


def _build_skip_result(check: Dict[str, Any], reason: Optional[str]) -> Dict[str, Any]:
    return {
        "id": check.get("id", ""),
        "name": check.get("name", ""),
        "module": check.get("module", "core"),
        "severity": str(check.get("severity", "low")).lower(),
        "tags": check.get("tags", {}),
        "command": check.get("command", ""),
        "rc": None,
        "output": "",
        "stderr": "",
        "result": "SKIP",
        "reason": reason or "skipped",
        "evidence": None,
        "weight": float(check.get("weight", 1.0) or 0.0),
        "duration": 0.0,
        "cpu_time": 0.0,
        "cached": False,
        "timed_out": False,
        "fact": check.get("use_fact") or check.get("fact"),
        "asserts": [],
        "ref": check.get("ref"),
        "remediation": check.get("remediation"),
        "evidence_snippet": "",
    }


def _build_error_result(check: Dict[str, Any], context: ExecutionContext, exc: Exception) -> Dict[str, Any]:
    reason = f"internal error: {exc}"
    return {
        "id": check.get("id", ""),
        "name": check.get("name", ""),
        "module": check.get("module", "core"),
        "severity": str(check.get("severity", "low")).lower(),
        "tags": check.get("tags", {}),
        "command": check.get("command", ""),
        "rc": None,
        "output": "",
        "stderr": "",
        "result": "UNDEF",
        "reason": reason,
        "evidence": None,
        "weight": float(check.get("weight", 1.0) or 0.0),
        "duration": 0.0,
        "cpu_time": 0.0,
        "cached": False,
        "timed_out": False,
        "fact": check.get("use_fact") or check.get("fact"),
        "asserts": [],
        "ref": check.get("ref"),
        "remediation": check.get("remediation"),
        "evidence_snippet": "",
    }


def _execute_check(check: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
    check_id = check.get("id", "")
    name = check.get("name", "")
    module = str(check.get("module", "core"))
    severity = str(check.get("severity", "low")).lower()
    weight = float(check.get("weight", 1.0) or 0.0)
    rc_ok = _normalize_rc_ok(check.get("rc_ok", (0, 1)))
    timeout = int(check.get("timeout", 10))

    use_fact = check.get("use_fact") or check.get("fact")
    command = str(check.get("command", "")).strip()

    stdout = ""
    stderr = ""
    rc: Optional[int] = 0
    duration = 0.0
    cpu_time = 0.0
    cached = False
    timed_out = False
    command_error: Optional[str] = None
    fact_used: Optional[str] = None

    if use_fact:
        fact_used = str(use_fact)
        fact = context.facts.get(fact_used)
        if not fact:
            return {
                "id": check_id,
                "name": name,
                "module": module,
                "severity": severity,
                "tags": check.get("tags", {}),
                "command": command,
                "rc": None,
                "output": "",
                "stderr": "",
                "result": "UNDEF",
                "reason": f"fact '{fact_used}' unavailable",
                "evidence": None,
                "weight": weight,
                "duration": 0.0,
                "cpu_time": 0.0,
                "cached": False,
                "timed_out": False,
                "fact": fact_used,
                "asserts": [],
                "ref": check.get("ref"),
                "remediation": check.get("remediation"),
                "evidence_snippet": "",
            }
        stdout = fact.stdout or ""
        stderr = fact.stderr or ""
        rc = fact.returncode
        duration = fact.duration
        cpu_time = fact.cpu_time
        cached = True
        timed_out = fact.timed_out
        command_error = fact.error
        command = fact.command or command
    else:
        if not command:
            return _build_error_result(check, context, ValueError("missing command"))
        cache_enabled = bool(check.get("cache", False))
        cmd_res = _run_command(
            command,
            timeout=timeout,
            rc_ok=rc_ok,
            context=context,
            cache_enabled=cache_enabled,
        )
        stdout = cmd_res.stdout or ""
        stderr = cmd_res.stderr or ""
        rc = cmd_res.returncode
        duration = cmd_res.duration
        cpu_time = cmd_res.cpu_time
        cached = cmd_res.cached
        timed_out = cmd_res.timed_out
        command_error = cmd_res.error

    if rc is None:
        rc = 0

    if command_error and rc not in rc_ok:
        status = _normalize_status(check.get("on_rc_fail"), "UNDEF" if timed_out else "FAIL") or "FAIL"
        evidence_file = _write_evidence(context.evidence_dir, check, stdout, stderr or "", rc)
        snippet = _make_snippet(stdout or stderr or "")
        return {
            "id": check_id,
            "name": name,
            "module": module,
            "severity": severity,
            "tags": check.get("tags", {}),
            "command": command,
            "rc": rc,
            "output": stdout if stdout else (stderr or "").strip(),
            "stderr": stderr,
            "result": status,
            "reason": command_error,
            "evidence": str(evidence_file) if evidence_file else None,
            "weight": weight,
            "duration": duration,
            "cpu_time": cpu_time,
            "cached": cached,
            "timed_out": timed_out,
            "fact": fact_used,
            "asserts": [],
            "ref": check.get("ref"),
            "remediation": check.get("remediation"),
            "evidence_snippet": snippet,
        }

    normalized_stdout = _normalize_output(stdout, check.get("normalize"))
    display_output = normalized_stdout or stdout or (stderr or "").strip()

    assertions = _collect_assertions(check)
    assert_results: List[Dict[str, Any]] = []
    overall_status = "PASS"
    reasons: List[str] = []

    if assertions:
        for spec in assertions:
            status, detail = _evaluate_single_assert(normalized_stdout or stdout, rc, spec, rc_ok, context)
            if status == "FAIL" and spec.on_fail:
                status = _normalize_status(spec.on_fail, status) or status
            assert_results.append(
                {
                    "type": spec.type,
                    "value": spec.value,
                    "status": status,
                    "detail": detail,
                }
            )
            if status != "PASS":
                reasons.append(detail)
            overall_status = _combine_status(overall_status, status)
    else:
        overall_status = "PASS"

    on_fail_status = _normalize_status(check.get("on_fail"))
    if overall_status == "FAIL" and on_fail_status:
        overall_status = on_fail_status

    reason_text = "; ".join([r for r in reasons if r]) or "ok"

    evidence_file = _write_evidence(context.evidence_dir, check, stdout, stderr or "", rc)
    snippet = _make_snippet(display_output)

    return {
        "id": check_id,
        "name": name,
        "module": module,
        "severity": severity,
        "tags": check.get("tags", {}),
        "command": command,
        "rc": rc,
        "output": display_output,
        "stderr": stderr,
        "result": overall_status,
        "reason": reason_text,
        "evidence": str(evidence_file) if evidence_file else None,
        "weight": weight,
        "duration": duration,
        "cpu_time": cpu_time,
        "cached": cached,
        "timed_out": timed_out,
        "fact": fact_used,
        "asserts": assert_results,
        "ref": check.get("ref"),
        "remediation": check.get("remediation"),
        "evidence_snippet": snippet,
    }


def _calculate_summary(results: List[Dict[str, Any]], context: ExecutionContext) -> Dict[str, Any]:
    counts: Dict[str, int] = defaultdict(int)
    total_weight = 0.0
    eligible_weight = 0.0
    weighted_pass = 0.0
    score_map = {"PASS": 1.0, "WARN": 0.5}
    fail_candidates: List[Dict[str, Any]] = []
    slow_candidates: List[Dict[str, Any]] = []

    for res in results:
        status = res.get("result", "UNDEF")
        counts[status] += 1
        weight = float(res.get("weight", 1.0) or 0.0)
        total_weight += weight
        if status != "SKIP":
            eligible_weight += weight
            weighted_pass += weight * score_map.get(status, 0.0)
            slow_candidates.append(res)
        if status in {"FAIL", "UNDEF", "WARN"}:
            fail_candidates.append(res)

    coverage = (eligible_weight / total_weight) if total_weight else 1.0
    score = (weighted_pass / eligible_weight * 100.0) if eligible_weight else 100.0

    def _failure_key(res: Dict[str, Any]) -> Tuple[int, int, float, str]:
        status = res.get("result", "PASS")
        severity = res.get("severity", "low")
        weight = float(res.get("weight", 1.0) or 0.0)
        return (
            -STATUS_PRIORITY.get(status, 0),
            -severity_rank(severity),
            -weight,
            str(res.get("id", "")),
        )

    top_failures = [
        {
            "id": res.get("id", ""),
            "name": res.get("name", ""),
            "result": res.get("result"),
            "severity": res.get("severity"),
            "weight": res.get("weight"),
            "module": res.get("module"),
            "reason": res.get("reason"),
        }
        for res in sorted(fail_candidates, key=_failure_key)[:5]
    ]

    top_slowest = [
        {
            "id": res.get("id", ""),
            "name": res.get("name", ""),
            "module": res.get("module", ""),
            "duration": res.get("duration", 0.0),
            "cpu_time": res.get("cpu_time", 0.0),
            "result": res.get("result"),
        }
        for res in sorted(slow_candidates, key=lambda r: r.get("duration", 0.0), reverse=True)[:5]
    ]

    facts_meta = {
        fid: {
            "rc": fact.returncode,
            "cached": fact.cached,
            "timed_out": fact.timed_out,
            "duration": fact.duration,
            "error": fact.error,
        }
        for fid, fact in context.facts.items()
    }

    summary = {
        "level": context.level,
        "variables": context.variables,
        "os": context.render_context.get("os", {}),
        "status_counts": dict(counts),
        "score": score,
        "score_scale": "percent",
        "weighted_pass": weighted_pass,
        "eligible_weight": eligible_weight,
        "total_weight": total_weight,
        "coverage": coverage,
        "top_failures": top_failures,
        "top_slowest": top_slowest,
        "facts": facts_meta,
        "checks_total": len(results),
        "duration_total": sum(res.get("duration", 0.0) for res in results),
        "generated_at": time.time(),
    }

    return summary


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
    dummy_context = ExecutionContext(
        level="baseline",
        variables={},
        render_context={},
        os_release={},
        base_dir=Path.cwd(),
    )
    spec = AssertSpec(type=assert_type, value=expect)
    status, detail = _evaluate_single_assert(stdout, rc, spec, rc_ok, dummy_context)
    return status, detail


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
