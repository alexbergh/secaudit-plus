# secaudit/main.py
from pathlib import Path
from datetime import datetime
import sys
import json
import re

from modules.cli import (
    parse_args,
    list_modules,
    list_checks,
    describe_check,
    parse_tag_filters,
)
from modules.os_detect import detect_os
from modules.audit_runner import load_profile, run_checks
from modules.report_generator import (
    generate_report,
    generate_json_report,
    generate_sarif_report,
    generate_junit_report,
    collect_host_metadata,
)
from utils.logger import log_info, log_warn, log_pass, log_fail

# Валидация профиля по схеме
from seclib.validator import validate_profile
from secaudit.exceptions import MissingDependencyError


def _resolve_profile_path(cli_profile: str | None) -> str:
    """
    Возвращает путь к профилю:
      1) если указан --profile и файл существует — используем его,
      2) если не указан/не найден — пытаемся определить по ОС (profiles/<os_id>.yml),
      3) иначе — fallback на profiles/common/baseline.yml.
    """
    if cli_profile:
        p = Path(cli_profile)
        if p.exists():
            return str(p)

    os_id = detect_os()
    candidate = Path(f"profiles/os/{os_id}.yml")
    if candidate.exists():
        return str(candidate)

    fallback_base = Path(f"profiles/base/{os_id}.yml")
    if fallback_base.exists():
        return str(fallback_base)

    log_warn(f"Профиль для {os_id} не найден. Использую profiles/common/baseline.yml")
    return "profiles/common/baseline.yml"


def _sanitize_filename_component(raw: str | None, fallback: str = "host") -> str:
    if raw is None:
        raw = ""
    text = str(raw).strip()
    if not text:
        text = fallback
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    sanitized = sanitized.strip("._-")
    return sanitized or fallback


