
#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT=${1:-secaudit-core}
PROJECT_NAME=$(basename "${PROJECT_ROOT}")

log() {
  printf '[+] %s\n' "$1"
}

log "Инициализация структуры SecAudit-core в '${PROJECT_ROOT}'"

mkdir -p "${PROJECT_ROOT}"
cd "${PROJECT_ROOT}"

DIRECTORIES=(
  "docs"
  "modules"
  "profiles/base"
  "profiles/common"
  "profiles/include"
  "profiles/os"
  "profiles/roles"
  "profiles/szi"
  "reports"
  "results"
  "seclib"
  "secaudit"
  "tests"
  "utils"
  "workflows"
)

for dir in "${DIRECTORIES[@]}"; do
  mkdir -p "${dir}"
done

touch results/.gitkeep

log "Создание README"
cat <<EOF > README.md
# ${PROJECT_NAME}

SecAudit-core — CLI-инструмент для аудита безопасности Linux-систем.
Генерируемая структура включает профили аудита на YAML, движок
выполнения проверок и вспомогательные библиотеки. Начните с установки
зависимостей и запуска `secaudit --help`.
EOF

log "Создание файла зависимостей"
cat <<'EOF' > requirements.txt
PyYAML>=6.0.1
colorama>=0.4.6
Jinja2>=3.1.4
jsonschema>=4.0.0
packaging>=24.0
pytest>=8.2.0
flake8>=7.1.0
mypy>=1.10.0
yamllint>=1.35.1
EOF

log "Создание pyproject.toml"
cat <<'EOF' > pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "secaudit"
version = "0.1.0"
description = "SecAudit++ core CLI"
readme = "README.md"
requires-python = ">=3.10"
authors = [{ name = "Your Name" }]
dependencies = [
  "PyYAML>=6.0.1",
  "Jinja2>=3.1.4",
  "colorama>=0.4.6",
  "jsonschema>=4.0.0",
  "packaging>=24.0"
]

[project.scripts]
secaudit = "secaudit.main:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["secaudit*", "modules*", "utils*", "seclib*"]

[tool.setuptools.package-data]
secaudit = ["*.j2"]
EOF

log "Создание .gitignore"
cat <<'EOF' > .gitignore
.DS_Store
# Python
__pycache__/
*.pyc

# VSCode/IDE
.vscode/
.idea/

# Logs
*.log

