# modules/cli.py
import argparse
import sys
import yaml
from pathlib import Path
from typing import Tuple, List, Dict, Any

from seclib.validator import PROFILE_SCHEMA as STRICT_PROFILE_SCHEMA

# Пытаемся подключить jsonschema, чтобы валидировать профиль.
# Если библиотека не установлена — работаем без "жёсткой" валидации.
try:
    from jsonschema import validate as js_validate
    from jsonschema.exceptions import ValidationError as JSValidationError
    _HAS_JSONSCHEMA = True
except Exception:
    _HAS_JSONSCHEMA = False


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


# ──────────────────────────────────────────────────────────────────────────────
# Загрузка профиля и опциональная валидация
# ──────────────────────────────────────────────────────────────────────────────
def load_profile_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        print(f"Ошибка: Файл профиля не найден: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
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
    if _HAS_JSONSCHEMA:
        try:
            js_validate(instance=profile, schema=_PROFILE_SCHEMA)
        except JSValidationError as e:
            # Разворачиваем путь для понятной трассировки
            path = " -> ".join(str(p) for p in e.path) if e.path else "<root>"
            errors.append(f"{path}: {e.message}")

    return (len(errors) == 0), errors


# ──────────────────────────────────────────────────────────────────────────────
# Парсинг аргументов
# ──────────────────────────────────────────────────────────────────────────────
def _parent_parser(default_profile: str) -> argparse.ArgumentParser:
    """Родительский парсер с общими для подкоманд аргументами (если нужно)."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--profile",
        default=argparse.SUPPRESS,
        help=f"Путь к YAML-профилю (по умолчанию: {default_profile})",
    )
    return parent


def _attach_positional_profile(subparser: argparse.ArgumentParser) -> None:
    """Добавляет опциональный позиционный аргумент для указания профиля."""

    subparser.add_argument(
        "profile_path",
        nargs="?",
        metavar="PROFILE",
        help=PROFILE_ARGUMENT_HELP,
    )


def parse_args() -> argparse.Namespace:
    """
    Глобальный флаг --profile разрешён и до, и после команды.
    Также можно указать путь к профилю последним позиционным аргументом:
      secaudit validate profiles/alt.yml
      secaudit audit profiles/alt.yml --fail-on-undef
    """
    default_profile = DEFAULT_PROFILE_PATH
    parent = _parent_parser(default_profile)

    parser = argparse.ArgumentParser(
        prog="secaudit",
        description="SecAudit++ CLI — запуск аудита, валидация профиля и служебные команды.",
    )

    # Глобальный флаг профиля — можно ставить до/после команды
    parser.add_argument(
        "--profile",
        default=default_profile,
        help=f"Путь к YAML-профилю (по умолчанию: {default_profile})",
    )

    subs = parser.add_subparsers(dest="command", required=True, help="Доступные команды")

    # list-modules
    sub_modules = subs.add_parser(
        "list-modules", parents=[parent], help="Показать все модули в профиле"
    )
    _attach_positional_profile(sub_modules)

    # list-checks
    sub_checks = subs.add_parser("list-checks", parents=[parent], help="Показать проверки")
    sub_checks.add_argument("--module", help="Фильтровать проверки по модулю")
    sub_checks.add_argument(
        "--tags",
        action="append",
        metavar="KEY=VALUE",
        help="Фильтр по тегам (можно указывать несколько раз)",
    )
    _attach_positional_profile(sub_checks)

    # describe-check
    sub_desc = subs.add_parser("describe-check", parents=[parent], help="Детали проверки по ID")
    sub_desc.add_argument("check_id", help="ID проверки")
    _attach_positional_profile(sub_desc)

    # validate
    sub_val = subs.add_parser("validate", parents=[parent], help="Проверить профиль на ошибки")
    sub_val.add_argument("--strict", action="store_true", help="Строгий режим: код возврата 1 при предупреждениях")
    _attach_positional_profile(sub_val)

    # audit
    sub_audit = subs.add_parser("audit", parents=[parent], help="Запустить аудит")
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
        help="Return exit code 2 if any check result is UNDEF."
    )
    sub_audit.add_argument(
        "--evidence",
        metavar="DIR",
        help="Каталог для сохранения выводов команд (улики)."
    )
    _attach_positional_profile(sub_audit)

    args = parser.parse_args()
    profile_from_position = getattr(args, "profile_path", None)
    if profile_from_position:
        args.profile = profile_from_position
    elif not hasattr(args, "profile"):
        args.profile = default_profile
    if hasattr(args, "profile_path"):
        delattr(args, "profile_path")
    return args


# ──────────────────────────────────────────────────────────────────────────────
# Точка входа для «standalone» запуска cli.py (необязательна)
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    """Небольшой удобный раннер — полезен для отладки самого cli.py."""
    args = parse_args()
    profile = load_profile_file(args.profile)

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
