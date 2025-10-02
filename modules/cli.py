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
@@ -130,124 +132,160 @@ def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
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

    Если флаг и позиционный аргумент переданы одновременно, предпочтение
    отдаётся позиционному значению, чтобы последняя указанная цель профиля
    всегда побеждала.
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
    if profile_from_position is not None:
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