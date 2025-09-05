# modules/cli.py
import argparse
import sys
import yaml
from pathlib import Path
from typing import Tuple, List, Dict, Any

# Пытаемся подключить jsonschema, чтобы валидировать профиль.
# Если библиотека не установлена — работаем без "жёсткой" валидации.
try:
    from jsonschema import validate as js_validate
    from jsonschema.exceptions import ValidationError as JSValidationError
    _HAS_JSONSCHEMA = True
except Exception:
    _HAS_JSONSCHEMA = False


# ──────────────────────────────────────────────────────────────────────────────
# Мини-схема профиля (упрощённая, без жесткого перечисления всех полей check)
# ──────────────────────────────────────────────────────────────────────────────
_PROFILE_SCHEMA = {
    "type": "object",
    "required": ["profile_name", "description", "checks"],
    "properties": {
        "profile_name": {"type": "string"},
        "description": {"type": "string"},
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "module", "command", "expect", "assert_type", "severity"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "module": {"type": "string"},
                    "command": {"type": "string"},
                    "expect": {"type": "string"},
                    # Допустимые типы сравнения: exact | contains | not_contains | regexp | exit_code
                    "assert_type": {
                        "type": "string",
                        "enum": [
                            "exact",
                            "contains",
                            "not_contains",
                            "regexp",
                            "exit_code",
                        ],
                    },
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    # Важно: теги — словарь {строка: строка}. Если у тебя массивы, конверти в строку заранее.
                    "tags": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "additionalProperties": True
            }
        }
    },
    "additionalProperties": True
}


# ──────────────────────────────────────────────────────────────────────────────
# Утилиты печати из профиля (их импортирует твой main.py)
# ──────────────────────────────────────────────────────────────────────────────
def list_modules(profile: Dict[str, Any]) -> None:
    """Печатает отсортированный список уникальных модулей из профиля."""
    modules = {check.get("module", "core") for check in profile.get("checks", [])}
    for m in sorted(modules):
        print(m)


def list_checks(profile: Dict[str, Any], module: str | None = None) -> None:
    """Печатает список проверок, опционально фильтруя по модулю."""
    for check in profile.get("checks", []):
        if module and check.get("module") != module:
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
    required_top = ["profile_name", "description", "checks"]
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
def _parent_parser() -> argparse.ArgumentParser:
    """Родительский парсер с общими для подкоманд аргументами (если нужно)."""
    parent = argparse.ArgumentParser(add_help=False)
    return parent


def parse_args() -> argparse.Namespace:
    """
    Глобальный флаг --profile разрешён и до, и после команды.
    Примеры:
      secaudit --profile profiles/alt.yml list-modules
      secaudit list-modules --profile profiles/alt.yml
    """
    parent = _parent_parser()

    parser = argparse.ArgumentParser(
        prog="secaudit",
        description="SecAudit++ CLI — запуск аудита, валидация профиля и служебные команды.",
    )

    # Глобальный флаг профиля — можно ставить до/после команды
    parser.add_argument(
        "--profile",
        default="profiles/common/baseline.yml",
        help="Путь к YAML-профилю (по умолчанию: profiles/common/baseline.yml)",
    )

    subs = parser.add_subparsers(dest="command", required=True, help="Доступные команды")

    # list-modules
    subs.add_parser("list-modules", parents=[parent], help="Показать все модули в профиле")

    # list-checks
    sub_checks = subs.add_parser("list-checks", parents=[parent], help="Показать проверки")
    sub_checks.add_argument("--module", help="Фильтровать проверки по модулю")

    # describe-check
    sub_desc = subs.add_parser("describe-check", parents=[parent], help="Детали проверки по ID")
    sub_desc.add_argument("check_id", help="ID проверки")

    # validate
    sub_val = subs.add_parser("validate", parents=[parent], help="Проверить профиль на ошибки")
    sub_val.add_argument("--strict", action="store_true", help="Строгий режим: код возврата 1 при предупреждениях")

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

    return parser.parse_args()


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
        list_checks(profile, args.module)
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
