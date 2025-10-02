# seclib/validator.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

try:
    from jsonschema import Draft7Validator
    from jsonschema.exceptions import ValidationError
except Exception as e:
    # Жёсткое требование jsonschema в зависимостях проекта
    raise RuntimeError(
        "Требуется пакет 'jsonschema' (pip install jsonschema)"
    ) from e

PROFILE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "profile_name", "description", "checks"],
    "properties": {
        "schema_version": {"type": "string", "pattern": r"^1\.\d+$"},
        "profile_name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "checks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "name",
                    "module",
                    "command",
                    "expect",
                    "assert_type",
                    "severity",
                    "tags",
                ],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1},
                    "module": {"type": "string", "minLength": 1},
                    "command": {"type": "string", "minLength": 1},
                    "expect": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "integer"},
                            {"type": "number"},
                            {"type": "boolean"},
                            {"type": "object"},
                            {"type": "array"},
                            {"type": "null"},
                        ]
                    },
                    "assert_type": {
                        "type": "string",
                        "enum": [
                            "exact",
                            "contains",
                            "not_contains",
                            "regexp",
                            "exit_code",
                            "jsonpath",
                            "version_gte",
                            "int_lte",
                        ],
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "tags": {
                        "type": "object",
                        "additionalProperties": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                            ]
                        },
                    },
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 600},
                    "rc_ok": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0, "maximum": 255},
                        "minItems": 1,
                        "maxItems": 8,
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}

def _format_error(e: ValidationError) -> str:
    """Форматирует ошибку jsonschema в человекочитаемую строку."""
    path = "$"
    if e.absolute_path:
        path = "$." + ".".join(str(p) for p in e.absolute_path)
    return f"{path}: {e.message}"

def normalize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Приводит регистры и проводит мягкую нормализацию. Модифицирует объект на месте."""
    for chk in profile.get("checks", []):
        if "severity" in chk and isinstance(chk["severity"], str):
            chk["severity"] = chk["severity"].strip().lower()
        if "assert_type" in chk and isinstance(chk["assert_type"], str):
            chk["assert_type"] = chk["assert_type"].strip().lower()
        if "module" in chk and isinstance(chk["module"], str):
            chk["module"] = chk["module"].strip().lower()
    return profile

def _check_unique_ids(checks: List[Dict[str, Any]]) -> List[str]:
    """Проверяет уникальность ID всех проверок в профиле."""
    seen = set()
    duplicates = []
    for c in checks:
        cid = c.get("id")
        if cid in seen:
            duplicates.append(cid)
        else:
            seen.add(cid)
    # Возвращаем только уникальные дубликаты
    return sorted(list(set(duplicates)))

def _precompile_regexps(checks: List[Dict[str, Any]]) -> List[str]:
    """Проверяет, что все регулярные выражения в профиле корректны."""
    errors: List[str] = []
    for c in checks:
        if c.get("assert_type") == "regexp":
            pattern = c.get("expect", "")
            try:
                re.compile(pattern)
            except re.error as ex:
                errors.append(f"check id '{c.get('id')}': invalid regexp in 'expect': {ex}")
    return errors

def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Валидирует YAML-профиль по JSON-схеме.
    Возвращает (is_valid, errors[]).
    """
    profile = normalize_profile(profile)
    validator = Draft7Validator(PROFILE_SCHEMA)
    errors: List[str] = []
    for err in sorted(validator.iter_errors(profile), key=lambda e: e.path):
        loc = " -> ".join([str(p) for p in err.path]) or "<root>"
        errors.append(f"{loc}: {err.message}")
    errors.extend(_check_unique_ids(profile.get("checks", [])))
    errors.extend(_precompile_regexps(profile.get("checks", [])))
    return (len(errors) == 0, errors)

def severity_rank(sev: str) -> int:
    """Возвращает числовой ранг для строки с уровнем критичности."""
    return SEVERITY_RANK.get(sev.strip().lower(), 0)
