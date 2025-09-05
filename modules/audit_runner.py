# modules/audit_runner.py
from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Tuple

from modules.bash_executor import run_bash, CommandError  # <= используем мягкий исполнитель


# ───────────────────────── Загрузка профиля ─────────────────────────

def load_profile(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Profile not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # Минимальная нормализация
    data.setdefault("profile_name", str(p.stem))
    data.setdefault("description", "")
    data.setdefault("checks", [])
    return data


# ───────────────────────── Исполнение проверок ─────────────────────────

def run_checks(profile: Dict[str, Any], selected_modules: List[str] | None = None) -> List[Dict[str, Any]]:
    """
    Выполняет проверки из профиля, опционально фильтруя по модулям.
    Возвращает список результатов (для JSON/отчётов).
    """
    selected_modules = selected_modules or []
    out: List[Dict[str, Any]] = []

    for check in profile.get("checks", []):
        module = check.get("module", "core")
        if selected_modules and module not in selected_modules:
            continue

        res = _execute_check(check)
        out.append(res)

    return out


def _execute_check(check: Dict[str, Any]) -> Dict[str, Any]:
    """
    Запускает одну проверку через run_bash и применяет assert-логику.
    Поддерживаем assert_type: exact | contains | regexp | exit_code.
    """
    cmd: str = check["command"]
    expect: str = str(check.get("expect", ""))
    assert_type: str = check.get("assert_type", "exact").lower()
    timeout: int = int(check.get("timeout", 10))
    # По умолчанию принимаем rc 0/1 как "неошибочные" для аудита (grep no-match = 1)
    rc_ok = tuple(check.get("rc_ok", (0, 1)))

    # Выполняем
    try:
        exec_res = run_bash(cmd, timeout=timeout, rc_ok=rc_ok)
        rc, stdout, stderr = exec_res.returncode, exec_res.stdout, exec_res.stderr
    except CommandError as e:
        rc = e.returncode if e.returncode is not None else 1
        stdout = getattr(e, "stdout", "")
        stderr = e.stderr
        return {
            "id": check.get("id", ""),
            "name": check.get("name", ""),
            "module": check.get("module", "core"),
            "severity": check.get("severity", "low"),
            "tags": check.get("tags", {}),
            "command": cmd,
            "assert_type": assert_type,
            "expect": expect,
            "rc": rc,
            "output": stdout if stdout else (stderr or "").strip(),
            "stderr": stderr,
            "result": "FAIL",        # Ошибка выполнения команды
            "reason": str(e),          # сообщение об ошибке
        }

    # Нормализация результатов
    status, verdict_detail = _apply_assert(stdout, rc, expect, assert_type, rc_ok)

    # Таймаут оставляем как UNDEF, чтобы не путать с FAIL
    if rc == 124 and status == "FAIL":
        status = "UNDEF"
        if not verdict_detail:
            verdict_detail = "timeout"

    return {
        "id": check.get("id", ""),
        "name": check.get("name", ""),
        "module": check.get("module", "core"),
        "severity": check.get("severity", "low"),
        "tags": check.get("tags", {}),
        "command": cmd,
        "assert_type": assert_type,
        "expect": expect,
        "rc": rc,
        "output": stdout if stdout else (stderr or "").strip(),
        "stderr": stderr,
        "result": status,           # PASS | FAIL | UNDEF
        "reason": verdict_detail,   # пояснение для отчёта/отладки
    }


def _apply_assert(stdout: str, rc: int, expect: str, assert_type: str, rc_ok: Tuple[int, ...]) -> Tuple[str, str]:
    """
    Возвращает кортеж (result, reason).
    result: PASS|FAIL по проверке (до обработки таймаута в _execute_check)
    reason: краткое пояснение
    """
    out = stdout.strip()

    # Если код возврата "неприемлемый" — это сразу FAIL (кроме таймаута, который позже станет UNDEF)
    if rc not in rc_ok:
        return "FAIL", f"rc={rc} not in {rc_ok}"

    if assert_type == "exact":
        return ("PASS", "exact match") if out == expect else ("FAIL", f"got '{out}' != expect '{expect}'")

    if assert_type == "contains":
        return ("PASS", "contains") if expect in out else ("FAIL", f"'{expect}' not found")

    if assert_type == "regexp":
        try:
            pat = re.compile(expect, re.MULTILINE)
        except re.error as e:
            # Некорректный шаблон — отмечаем провал проверки
            return "FAIL", f"bad regexp: {e}"
        return ("PASS", "regexp match") if pat.search(out) else ("FAIL", "regexp no match")

    if assert_type == "exit_code":
        # Проверяем код возврата вместо stdout: exact | regexp, если expect — шаблон ^\d+$
        if expect == "":
            # Если не задано — трактуем как rc == 0
            return ("PASS", "rc==0") if rc == 0 else ("FAIL", f"rc={rc}")
        if expect.isdigit():
            return ("PASS", "rc==expect") if int(expect) == rc else ("FAIL", f"rc={rc} != {expect}")
        # Если в expect не чистое число — разрешим regexp по числу rc (в виде строки)
        try:
            pat = re.compile(expect)
            return ("PASS", "rc~regexp") if pat.fullmatch(str(rc)) else ("FAIL", f"rc={rc} !~ /{expect}/")
        except re.error as e:
            return "FAIL", f"bad rc regexp: {e}"

    # Если тип неизвестен — лучше провалить, чтобы не было ложноположительных
    return "FAIL", f"unsupported assert_type '{assert_type}'"