def _print_and_exit_validation_errors(profile_path: str, errors: list[str], strict_exit_code: int = 2) -> None:
    print(f"Профиль '{profile_path}' невалиден:", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    sys.exit(strict_exit_code)


def _apply_exit_policy(results: list[dict], fail_level: str, fail_on_undef: bool) -> int:
    """
    Рассчитывает код возврата процесса по политике:
      --fail-on-undef: любой UNDEF → код 2
      --fail-level {low|medium|high|none}: любой FAIL с sev ≥ порога → код 2
    Если ни одно условие не выполнено → 0
    """
    level_weight = {"none": -1, "low": 0, "medium": 1, "high": 2}
    sev_weight   = {"low": 0, "medium": 1, "high": 2}

    exit_code = 0

    if fail_on_undef and any(r.get("result") == "UNDEF" for r in results):
        exit_code = max(exit_code, 2)

    threshold = level_weight.get(fail_level, -1)
    if threshold >= 0:
        for r in results:
            if r.get("result") == "FAIL":
                sev = sev_weight.get(r.get("severity", "low"), 0)
                if sev >= threshold:
                    exit_code = max(exit_code, 2)

    return exit_code


def _print_project_info() -> None:
    print("SecAudit++")
    print("Alex Hellberg")
    print("https://github.com/alexbergh/secaudit-core")
    print("2025")
    print("Проект распространяется под лицензией GPL-3.0")


def main():
    args = parse_args()

    if getattr(args, "info", False):
        _print_project_info()
        return

    # Определяем профиль
    profile_path = _resolve_profile_path(getattr(args, "profile", None))
    log_info(f"Загрузка профиля: {profile_path}")

    # Загружаем профиль (парсинг YAML + базовые проверки структуры внутри load_profile)
    try:
        profile = load_profile(profile_path)
    except MissingDependencyError as exc:
        log_fail(str(exc))
        sys.exit(3)

    # Валидация по JSON-схеме перед любыми действиями
    is_valid, val_errors = validate_profile(profile)

    # Команды, которым нужен только чтение профиля и/или мягкая реакция на ошибки
    if args.command in ("list-modules", "list-checks", "describe-check"):
        if not is_valid:
            log_warn("Профиль содержит ошибки валидации, вывод может быть неполным.")
        if args.command == "list-modules":
            list_modules(profile)
            return
        if args.command == "list-checks":
            try:
                tag_filters = parse_tag_filters(getattr(args, "tags", None))
            except ValueError as exc:
                log_fail(str(exc))
                sys.exit(2)
            list_checks(profile, getattr(args, "module", None), tag_filters)
            return
        if args.command == "describe-check":
            describe_check(profile, args.check_id)
            return

    # Команда validate — выводим результат проверки схемы
    if args.command == "validate":
        if is_valid:
            print("OK: Профиль соответствует схеме.")
            return
        strict = getattr(args, "strict", False)
        if strict:
            _print_and_exit_validation_errors(profile_path, val_errors, strict_exit_code=2)
        else:
            _print_and_exit_validation_errors(profile_path, val_errors, strict_exit_code=1)

    # Команда audit — полный запуск проверок
    if args.command == "audit":
        if not is_valid:
            # Для аудита ошибки профиля критичны
            _print_and_exit_validation_errors(profile_path, val_errors, strict_exit_code=2)

        # Фильтрация модулей, если указано --module
        selected_modules = []
        if getattr(args, "module", None):
            selected_modules = [m.strip() for m in args.module.split(",") if m.strip()]
            if selected_modules:
                log_info(f"Выбраны модули: {selected_modules}")

        # Запуск проверок
        evidence_dir = getattr(args, "evidence", None)
        outcome = run_checks(
            profile,
            selected_modules,
            evidence_dir,
            profile_path=profile_path,
            level=getattr(args, "level", "baseline"),
            variables_override=getattr(args, "vars", {}),
            workers=getattr(args, "workers", 0),
        )
        results = outcome.results
        summary = outcome.summary

        # Директория результатов
        Path("results").mkdir(exist_ok=True)

        # Полный список результатов (плоский)
        with open("results/report.json", "w", encoding="utf-8") as f:
            json.dump({"results": results, "summary": summary}, f, indent=2, ensure_ascii=False)

        # Группировка результатов по модулям
        generate_json_report(results, "results/report_grouped.json", summary=summary)

        # Логируем в консоль краткую сводку
        score = summary.get("score")
        if score is not None:
            coverage = summary.get("coverage", 0) * 100
            log_info(f"Итоговый балл: {score:.1f}% (покрытие {coverage:.1f}%)")
        for r in results:
            name = r.get("name", r.get("id", "<no-name>"))
            out = r.get("output", "")
            status = r.get("result", "UNDEF")
            if status == "PASS":
                log_pass(f"{name} → {out}")
            elif status == "FAIL":
                log_fail(f"{name} → {out}")
            elif status == "WARN":
                log_warn(f"{name} → {out}")
            else:
                log_warn(f"{name} [{status}] → {out}")

        for failure in summary.get("top_failures", []) or []:
            log_warn(
                f"ТОП-провал: {failure.get('id')} ({failure.get('result')}) → {failure.get('reason')}"
            )

        # Метаданные хоста для отчётов и имени файла
        host_info = collect_host_metadata(profile, results, summary=summary)
        hostname_component = _sanitize_filename_component(host_info.get("hostname"))
        date_component = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_report_path = Path("results") / f"report_{hostname_component}_{date_component}.html"

        # Генерируем отчёты (Markdown и HTML)
        generate_report(
            profile,
            results,
            "report_template.md.j2",
            "results/report.md",
            host_info=host_info,
            summary=summary,
        )
        generate_report(
            profile,
            results,
            "report_template.html.j2",
            str(html_report_path),
            host_info=host_info,
            summary=summary,
        )

        generate_sarif_report(
            profile,
            results,
            "results/report.sarif",
            summary=summary,
            host_info=host_info,
        )
        generate_junit_report(
            profile,
            results,
            "results/report.junit.xml",
            summary=summary,
            host_info=host_info,
        )

        # Политика завершения по --fail-level / --fail-on-undef
        fail_level = getattr(args, "fail_level", "none")
        fail_on_undef = getattr(args, "fail_on_undef", False)
        exit_code = _apply_exit_policy(results, fail_level, fail_on_undef)

        if exit_code:
            sys.exit(exit_code)
        return

    # Если сюда дошли — неизвестная команда
    log_warn(f"Неизвестная команда: {args.command}")
    sys.exit(1)


if __name__ == "__main__":
    main()
