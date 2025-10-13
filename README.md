# SecAudit+

SecAudit-core — инструмент командной строки для аудита безопасности GNU/Linux. Профили аудита описываются на YAML и объединяют требования ФСТЭК, CIS Benchmarks и внутренних регламентов. Движок поддерживает наследование профилей, шаблоны Jinja2 и подробные отчёты в JSON, Markdown и HTML.

## Основные возможности

- **Расширяемые профили.** Базовые, ОС-специфичные и ролевые YAML-файлы собираются каскадом через `extends` и не допускают дублирования идентификаторов проверок благодаря тестам на наследование.
- **Гибкая параметризация.** Переменные задаются значениями по умолчанию, уровнями строгости (`baseline`, `strict`, `paranoid`), файлами `vars_*.env` и переопределениями из CLI (`--var KEY=VALUE`).
- **Диагностика и отчётность.** Итог содержит оценки, покрытие, топ критичных отклонений и, при необходимости, артефакты команд (evidence). Отчёты собираются через шаблоны Jinja2 в `reports/`.
- **Разнообразие проверок.** Проверяются PAM, sudo, учётные записи, файлы, сетевые службы, контейнеры, политики журналирования и другие направления, включая отраслевые профили (например, Secret Net LSP).
- **Автоматизация.** CLI совместим с CI/CD: политика завершения настраивается флагами `--fail-level` и `--fail-on-undef`, а структура репозитория содержит готовый workflow GitHub Actions.

## Требования

- Python 3.10+
- Системные пакеты: `python3-venv`, `python3-dev`, компилятор C (для установки зависимостей)
- Зависимости проекта перечислены в `requirements.txt` и `pyproject.toml`

## Быстрый старт

```bash
# Клонирование и установка зависимостей
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core
python3 -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -e .

# Проверка доступных команд
secaudit --info
secaudit --help

# Быстрая валидация профиля
secaudit validate --profile profiles/base/linux.yml

# Аудит с уровнем strict и сохранением улик
secaudit audit \
  --profile profiles/base/server.yml \
  --level strict \
  --workers 4 \
  --fail-level medium \
  --evidence results/evidence \
  --var FAILLOCK_DENY=5
```

CLI можно запускать и напрямую через интерпретатор: `python3 main.py ...` — модуль `main.py` всего лишь вызывает `secaudit.main:main`.

## Структура команд CLI

| Команда | Назначение |
|---------|------------|
| `secaudit list-modules` | Список модулей профиля (например, `system`, `network`, `services`). |
| `secaudit list-checks [--module NAME] [--tags KEY=VALUE]` | Перечень проверок с фильтрами по модулю и тегам. |
| `secaudit describe-check <ID>` | Детали конкретной проверки (команда, ожидаемый результат, теги). |
| `secaudit validate [--strict]` | Валидация профиля по JSON-схеме. В строгом режиме ошибки возвращают код 2. |
| `secaudit audit [OPTIONS]` | Полноценный запуск аудита и генерация отчётов. |

Глобальные флаги:

- `--profile PATH` или позиционный аргумент — путь к YAML-профилю; при отсутствии выбирается профиль по идентификатору текущей ОС или `profiles/common/baseline.yml`.
- `-i/--info` — информация о проекте.

Параметры команды `audit`:

- `--module system,network` — запуск выбранных модулей.
- `--level baseline|strict|paranoid` — уровень строгости (по умолчанию берётся из `SECAUDIT_LEVEL`).
- `--var KEY=VALUE` — переопределение переменных профиля (можно указывать несколько раз).
- `--workers N` — количество параллельных потоков (0 — авто или `SECAUDIT_WORKERS`).
- `--fail-level none|low|medium|high` — порог для кода возврата 2.
- `--fail-on-undef` — завершить с кодом 2, если есть результаты `UNDEF`.
- `--evidence DIR` — сохранить вывод команд в каталог.

## Архитектура профилей

Каталог `profiles/` содержит четыре слоя:

- `profiles/base/` — базовые роли (рабочая станция, сервер, минимальный Linux).
- `profiles/os/` — дистрибутив-специфичные дополнения и переопределения.
- `profiles/roles/` — прикладные роли (киоск, сервер БД и т.д.).
- `profiles/szi/` — профили для средств защиты информации.

Общие константы и шаблоны лежат в `profiles/include/`. Файлы подключаются через ключ `extends`, например:

```yaml
extends:
  - "../include/linux_hardening.yml"
  - "../base/linux.yml"
```

Каждая проверка задаёт:

- `id` — уникальный идентификатор (контролируется тестами в `tests/test_profiles.py`).
- `module` — тематический блок (system, network, services, integrity…).
- `command` — выполняемая команда или сценарий.
- `expect` + `assert_type` (`exact`, `contains`, `regexp`, `jsonpath`, `not_contains`).
- `severity` — уровень серьёзности (`low`, `medium`, `high`).
- `tags` — ссылки на нормативные требования и внутренние классификаторы.
- `remediation`, `ref`, `evidence` — опциональные поля для пояснений и сбора артефактов.

### Переменные и уровни строгости

Секция `vars` внутри профиля позволяет определить значения по умолчанию, уровневые настройки и дополнительные файлы:

