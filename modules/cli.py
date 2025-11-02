# modules/cli.py
import argparse
import os
import sys
from pathlib import Path
from typing import Tuple, List, Dict, Any

from secaudit.exceptions import MissingDependencyError

# ──────────────────────────────────────────────────────────────────────────────
# Проверка критичных зависимостей при импорте
# ──────────────────────────────────────────────────────────────────────────────
try:
    import yaml  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - runtime guard
    yaml = None  # type: ignore
    _YAML_IMPORT_ERROR = exc
else:  # pragma: no cover - exercised indirectly
    _YAML_IMPORT_ERROR = None
try:
    from jsonschema import validate as js_validate
    from jsonschema.exceptions import ValidationError as JSValidationError
    _HAS_JSONSCHEMA = True
except Exception:
    js_validate = None  # type: ignore
    JSValidationError = None  # type: ignore
    _HAS_JSONSCHEMA = False

from seclib.validator import PROFILE_SCHEMA as STRICT_PROFILE_SCHEMA


_PROFILE_SCHEMA = STRICT_PROFILE_SCHEMA
DEFAULT_PROFILE_PATH = "profiles/common/baseline.yml"
PROFILE_ARGUMENT_HELP = "Необязательный путь к профилю."


# ──────────────────────────────────────────────────────────────────────────────
# Утилиты печати из профиля (их импортирует твой main.py)
# ──────────────────────────────────────────────────────────────────────────────
def list_modules(profile: Dict[str, Any]) -> None:
    """Печатает отсортированный список уникальных модулей из профиля."""
    modules = {check.get("module", "core") for check in profile.get("checks", [])}
    for m in sorted(modules):
        print(m)


def parse_tag_filters(raw: List[str] | None) -> Dict[str, str]:
    filters: Dict[str, str] = {}
    if not raw:
        return filters
    for item in raw:
        if "=" not in item:
            raise ValueError(f"Неверный формат фильтра по тегам: '{item}' (используйте KEY=VALUE)")
        key, value = item.split("=", 1)
        key = key.strip().lower()
        value = value.strip().lower()
        if not key or not value:
            raise ValueError(f"Неверный фильтр по тегам: '{item}'")
        filters[key] = value
    return filters


def parse_kv_pairs(raw: List[str] | None, *, option: str) -> Dict[str, str]:
    """Парсит список KEY=VALUE в словарь."""

    if not raw:
        return {}

    parsed: Dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(
                f"Неверный формат {option}: '{item}'. Используйте KEY=VALUE."
            )
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Неверный ключ в {option}: '{item}'")
        parsed[key] = value
    return parsed


def _match_tags(check_tags: Dict[str, Any], filters: Dict[str, str]) -> bool:
    if not filters:
        return True
    if not isinstance(check_tags, dict):
        return False
    lowered = {str(k).lower(): v for k, v in check_tags.items()}
    for key, expected in filters.items():
        value = lowered.get(key)
        if value is None:
            return False
        if isinstance(value, (list, tuple, set)):
            haystack = [str(v).lower() for v in value]
            if expected not in haystack:
                return False
        else:
            if str(value).lower() != expected:
                return False
    return True


def list_checks(
    profile: Dict[str, Any],
    module: str | None = None,
    tags: Dict[str, str] | None = None,
) -> None:
    """Печатает список проверок, опционально фильтруя по модулю и тегам."""
    tags = tags or {}
    module_filter = module.lower() if module else None
    for check in profile.get("checks", []):
        check_module = str(check.get("module", "")).lower()
        if module_filter and check_module != module_filter:
            continue
        if tags and not _match_tags(check.get("tags", {}), tags):
            continue
        cid = check.get("id", "<no_id>")
        name = check.get("name", "<Unnamed Check>")
        sev = check.get("severity", "-")
        mod = check.get("module", "-")
        print(f"{cid}: {name} [{sev}] (module: {mod})")


def describe_check(profile: Dict[str, Any], check_id: str) -> None:
    """Печатает подробную информацию по конкретной проверке по ID."""
    for check in profile.get("checks", []):
        if check.get("id") == check_id:
            print(f"ID: {check.get('id', '<no_id>')}")
            print(f"Name: {check.get('name', '<Unnamed Check>')}")
            print(f"Module: {check.get('module', 'core')}")
            print(f"Severity: {check.get('severity', 'low')}")
            print(f"Command: {check.get('command', '<no_command>')}")
            print(f"Expected: {check.get('expect', '')}")
            print(f"Assert Type: {check.get('assert_type', 'exact')}")
            print("Tags:")
            for k, v in check.get("tags", {}).items():
                print(f"  {k}: {v}")
            return
    print(f"Check ID '{check_id}' not found in the profile.")


