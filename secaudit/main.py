# secaudit/main.py
from pathlib import Path
from datetime import datetime
import sys
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    generate_prometheus_metrics,
    generate_elastic_export,
)
from modules.report_diff import compare_reports, format_report_diff
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
    try:
        args = parse_args()
    except SystemExit:
        raise
    except Exception as exc:
        log_fail(f"Ошибка парсинга аргументов: {exc}")
        sys.exit(1)

    if getattr(args, "info", False):
        _print_project_info()
        return

    # Health check command (doesn't require profile)
    if args.command == "health":
        try:
            from secaudit.health import health_check_handler, print_health_status
            if getattr(args, "json", False):
                exit_code = health_check_handler(getattr(args, "type", "liveness"))
            else:
                exit_code = print_health_status()
            sys.exit(exit_code)
        except ImportError:
            log_fail("Health check module not available")
            sys.exit(1)

    # Определяем профиль
    try:
        profile_path = _resolve_profile_path(getattr(args, "profile", None))
        log_info(f"Загрузка профиля: {profile_path}")
    except Exception as exc:
        log_fail(f"Ошибка определения пути профиля: {exc}")
        sys.exit(1)

    # Загружаем профиль (парсинг YAML + базовые проверки структуры внутри load_profile)
    try:
        profile = load_profile(profile_path)
    except MissingDependencyError as exc:
        log_fail(f"Отсутствует зависимость: {exc}")
        sys.exit(3)
    except FileNotFoundError:
        log_fail(f"Файл профиля не найден: {profile_path}")
        sys.exit(1)
    except Exception as exc:
        log_fail(f"Ошибка загрузки профиля: {exc}")
        sys.exit(1)

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

    if args.command == "compare":
        try:
            diff = compare_reports(args.before, args.after, fail_only=getattr(args, "fail_only", False))
            print(format_report_diff(diff))
            output_path = getattr(args, "output", None)
            if output_path:
                Path(output_path).write_text(
                    json.dumps(diff, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            log_info("Сравнение отчетов завершено")
            return
        except FileNotFoundError as exc:
            log_fail(f"Файл отчета не найден: {exc}")
            sys.exit(1)
        except Exception as exc:
            log_fail(f"Ошибка сравнения отчетов: {exc}")
            sys.exit(1)

    # Команда scan — сканирование сети
    if args.command == "scan":
        from modules.network_scanner import scan_networks, export_results_json, export_results_yaml, print_scan_summary
        
        networks = [n.strip() for n in args.networks.split(",") if n.strip()]
        ssh_ports = [int(p.strip()) for p in args.ssh_ports.split(",") if p.strip()]
        
        log_info(f"Сканирование сетей: {', '.join(networks)}")
        
        try:
            results = scan_networks(
                networks=networks,
                ssh_ports=ssh_ports,
                timeout=args.timeout,
                workers=args.workers,
                ping_method=args.ping_method,
                resolve_hostnames=not args.no_resolve,
                detect_os=not args.no_detect_os,
            )
            
            # Фильтрация по ОС если указано
            if hasattr(args, "filter_os") and args.filter_os:
                os_filters = [f.strip().lower() for f in args.filter_os.split(",")]
                results = [
                    r for r in results 
                    if r.os_detected and any(f in r.os_detected.lower() for f in os_filters)
                ]
                log_info(f"Отфильтровано по ОС: {len(results)} хостов")
            
            # Сохранение результатов
            output_path = Path(args.output)
            if output_path.suffix.lower() in [".yml", ".yaml"]:
                export_results_yaml(results, output_path)
            else:
                export_results_json(results, output_path)
            
            # Вывод сводки
            print_scan_summary(results)
            
            return
            
        except Exception as exc:
            log_fail(f"Ошибка сканирования: {exc}")
            sys.exit(1)
    
    # Команда inventory — управление инвентори
    if args.command == "inventory":
        from modules.inventory_manager import InventoryManager, HostEntry
        from modules.network_scanner import ScanResult
        
        if args.inventory_command == "create":
            # Создание инвентори из сканирования
            try:
                with open(args.from_scan, 'r', encoding='utf-8') as f:
                    scan_data = json.load(f)
                
                # Конвертируем в ScanResult объекты
                scan_results = []
                for host_data in scan_data.get("hosts", []):
                    result = ScanResult(
                        ip=host_data["ip"],
                        hostname=host_data.get("hostname"),
                        is_alive=host_data.get("is_alive", False),
                        ssh_port=host_data.get("ssh_port"),
                        ssh_banner=host_data.get("ssh_banner"),
                        os_detected=host_data.get("os_detected"),
                    )
                    scan_results.append(result)
                
                manager = InventoryManager()
                manager.create_from_scan(
                    scan_results,
                    auto_group=args.auto_group,
                    default_group=args.default_group,
                    ssh_user=args.ssh_user,
                    ssh_key=args.ssh_key,
                    default_profile=args.profile,
                )
                
                manager.save(Path(args.output))
                manager.print_summary()
                
                log_info("Инвентори успешно создан")
                return
                
            except Exception as exc:
                log_fail(f"Ошибка создания инвентори: {exc}")
                sys.exit(1)
        
        elif args.inventory_command == "add-host":
            # Добавление хоста в инвентори
            try:
                manager = InventoryManager(Path(args.inventory))
                manager.load()
                
                tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
                
                host = HostEntry(
                    ip=args.ip,
                    hostname=args.hostname,
                    ssh_port=args.ssh_port,
                    ssh_user=args.ssh_user,
                    ssh_key=args.ssh_key,
                    profile=args.profile,
                    tags=tags,
                )
                
                manager.inventory.add_host(host, args.group)
                manager.save()
                
                log_info(f"Хост {args.ip} добавлен в группу {args.group}")
                return
                
            except Exception as exc:
                log_fail(f"Ошибка добавления хоста: {exc}")
                sys.exit(1)
        
        elif args.inventory_command == "list":
            # Показ хостов из инвентори
            try:
                manager = InventoryManager(Path(args.inventory))
                manager.load()
                
                tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
                
                manager.list_hosts(
                    group=args.group,
                    tags=tags,
                    os_filter=args.os,
                    verbose=args.verbose,
                )
                
                return
                
            except Exception as exc:
                log_fail(f"Ошибка чтения инвентори: {exc}")
                sys.exit(1)
        
        elif args.inventory_command == "update":
            # Обновление инвентори
            try:
                manager = InventoryManager(Path(args.inventory))
                manager.load()
                
                if args.scan and args.networks:
                    from modules.network_scanner import scan_networks
                    
                    networks = [n.strip() for n in args.networks.split(",")]
                    log_info(f"Сканирование для обновления: {', '.join(networks)}")
                    
                    scan_results = scan_networks(networks=networks)
                    
                    # Обновляем существующие хосты и добавляем новые
                    for result in scan_results:
                        if not result.is_alive:
                            continue
                        
                        existing = manager.inventory.get_host(result.ip)
                        if existing:
                            # Обновляем информацию
                            host, group_name = existing
                            if result.hostname:
                                host.hostname = result.hostname
                            if result.ssh_port:
                                host.ssh_port = result.ssh_port
                            if result.os_detected:
                                host.os = result.os_detected
                        else:
                            # Добавляем новый хост
                            host = HostEntry(
                                ip=result.ip,
                                hostname=result.hostname,
                                ssh_port=result.ssh_port or 22,
                                os=result.os_detected,
                            )
                            manager.inventory.add_host(host, "discovered")
                    
                    manager.save()
                    log_info("Инвентори обновлён")
                
                manager.print_summary()
                return
                
            except Exception as exc:
                log_fail(f"Ошибка обновления инвентори: {exc}")
                sys.exit(1)
    
    # Команда audit-remote — удалённый аудит
    if args.command == "audit-remote":
        from modules.inventory_manager import load_inventory
        from modules.remote_executor import execute_remote_audit
        
        try:
            # Загружаем инвентори
            inventory = load_inventory(Path(args.inventory))
            log_info(f"Загружен инвентори с {inventory.get_host_count()} хостами")
            
            # Парсим теги если указаны
            tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
            
            # Выполняем удалённый аудит
            results = execute_remote_audit(
                inventory=inventory,
                output_dir=Path(args.output_dir),
                workers=args.workers,
                profile=args.profile,
                level=args.level,
                fail_level=args.fail_level,
                evidence=args.evidence,
                group=args.group,
                tags=tags,
                os_filter=args.os_filter,
            )
            
            # Выводим сводку
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            print("\n" + "="*60)
            print("СВОДКА УДАЛЁННОГО АУДИТА")
            print("="*60)
            print(f"Всего хостов: {len(results)}")
            print(f"Успешно: {successful}")
            print(f"С ошибками: {failed}")
            print("="*60 + "\n")
            
            # Код возврата
            if failed > 0:
                sys.exit(2)
            
            return
            
        except Exception as exc:
            log_fail(f"Ошибка удалённого аудита: {exc}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Команда audit-agentless — agentless аудит (рекомендуется)
    if args.command == "audit-agentless":
        from modules.inventory_manager import load_inventory
        from modules.agentless_executor import execute_agentless_audit
        
        try:
            # Загружаем инвентори
            inventory = load_inventory(Path(args.inventory))
            log_info(f"[Agentless] Загружен инвентори с {inventory.get_host_count()} хостами")
            
            # Парсим теги если указаны
            tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
            
            # Выполняем agentless аудит
            results = execute_agentless_audit(
                inventory=inventory,
                output_dir=Path(args.output_dir),
                profile_path=args.profile,
                level=args.level,
                workers=args.workers,
                timeout=args.timeout,
                group=args.group,
                tags=tags,
                os_filter=args.os_filter,
            )
            
            # Выводим сводку
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            avg_score = sum(r.score for r in results if r.success) / max(successful, 1)
            
            print("\n" + "="*60)
            print("СВОДКА AGENTLESS АУДИТА")
            print("="*60)
            print(f"Всего хостов: {len(results)}")
            print(f"Успешно: {successful}")
            print(f"С ошибками: {failed}")
            print(f"Средний security score: {avg_score:.1f}/100")
            print("="*60)
            
            # Детализация по хостам
            print("\nРезультаты по хостам:")
            print(f"{'Хост':<30} {'Score':<10} {'Pass/Fail/Undef':<20} {'Status':<10}")
            print("-" * 80)
            for r in results:
                if r.success:
                    status = "✓ OK"
                    stats = f"{r.checks_pass}/{r.checks_fail}/{r.checks_undef}"
                else:
                    status = "✗ ERROR"
                    stats = "-"
                print(f"{r.host:<30} {r.score:>6.1f}/100  {stats:<20} {status:<10}")
            
            print("\nОтчёты сохранены в:", args.output_dir)
            print("="*60 + "\n")
            
            # Код возврата
            if failed > 0:
                sys.exit(2)
            
            return
            
        except Exception as exc:
            log_fail(f"[Agentless] Ошибка аудита: {exc}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
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
        try:
            Path("results").mkdir(exist_ok=True)
        except OSError as exc:
            log_fail(f"Не удалось создать директорию results: {exc}")
            sys.exit(1)

        # Полный список результатов (плоский)
        try:
            with open("results/report.json", "w", encoding="utf-8") as f:
                json.dump({"results": results, "summary": summary}, f, indent=2, ensure_ascii=False)
            log_info("Сохранен results/report.json")
        except OSError as exc:
            log_fail(f"Ошибка записи results/report.json: {exc}")

        # Группировка результатов по модулям
        try:
            generate_json_report(results, "results/report_grouped.json", summary=summary)
            log_info("Сохранен results/report_grouped.json")
        except Exception as exc:
            log_fail(f"Ошибка генерации report_grouped.json: {exc}")

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

        # Параллельная генерация отчетов
        log_info("Генерация отчетов...")
        report_tasks = [
            (generate_report, (profile, results, "report_template.md.j2", Path("results/report.md")), {"host_info": host_info, "summary": summary}),
            (generate_report, (profile, results, "report_template.html.j2", html_report_path), {"host_info": host_info, "summary": summary}),
            (generate_sarif_report, (profile, results, Path("results/report.sarif")), {"summary": summary, "host_info": host_info}),
            (generate_junit_report, (profile, results, Path("results/report.junit.xml")), {"summary": summary, "host_info": host_info}),
            (generate_prometheus_metrics, (profile, results, Path("results/report.prom")), {"summary": summary, "host_info": host_info}),
            (generate_elastic_export, (profile, results, Path("results/report.elastic.ndjson")), {"summary": summary, "host_info": host_info}),
        ]

        with ThreadPoolExecutor(max_workers=len(report_tasks)) as executor:
            futures = {executor.submit(func, *args, **kwargs) for func, args, kwargs in report_tasks}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    log_fail(f"Ошибка при генерации отчета: {exc}")

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