```yaml
vars:
  defaults:
    FAILLOCK_DENY: "5"
  levels:
    strict:
      FAILLOCK_DENY: "3"
  files:
    - "../include/common.env"
  optional_files:
    - "../include/{{ level }}.env"
```

Дополнительно движок автоматически подключает `profiles/include/vars_<level>.env`. Любые значения можно переопределить через `--var KEY=VALUE` или переменные окружения перед запуском.

## Каталоги репозитория

```
secaudit-core/
├─ main.py              # Альтернативная точка входа CLI
├─ secaudit/            # Пакет CLI и служебные исключения
├─ modules/             # Исполнитель аудита, CLI-парсер, генератор отчётов
├─ seclib/              # Схемы и валидаторы профилей
├─ profiles/            # YAML-профили и include-файлы
├─ reports/             # Шаблоны отчётов (Jinja2)
├─ tests/               # Юнит-тесты и регрессия профилей
├─ docs/                # Расширенная документация и дорожные карты
├─ workflows/           # Примеры интеграции с CI
├─ utils/               # Вспомогательные скрипты и преобразования
├─ results/             # Каталог для отчётов (создаётся автоматически)
├─ requirements.txt
├─ pyproject.toml
└─ init.sh
```

## Отчётность и артефакты

После выполнения аудита в каталоге `results/` появятся файлы:

- `report.json` — полный список проверок с результатами и сводкой.
- `report_grouped.json` — результаты, сгруппированные по модулям.
- `report.md` — Markdown-отчёт с аккордеонами по модулям.
- `report_<hostname>_<timestamp>.html` — HTML-отчёт с визуальными индикаторами.
- Каталог `evidence/` (если передан `--evidence`) с вырезками команд.

Сводка содержит итоговый балл, покрытие, список провалов с наибольшим весом и сопоставление требований ФСТЭК благодаря преобразованиям в `modules/report_generator.py`. Отдельный блок «Remediation» в HTML/Markdown-отчётах агрегирует проваленные проверки с заполненным полем `remediation`, чтобы команды эксплуатации сразу видели план действий.

## Интеграция с Ansible и SaltStack

### Ansible

SecAudit удобно вызывать из плейбуков для регулярного контроля Golden-образов или серверов. Ниже пример роли, которая выполняет аудит и собирает отчёты как артефакты:

```yaml
- name: Аудит хоста SecAudit
  hosts: all
  become: true
  vars:
    secaudit_repo: /opt/secaudit-core
    secaudit_bin: /opt/secaudit-core/.venv/bin/secaudit
    secaudit_profile: profiles/base/server.yml
  tasks:
    - name: Запуск SecAudit с уровнем strict
      ansible.builtin.command:
        cmd: >-
          {{ secaudit_bin }} audit
          --profile {{ secaudit_profile }}
          --level strict
          --fail-level medium
          --evidence results/evidence
      args:
        chdir: "{{ secaudit_repo }}"
      register: secaudit_run
      changed_when: false
      failed_when: secaudit_run.rc not in [0, 2]

    - name: Сбор отчётов как артефактов
      ansible.builtin.fetch:
        src: "{{ secaudit_repo }}/results/report_{{ inventory_hostname }}.html"
        dest: "artifacts/"
        flat: false

    - name: Прервать плейбук при критическом несоответствии
      ansible.builtin.fail:
        msg: "SecAudit обнаружил несоответствия уровня medium и выше"
      when: secaudit_run.rc == 2
```

Регистрируйте код возврата: `0` означает чистый аудит, `2` — найдены проблемы ≥ выбранного `--fail-level`. Сами отчёты можно прикреплять к тикетам, а поле `remediation` использовать для генерации оперативных задач.

### SaltStack

В SaltStack аудит подключается в виде состояния `cmd.run`. Пример проверяет образ на этапе сборки и сохраняет артефакты в кэше minion:

```yaml
secaudit_audit:
  cmd.run:
    - name: >-
        /opt/secaudit-core/.venv/bin/secaudit audit
        --profile profiles/base/linux.yml
        --level baseline
        --fail-level low
        --evidence results/evidence
    - cwd: /opt/secaudit-core
    - env:
        SECAUDIT_WORKERS: '4'
    - success_retcodes:
        - 0
        - 2
    - require:
        - file: secaudit_checkout

fetch_reports:
  file.recurse:
    - name: salt://artifacts/{{ grains['id'] }}/
    - source: salt://{{ salt['config.get']('cachedir') }}/secaudit/results/
    - require:
        - cmd: secaudit_audit
```

Код возврата `2` трактуется как «успешно, но найдены несоответствия» и не прерывает пайплайн. Сохранённые отчёты можно анализировать вручную или отправлять в SIEM.

## Тестирование и качество

- `pytest` — проверка вспомогательных функций и регрессия наследования профилей.
- `yamllint` — статический анализ YAML (используется в CI).
- `flake8`, `mypy` — линтеры и статический анализ (см. `workflows/ci.yml`).

Запуск локально:

```bash
pytest
yamllint profiles
flake8
mypy
```

## Дополнительные материалы

- [Руководство пользователя](docs/user_guide.md)
- [Дорожная карта и статус покрытия](docs/roadmap.md)

Обратная связь и предложения приветствуются через issue tracker.