def _ensure_dependencies() -> None:
    """Проверяет наличие PyYAML и завершает работу, если он отсутствует."""
    if yaml is None:
        raise MissingDependencyError(
            package="PyYAML",
            import_name="yaml",
            instructions="pip install -r requirements.txt",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Загрузка профиля и опциональная валидация
# ──────────────────────────────────────────────────────────────────────────────
def load_profile_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    _ensure_dependencies()
    if not p.is_file():
        print(f"Ошибка: Файл профиля не найден: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}  # type: ignore[union-attr]
    except yaml.YAMLError as e:  # type: ignore[union-attr]
        print(f"Ошибка: Не удалось прочитать YAML: {e}", file=sys.stderr)
        sys.exit(2)


def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Возвращает (is_valid, errors). Если jsonschema нет — мягкая валидация."""
    errors: List[str] = []

    if not isinstance(profile, dict):
        return False, ["Формат профиля не является YAML-объектом (ожидался mapping)."]

    # Базовые проверки без jsonschema
    required_top = ["schema_version", "profile_name", "description", "checks"]
    for k in required_top:
        if k not in profile:
            errors.append(f"Отсутствует обязательное поле '{k}'.")

    checks = profile.get("checks", [])
    if not isinstance(checks, list):
        errors.append("Поле 'checks' должно быть массивом.")


    # Если jsonschema доступен — используем полную схему
    if _HAS_JSONSCHEMA and js_validate and JSValidationError:
        try:
            js_validate(instance=profile, schema=_PROFILE_SCHEMA)
        except JSValidationError as e:  # type: ignore
            # Разворачиваем путь для понятной трассировки
            path = " -> ".join(str(p) for p in e.path) if e.path else "<root>"
            errors.append(f"{path}: {e.message}")

    return (len(errors) == 0), errors


# ──────────────────────────────────────────────────────────────────────────────
# Парсинг аргументов
# ──────────────────────────────────────────────────────────────────────────────
def _add_profile_arguments(subparser: argparse.ArgumentParser, *, default_profile: str) -> None:
    """Подключает флаг и позиционный аргумент профиля к подкоманде."""

    subparser.add_argument(
        "--profile",
        dest="profile",
        default=argparse.SUPPRESS,
        help=f"Путь к YAML-профилю (по умолчанию: {default_profile})",
    )
    subparser.add_argument(
        "profile_path",
        nargs="?",
        metavar="PROFILE",
        help=PROFILE_ARGUMENT_HELP,
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """
    Глобальный флаг --profile разрешён и до, и после команды.
    Также можно указать путь к профилю последним позиционным аргументом:
      secaudit validate profiles/alt.yml
      secaudit audit profiles/alt.yml --fail-on-undef

    Если флаг и позиционный аргумент переданы одновременно, предпочтение
    отдаётся позиционному значению, чтобы последняя указанная цель профиля
    всегда побеждала.
    """

    if argv is None:
        argv = sys.argv[1:]

    default_profile = DEFAULT_PROFILE_PATH

    info_flags = {"-i", "--info"}
    if argv and all(arg in info_flags for arg in argv):
        # Короткий путь: только флаг --info/ -i без дополнительных аргументов.
        # Возвращаем минимальный namespace, чтобы избежать жалоб argparse на
        # отсутствие подкоманды в разных окружениях.
        return argparse.Namespace(info=True, command=None, profile=default_profile)

    parser = argparse.ArgumentParser(
        prog="secaudit",
        description="SecAudit++ CLI — запуск аудита, валидация профиля и служебные команды.",
    )

    parser.add_argument(
        "-i",
        "--info",
        action="store_true",
        help="Показать сведения о проекте и завершиться.",
    )

    parser.add_argument(
        "--profile",
        dest="profile",
        default=argparse.SUPPRESS,
        help=f"Путь к YAML-профилю (по умолчанию: {default_profile})",
    )

    subs = parser.add_subparsers(dest="command", required=False, help="Доступные команды")

    sub_modules = subs.add_parser("list-modules", help="Показать все модули в профиле")
    _add_profile_arguments(sub_modules, default_profile=default_profile)

    sub_checks = subs.add_parser("list-checks", help="Показать проверки")
    sub_checks.add_argument("--module", help="Фильтровать проверки по модулю")
    sub_checks.add_argument(
        "--tags",
        action="append",
        metavar="KEY=VALUE",
        help="Фильтр по тегам (можно указывать несколько раз)",
    )
    _add_profile_arguments(sub_checks, default_profile=default_profile)

    sub_desc = subs.add_parser("describe-check", help="Детали проверки по ID")
    sub_desc.add_argument("check_id", help="ID проверки")
    _add_profile_arguments(sub_desc, default_profile=default_profile)

    sub_compare = subs.add_parser("compare", help="Сравнить два JSON-отчёта")
    sub_compare.add_argument("before", help="Путь к базовому отчёту (JSON)")
    sub_compare.add_argument("after", help="Путь к отчёту для сравнения (JSON)")
    sub_compare.add_argument(
        "--fail-only",
        action="store_true",
        help="Показывать только ухудшения и новые проблемы (FAIL/UNDEF)",
    )
    sub_compare.add_argument(
        "--output",
        help="Сохранить результат сравнения в JSON-файл",
    )

    sub_health = subs.add_parser("health", help="Проверка здоровья системы (для K8s probes)")
    sub_health.add_argument(
        "--type",
        choices=["liveness", "readiness"],
        default="liveness",
        help="Тип проверки: liveness (живость) или readiness (готовность)",
    )
    sub_health.add_argument(
        "--json",
        action="store_true",
        help="Вывод в JSON формате (для автоматизации)",
    )

    sub_val = subs.add_parser("validate", help="Проверить профиль на ошибки")
    sub_val.add_argument(
        "--strict",
        action="store_true",
        help="Строгий режим: код возврата 1 при предупреждениях",
    )
    _add_profile_arguments(sub_val, default_profile=default_profile)

    sub_audit = subs.add_parser("audit", help="Запустить аудит")
    sub_audit.add_argument(
        "--module",
        help="Список модулей через запятую (например: system,network). По умолчанию — все.",
    )
    sub_audit.add_argument(
        "--fail-level",
        choices=["none", "low", "medium", "high"],
        default="none",
        help="Порог неуспеха (код возврата 2, если найдены проблемы >= уровня). По умолчанию: none.",
    )
    sub_audit.add_argument(
        "--fail-on-undef",
        action="store_true",
        help="Return exit code 2 if any check result is UNDEF.",
    )
    sub_audit.add_argument(
        "--evidence",
        metavar="DIR",
        help="Каталог для сохранения выводов команд (улики).",
    )
    sub_audit.add_argument(
        "--level",
        choices=["baseline", "strict", "paranoid"],
        default=os.environ.get("SECAUDIT_LEVEL", "baseline"),
        help="Уровень строгости (можно задать через SECAUDIT_LEVEL).",
    )
    sub_audit.add_argument(
        "--var",
        action="append",
        metavar="KEY=VALUE",
        help="Переопределение переменных профиля (можно указывать несколько раз).",
    )
    sub_audit.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("SECAUDIT_WORKERS", "0")),
        help="Количество потоков (0 — авто).",
    )
    _add_profile_arguments(sub_audit, default_profile=default_profile)

    # ──────────────────────────────────────────────────────────────────────────────
    # Команды для сетевого сканирования и удалённого аудита
    # ──────────────────────────────────────────────────────────────────────────────
    
    sub_scan = subs.add_parser("scan", help="Сканирование сети для обнаружения хостов")
    sub_scan.add_argument(
        "--network",
        "--networks",
        dest="networks",
        required=True,
        help="Сеть или список сетей через запятую (например: 192.168.1.0/24,10.0.0.0/24)",
    )
    sub_scan.add_argument(
        "--ssh-ports",
        default="22",
        help="SSH порты для проверки через запятую (по умолчанию: 22)",
    )
    sub_scan.add_argument(
        "--timeout",
        type=int,
        default=2,
        help="Таймаут для каждого хоста в секундах (по умолчанию: 2)",
    )
    sub_scan.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Количество параллельных workers (по умолчанию: 50)",
    )
    sub_scan.add_argument(
        "--ping-method",
        choices=["tcp", "icmp", "both"],
        default="tcp",
        help="Метод проверки доступности (по умолчанию: tcp)",
    )
    sub_scan.add_argument(
        "--no-resolve",
        action="store_true",
        help="Не резолвить hostname'ы",
    )
    sub_scan.add_argument(
        "--no-detect-os",
        action="store_true",
        help="Не определять ОС по SSH баннеру",
    )
    sub_scan.add_argument(
        "--filter-os",
        help="Фильтр по ОС (например: ubuntu,debian)",
    )
    sub_scan.add_argument(
        "-o", "--output",
        required=True,
        help="Путь к выходному файлу (JSON или YAML)",
    )

    sub_inventory = subs.add_parser("inventory", help="Управление инвентори хостов")
    inv_subs = sub_inventory.add_subparsers(dest="inventory_command", required=True, help="Операции с инвентори")
    
    # inventory create
    inv_create = inv_subs.add_parser("create", help="Создать инвентори из результатов сканирования")
    inv_create.add_argument(
        "--from-scan",
        required=True,
        help="Путь к файлу с результатами сканирования (JSON)",
    )
    inv_create.add_argument(
        "-o", "--output",
        required=True,
        help="Путь к выходному файлу инвентори (YAML)",
    )
    inv_create.add_argument(
        "--auto-group",
        action="store_true",
        help="Автоматически группировать хосты по подсетям",
    )
    inv_create.add_argument(
        "--default-group",
        default="discovered",
        help="Имя группы по умолчанию (по умолчанию: discovered)",
    )
    inv_create.add_argument(
        "--ssh-user",
        default="root",
        help="SSH пользователь по умолчанию (по умолчанию: root)",
    )
    inv_create.add_argument(
        "--ssh-key",
        help="Путь к SSH ключу по умолчанию",
    )
    inv_create.add_argument(
        "--profile",
        help="Профиль аудита по умолчанию",
    )
    
    # inventory add-host
    inv_add = inv_subs.add_parser("add-host", help="Добавить хост в инвентори")
    inv_add.add_argument(
        "--inventory",
        required=True,
        help="Путь к файлу инвентори",
    )
    inv_add.add_argument(
        "--ip",
        required=True,
        help="IP адрес хоста",
    )
    inv_add.add_argument(
        "--hostname",
        help="Hostname хоста",
    )
    inv_add.add_argument(
        "--group",
        default="default",
        help="Группа хоста (по умолчанию: default)",
    )
    inv_add.add_argument(
        "--ssh-port",
        type=int,
        default=22,
        help="SSH порт (по умолчанию: 22)",
    )
    inv_add.add_argument(
        "--ssh-user",
        default="root",
        help="SSH пользователь (по умолчанию: root)",
    )
    inv_add.add_argument(
        "--ssh-key",
        help="Путь к SSH ключу",
    )
    inv_add.add_argument(
        "--profile",
        help="Профиль аудита",
    )
    inv_add.add_argument(
        "--tags",
        help="Теги через запятую",
    )
    
    # inventory list
    inv_list = inv_subs.add_parser("list", help="Показать хосты из инвентори")
    inv_list.add_argument(
        "--inventory",
        required=True,
        help="Путь к файлу инвентори",
    )
    inv_list.add_argument(
        "--group",
        help="Фильтр по группе",
    )
    inv_list.add_argument(
        "--tags",
        help="Фильтр по тегам через запятую",
    )
    inv_list.add_argument(
        "--os",
        help="Фильтр по ОС",
    )
    inv_list.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Подробный вывод",
    )
    
    # inventory update
    inv_update = inv_subs.add_parser("update", help="Обновить инвентори из сканирования")
    inv_update.add_argument(
        "--inventory",
        required=True,
        help="Путь к файлу инвентори",
    )
    inv_update.add_argument(
        "--scan",
        action="store_true",
        help="Выполнить новое сканирование",
    )
    inv_update.add_argument(
        "--networks",
        help="Сети для сканирования через запятую",
    )

    # audit-remote
    sub_audit_remote = subs.add_parser("audit-remote", help="Удалённый запуск аудита на хостах")
    sub_audit_remote.add_argument(
        "--inventory",
        required=True,
        help="Путь к файлу инвентори",
    )
    sub_audit_remote.add_argument(
        "--output-dir",
        default="results/remote",
        help="Директория для сохранения результатов (по умолчанию: results/remote)",
    )
    sub_audit_remote.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Количество параллельных workers (по умолчанию: 10)",
    )
    sub_audit_remote.add_argument(
        "--profile",
        help="Профиль аудита (переопределяет профили из инвентори)",
    )
    sub_audit_remote.add_argument(
        "--level",
        choices=["baseline", "strict", "paranoid"],
        default="baseline",
        help="Уровень строгости (по умолчанию: baseline)",
    )
    sub_audit_remote.add_argument(
        "--fail-level",
        choices=["none", "low", "medium", "high"],
        default="none",
        help="Порог неуспеха (по умолчанию: none)",
    )
    sub_audit_remote.add_argument(
        "--evidence",
        action="store_true",
        help="Собирать evidence (улики)",
    )
    sub_audit_remote.add_argument(
        "--group",
        help="Фильтр по группе хостов",
    )
    sub_audit_remote.add_argument(
        "--tags",
        help="Фильтр по тегам через запятую",
    )
    sub_audit_remote.add_argument(
        "--os",
        dest="os_filter",
        help="Фильтр по ОС",
    )
    sub_audit_remote.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Таймаут выполнения на одном хосте в секундах (по умолчанию: 300)",
    )

    # audit-agentless (рекомендуемый подход)
    sub_audit_agentless = subs.add_parser("audit-agentless", help="Agentless аудит (БЕЗ установки на целевые хосты)")
    sub_audit_agentless.add_argument(
        "--inventory",
        required=True,
        help="Путь к файлу инвентори",
    )
    sub_audit_agentless.add_argument(
        "--output-dir",
        default="results/agentless",
        help="Директория для сохранения результатов (по умолчанию: results/agentless)",
    )
    sub_audit_agentless.add_argument(
        "--profile",
        required=True,
        help="Путь к профилю аудита",
    )
    sub_audit_agentless.add_argument(
        "--level",
        choices=["baseline", "strict", "paranoid"],
        default="baseline",
        help="Уровень строгости (по умолчанию: baseline)",
    )
    sub_audit_agentless.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Количество параллельных workers (по умолчанию: 10)",
    )
    sub_audit_agentless.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Таймаут выполнения одной команды в секундах (по умолчанию: 30)",
    )
    sub_audit_agentless.add_argument(
        "--ssh-timeout",
        type=int,
        default=10,
        help="Таймаут SSH подключения в секундах (по умолчанию: 10)",
    )
    sub_audit_agentless.add_argument(
        "--group",
        help="Фильтр по группе хостов",
    )
    sub_audit_agentless.add_argument(
        "--tags",
        help="Фильтр по тегам через запятую",
    )
    sub_audit_agentless.add_argument(
        "--os",
        dest="os_filter",
        help="Фильтр по ОС",
    )

    args = parser.parse_args(argv)
    profile_from_position = getattr(args, "profile_path", None)
    if profile_from_position is not None:
        args.profile = profile_from_position
    elif not hasattr(args, "profile"):
        args.profile = default_profile
    if hasattr(args, "profile_path"):
        delattr(args, "profile_path")

    if getattr(args, "info", False):
        if getattr(args, "command", None):
            parser.error("--info нельзя использовать вместе с командами")
        return args

    if getattr(args, "command", None) is None:
        parser.print_help()
        sys.exit(1)
    if getattr(args, "command", None) == "audit":
        try:
            args.vars = parse_kv_pairs(getattr(args, "var", None), option="--var")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)
        if hasattr(args, "var"):
            delattr(args, "var")
    return args


# ──────────────────────────────────────────────────────────────────────────────
# Точка входа для «standalone» запуска cli.py (необязательна)
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    """Небольшой удобный раннер — полезен для отладки самого cli.py."""
    args = parse_args()
    try:
        profile = load_profile_file(args.profile)
    except MissingDependencyError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(3)

    if args.command == "list-modules":
        list_modules(profile)
        return

    if args.command == "list-checks":
        try:
            tag_filters = parse_tag_filters(getattr(args, "tags", None))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)
        list_checks(profile, args.module, tag_filters)
        return

    if args.command == "describe-check":
        describe_check(profile, args.check_id)
        return

    if args.command == "validate":
        ok, errs = validate_profile(profile)
        if ok:
            print("Профиль валиден.")
            sys.exit(0)
        print("Профиль невалиден:")
        for e in errs:
            print(f"  - {e}")
        # strict — вернуть 1; без strict — вернуть 0 (предупреждение)
        sys.exit(1 if args.strict else 0)

    if args.command == "audit":
        # Здесь ничего не делаем — аудит выполняется в secaudit/main.py
        # Этот блок оставлен для ясности.
        print("Используйте основной лаунчер (secaudit/main.py) для запуска аудита.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