# Reports
results/*.json
results/*.html
results/*.md

# PyInstaller
dist/
build/

# Venv
venv/
.env
EOF

log "Создание main.py"
cat <<'EOF' > main.py
"""Точка входа для запуска CLI напрямую через Python."""

from secaudit.main import main


if __name__ == "__main__":
    main()
EOF

log "Создание пакета modules"
cat <<'EOF' > modules/__init__.py
"""Пакет с основными модулями аудита."""
EOF

cat <<'EOF' > modules/assert_logic.py
"""Утилиты сравнения результатов команд с ожиданиями."""

from enum import Enum, auto
import re


class AssertStatus(Enum):
    PASS = auto()
    FAIL = auto()
    WARN = auto()


def assert_output(output: str, expected: str, assert_type: str) -> str:
    """Базовые проверки соответствия вывода ожидаемым значениям."""

    if assert_type == "exact":
        return AssertStatus.PASS.name if output.strip() == expected.strip() else AssertStatus.FAIL.name
    if assert_type == "contains":
        return AssertStatus.PASS.name if expected in output else AssertStatus.FAIL.name
    if assert_type == "not_contains":
        return AssertStatus.PASS.name if expected not in output else AssertStatus.FAIL.name
    if assert_type == "regexp":
        try:
            return AssertStatus.PASS.name if re.search(expected, output) else AssertStatus.FAIL.name
        except re.error:
            return AssertStatus.FAIL.name
    return AssertStatus.WARN.name
EOF

cat <<'EOF' > modules/bash_executor.py
"""Запуск системных команд для аудита."""

from __future__ import annotations

import subprocess
from typing import Iterable


def run_command(command: Iterable[str]) -> subprocess.CompletedProcess[str]:
    """Выполняет команду в оболочке и возвращает CompletedProcess."""

    return subprocess.run(list(command), capture_output=True, text=True, check=False)


def run_script(script: str) -> subprocess.CompletedProcess[str]:
    """Запускает произвольный скрипт Bash."""

    return subprocess.run(script, capture_output=True, text=True, check=False, shell=True)
EOF

cat <<'EOF' > modules/audit_runner.py
"""Управление запуском набора проверок."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping

from modules import assert_logic
from modules import bash_executor


@dataclass
class AuditCheck:
    identifier: str
    command: Iterable[str] | str
    expect: str
    assert_type: str = "exact"


def execute_check(check: AuditCheck) -> Mapping[str, str]:
    """Выполняет проверку и возвращает статус."""

    if isinstance(check.command, str):
        result = bash_executor.run_script(check.command)
    else:
        result = bash_executor.run_command(check.command)

    status = assert_logic.assert_output(result.stdout, check.expect, check.assert_type)
    return {
        "id": check.identifier,
        "status": status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": str(result.returncode),
    }


def run_audit(checks: Iterable[AuditCheck]) -> List[Mapping[str, str]]:
    """Запускает серию проверок."""

    return [execute_check(check) for check in checks]
EOF

cat <<'EOF' > modules/os_detect.py
"""Примитивное определение дистрибутива."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


def detect_os() -> Mapping[str, str]:
    """Возвращает словарь с базовой информацией об ОС."""

    release = Path("/etc/os-release")
    data: dict[str, str] = {}
    if release.exists():
        for line in release.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key] = value.strip().strip('"')
    return data
EOF

cat <<'EOF' > modules/report_generator.py
"""Генерация простых Markdown- и HTML-отчётов."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from jinja2 import Environment, FileSystemLoader


def _environment() -> Environment:
    templates_dir = Path("reports")
    return Environment(loader=FileSystemLoader(str(templates_dir)))


def render_report(template: str, results: Iterable[Mapping[str, str]], destination: Path) -> None:
    env = _environment()
    template_obj = env.get_template(template)
    destination.write_text(template_obj.render(results=list(results)), encoding="utf-8")
EOF

cat <<'EOF' > modules/cli.py
"""Аргументный парсер командной строки."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from modules.audit_runner import AuditCheck, run_audit
from modules.report_generator import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="secaudit", description="SecAudit-core CLI")
    parser.add_argument("profile", help="Путь к YAML-профилю аудита")
    parser.add_argument("--report", choices=["markdown", "html"], help="Тип итогового отчёта")
    parser.add_argument("--template", help="Имя файла шаблона отчёта", default="report_template.md.j2")
    parser.add_argument("--output", help="Путь для сохранения отчёта", default="results/report.md")
    return parser


def load_profile(profile_path: Path) -> Iterable[AuditCheck]:
    del profile_path
    return [AuditCheck("sample-echo", ["echo", "hello"], expect="hello")]


def main(args: list[str] | None = None) -> int:
    parser = build_parser()
    namespace = parser.parse_args(args=args)

    checks = load_profile(Path(namespace.profile))
    results = run_audit(checks)

    if namespace.report:
        output_path = Path(namespace.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template_name = "report_template.html.j2" if namespace.report == "html" else namespace.template
        render_report(template_name, results, output_path)

    return 0
EOF

log "Создание пакета utils"
cat <<'EOF' > utils/logger.py
"""Конфигурация базового логгера."""

import logging
from typing import Optional


def configure(level: int = logging.INFO, name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
EOF

log "Создание пакета seclib"
cat <<'EOF' > seclib/validator.py
"""Примитивная валидация профилей."""

from __future__ import annotations

from pathlib import Path

import yaml


class ValidationError(RuntimeError):
    """Ошибка структуры профиля."""


def validate_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - демонстрационный код
        raise ValidationError(str(exc)) from exc
    if not isinstance(data, dict):
        raise ValidationError("Профиль должен быть словарём")
    return data
EOF

log "Создание пакета secaudit"
cat <<'EOF' > secaudit/__init__.py
"""Пакет верхнего уровня SecAudit."""
EOF

cat <<'EOF' > secaudit/exceptions.py
"""Общие исключения CLI."""


class SecAuditError(Exception):
    """Базовое исключение SecAudit."""
EOF

cat <<'EOF' > secaudit/main.py
"""Входная точка для установленного пакета."""

from __future__ import annotations

import sys

from modules.cli import main as cli_main


def main() -> None:
    exit_code = cli_main()
    sys.exit(exit_code)
EOF

cat <<'EOF' > secaudit/__main__.py
"""Запуск через python -m secaudit."""

from .main import main


if __name__ == "__main__":
    main()
EOF

log "Создание профилей"
cat <<'EOF' > profiles/README.md
# Профили SecAudit

Каталог содержит YAML-профили, разделённые на уровни:

- `base/` — базовые роли.
- `os/` — специфичные настройки для дистрибутивов.
- `roles/` — прикладные роли.
- `szi/` — профили для СЗИ.
- `include/` — общие шаблоны и переменные.
EOF

cat <<'EOF' > profiles/base/linux.yml
extends:
  - "../include/linux_hardening.yml"

vars:
  defaults:
    FAILLOCK_DENY: "5"

checks:
  - id: "sample-echo"
    module: "system"
    command: ["echo", "hello"]
    expect: "hello"
    assert_type: "exact"
    severity: "low"
EOF

cat <<'EOF' > profiles/include/linux_hardening.yml
checks:
  - id: "ensure-tmp-noexec"
    module: "filesystem"
    command: "mount"
    expect: "tmpfs on /tmp"
    assert_type: "contains"
    severity: "medium"
EOF

cat <<'EOF' > profiles/include/vars_baseline.env
# Значения переменных для уровня baseline
FAILLOCK_DENY=5
EOF

cat <<'EOF' > profiles/include/vars_strict.env
# Значения переменных для уровня strict
FAILLOCK_DENY=3
EOF

cat <<'EOF' > profiles/include/vars_paranoid.env
# Значения переменных для уровня paranoid
FAILLOCK_DENY=2
EOF

log "Создание документации"
cat <<'EOF' > docs/roadmap.md
# Roadmap

- [ ] Улучшить парсер профилей
- [ ] Добавить сбор улик
- [ ] Реализовать экспорт в PDF
EOF

cat <<'EOF' > docs/user_guide.md
# Руководство пользователя

1. Установите зависимости с помощью `pip install -e .`.
2. Проверьте доступные команды `secaudit --help`.
3. Настройте профиль в каталоге `profiles/` и запустите аудит.
EOF

log "Создание шаблонов отчётов"
cat <<'EOF' > reports/report_template.md.j2
# Результаты аудита

{% for check in results %}
- **{{ check.id }}** — {{ check.status }}
{% endfor %}
EOF

cat <<'EOF' > reports/report_template.html.j2
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>SecAudit report</title>
  </head>
  <body>
    <h1>Результаты аудита</h1>
    <ul>
      {% for check in results %}
      <li><strong>{{ check.id }}</strong> — {{ check.status }}</li>
      {% endfor %}
    </ul>
  </body>
</html>
EOF

log "Создание тестов"
cat <<'EOF' > tests/__init__.py
"""Пакет с тестами."""
EOF

cat <<'EOF' > tests/test_cli.py
from modules.cli import build_parser


def test_parser_has_profile_argument():
    parser = build_parser()
    assert any(action.dest == "profile" for action in parser._actions)
EOF

cat <<'EOF' > tests/test_assert_logic.py
from modules.assert_logic import assert_output


def test_exact_match():
    assert assert_output("hello", "hello", "exact") == "PASS"
EOF

log "Создание workflows"
cat <<'EOF' > workflows/ci.yml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest
EOF

cat <<'EOF' > workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build
      - run: python -m build
EOF

cat <<'EOF' > workflows/Makefile
.RECIPEPREFIX := >
.PHONY: lint test

lint:
>flake8 modules secaudit seclib utils

test:
>pytest
EOF

log "Структура SecAudit-core подготовлена"
