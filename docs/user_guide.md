# Руководство пользователя SecAudit+

Документ описывает установку, запуск и использование CLI SecAudit+. Если вы только знакомитесь с проектом, начните с раздела «Быстрый старт» в [README](../README.md), затем возвращайтесь к детализированным сценариям ниже.

## 1. Установка и обновление

### 1.1. Подготовка окружения

Требуется Python 3.10+ и базовые инструменты сборки. На Debian/Ubuntu выполните:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-dev build-essential
```

На Red Hat/AlmaLinux:

```bash
sudo dnf install -y python3 python3-virtualenv python3-devel gcc
```

### 1.2. Установка из исходников

```bash
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Проект публикует исполняемый скрипт `secaudit`. Если нужно вызвать CLI без установки, используйте `python3 -m secaudit.main` или `python3 main.py` из корня репозитория.

### 1.3. Обновление

```bash
git pull
pip install -e . --upgrade
```

## 2. Основы CLI

Общий формат команд:

```bash
secaudit [ГЛОБАЛЬНЫЕ ОПЦИИ] <команда> [ОПЦИИ КОМАНДЫ]
```

Глобальные опции:

| Флаг | Описание |
|------|----------|
| `--profile PATH` | Явный путь к YAML-профилю. Можно указать и позиционным аргументом. |
| `-i`, `--info` | Вывести сведения о проекте и завершить работу. |

Если профиль не передан, SecAudit пытается подобрать файл по идентификатору ОС (`/etc/os-release`). В противном случае используется `profiles/common/baseline.yml`.

Каждая команда описана в таблице:

| Команда | Что делает | Типичное применение |
|---------|-------------|---------------------|
| `list-modules` | Показывает доступные модули проверок. | Получить обзор разделов профиля перед аудитом. |
| `list-checks` | Выводит проверки; поддерживает `--module` и `--tags KEY=VALUE`. | Поиск конкретных требований, фильтрация по нормативам ФСТЭК. |
| `describe-check <ID>` | Раскрывает содержимое проверки (команда, ожидания, теги). | Инвентаризация и отладка профиля. |
| `validate` | Проверяет профиль по JSON-схеме (`--strict` — код 2 при ошибках). | Перед выкладкой изменений в профили. |
| `audit` | Запускает аудит и формирует отчёты. | Основной режим использования. |
| `compare <before.json> <after.json>` | Сравнивает два отчёта и выводит регрессии/улучшения. | Анализ изменений Golden-образов и релизов. |

Встроенная помощь для любой команды доступна через `secaudit <команда> --help`.

## 3. Работа с профилями

### 3.1. Слои и наследование

Профили организованы слоями (`base`, `os`, `roles`, `szi`). YAML-файлы могут расширять друг друга с помощью `extends`. Наследование производится до запуска аудита: включаемые файлы объединяются, а идентификаторы проверок проверяются на уникальность модульными тестами.

### 3.2. Шаблоны и переменные

В секции `vars` описываются значения по умолчанию, уровневые настройки и файлы с переменными. Контекст формируется следующим образом:

1. Значения `defaults` из текущего профиля.
2. Файлы, перечисленные в `vars.files` (обязательные) и `vars.optional_files` (опциональные). Пути поддерживают шаблоны `{{ level }}`.
3. Значения для выбранного уровня строгости из `vars.levels[level]`.
4. Файл `profiles/include/vars_<level>.env`, если существует.
5. Переопределения из CLI (`--var KEY=VALUE`).

Контекст переменных доступен в полях `command`, `expect`, `when`, `extends` и других строковых значениях профиля. Для удобства можно хранить набор переменных в `.env` и подключать через `vars.files`.

### 3.3. Фильтры `when`

Поля `when` позволяют ограничивать проверку по ОС, роли или произвольным фактам. Доступны ключи `os.id`, `os.version_id`, `level` и значения из `vars`. Пример:

```yaml
when:
  any:
    - os.id: "debian"
    - os.id_like: "debian"
```

Если условие не выполняется, проверка получает статус `SKIP`.

### 3.4. Примеры прикладных профилей

- **Сервер баз данных (`profiles/roles/db.yml`).** Наследует базовый серверный профиль и добавляет проверки жизненного цикла PostgreSQL: активность и включение systemd-юнитов, требование `ssl = on` и `log_connections = on`, отсутствие `trust` в `pg_hba.conf`, а также права/владельца каталога `/var/lib/postgresql` и неинтерактивную оболочку пользователя `postgres`.
- **Киосковый терминал (`profiles/roles/kiosk.yml`).** Поверх рабочего стола проверяет, что GDM настроен на автологин выделенного пользователя, Firefox запускается в режиме Kiosk по политике, отключены дополнительные `getty@tty*` и маскирован `ctrl-alt-del.target`, а пакетный менеджер блокирует фоновые автообновления.

### 3.5. Приоритизированные allow/deny-листы

Поля `allowlist` и `denylist` принимают не только путь к файлу, но и структуру:

```yaml
asserts:
  - allowlist:
      mode: subset
      sources:
        - file: "../include/base_allow.txt"
          priority: 0
        - values: ["tcp:8443"]
          priority: 10
        - values: ["tcp:8080"]
          priority: 20
          effect: remove
```

Каждый источник задаёт `priority` (чем выше, тем сильнее переопределение) и `effect`: `include` добавляет значения, `remove` или `effect: remove` исключает их из итогового набора. Аналогично работает `denylist`, что позволяет строить ролевые исключения без дублирования списков.

### 3.6. Новые сценарии рабочих станций и контейнеров

- **Рабочие станции с GUI (`profiles/base/workstation.yml`).** Профиль теперь расширяет `profiles/include/workstation_hardening.yml`, который задаёт переменные `GUI_IDLE_TIMEOUT` и `GUI_LOCK_DELAY` и включает проверки на принудительную блокировку экрана GNOME, фиксацию параметров через `dconf`-locks, отключение Bluetooth AutoEnable и чёрные списки USB-модулей. Дополнительные проверки анализируют политики Firefox/Chromium: наличие обязательного `policies.json`, запрет телеметрии и единый корпоративный стартовый URL. Значения переменных можно переопределять на уровне ролей или через `--var`, сохраняя наследование за счёт `extends`.
- **Контейнерные рантаймы (`profiles/base/linux.yml`).** Базовый профиль подключает `profiles/include/containers_runtime.yml`, проверяющий настройки Podman (`events_logger` и `cgroup_manager`), ключ `SystemdCgroup` в `containerd` и отсутствие незадекларированных rootless-сокетов. Список допустимых сокетов задаётся в `profiles/include/allowlist_rootless_sockets.txt`, что позволяет тонко настраивать исключения без правки команд в профиле и соблюдает каскад allow/deny.

## 4. Запуск аудита

Команда `audit` поддерживает несколько ключевых опций:

| Опция | Назначение |
|-------|------------|
| `--module a,b` | Ограничить запуск списком модулей. |
| `--workers N` | Количество параллельных проверок (0 — авто по числу CPU). |
| `--level baseline|strict|paranoid` | Выбор набора переменных и проверок по уровню строгости. |
| `--fail-level none|low|medium|high` | Возвратить код 2, если найдены `FAIL` уровня ≥ порога. |
| `--fail-on-undef` | Возвратить код 2, если есть результаты `UNDEF`. |
| `--evidence DIR` | Сохранить вывод команд в указанную директорию. |
| `--var KEY=VALUE` | Переопределить переменную для одного запуска. |

### 4.1. Типичные сценарии

**Аудит по умолчанию:**

```bash
secaudit audit --profile profiles/base/linux.yml
```

**Аудит только сетевых модулей с уровнем `strict`:**

```bash
secaudit audit \
  --profile profiles/os/debian.yml \
  --module network,services \
  --level strict
```

**Аудит с кастомным порогом блокировок и экспортом улик:**

```bash
secaudit audit \
  --profile profiles/base/server.yml \
  --var FAILLOCK_DENY=4 \
  --fail-level medium \
  --evidence results/evidence
```

### 4.2. Политика завершения

Код выхода CLI:

- `0` — аудит выполнен, критичных проблем не найдено (или порог не достигнут).
- `1` — предупреждения в режиме `validate --strict` или ошибки использования.
- `2` — превышен порог `--fail-level` или обнаружены `UNDEF` при включённом `--fail-on-undef`.
- `3` — критическая ошибка (например, отсутствие обязательной зависимости).

### 4.3. Улики и артефакты

При указании `--evidence DIR` каждая проверка сохраняет stdout/stderr в файл `DIR/<check_id>.txt`. Артефакты отчётов (`results/report*.{json,md,html}`) можно загружать в системы управления уязвимостями или прикреплять к тикетам.

## 5. Отчёты и интерпретация результатов

После завершения аудита создаётся сводка с полями:

- `score` — общий балл, вычисляемый на основе веса проверок.
- `coverage` — процент выполненных проверок (исключая `SKIP`).
- `top_failures` — краткий список наиболее критичных провалов с пояснениями.

HTML-отчёт содержит раскраску по статусам (`PASS`, `FAIL`, `WARN`, `UNDEF`, `SKIP`) и группировку по модулям. Для интеграции с SIEM можно использовать `results/report_grouped.json`.

**Раздел Remediation.** В HTML и Markdown-отчётах появился блок, который агрегирует все непройденные проверки с заполненным полем `remediation`. Он упрощает передачу задач в сервис-деск: операторы сразу видят конкретные шаги, подготовленные авторами профиля. Чтобы заполнить рекомендации, добавьте в YAML-проверку многострочное поле `remediation`.

Помимо визуальных отчётов SecAudit сохраняет машинные экспорты: `results/report.sarif` (формат SARIF 2.1.0 для GitHub Advanced Security, Azure DevOps и других сканеров), `results/report.junit.xml` (JUnit XML для публикации в CI), `results/report.prom` (метрики Prometheus со статусами проверок и сводкой) и `results/report.elastic.ndjson` (NDJSON-события для Elasticsearch/Logstash). Эти файлы подключаются к CI/CD и позволяют анализировать отклонения в единых интерфейсах и дашбордах наблюдения.

### 5.1. Сравнение отчётов

Команда `secaudit compare before.json after.json` читает два JSON-отчёта (`results/report.json` или сгруппированный файл) и выводит:

- кол-во регрессий и улучшений;
- новые проверки и удалённые элементы;
- изменение итогового балла (`score`).

Флаг `--fail-only` ограничивает вывод ухудшениями, где результирующий статус — `FAIL` или `UNDEF`. Результат можно сохранить в файл `--output diff.json` и использовать в пайплайнах регрессионного анализа.

## 6. Тестирование и CI/CD

Запуски `pytest`, `flake8`, `mypy` и `yamllint` описаны в `workflows/ci.yml`. Чтобы повторить локально:

```bash
pytest
yamllint profiles
flake8
mypy
```

В CI можно настроить шаг, который запускает аудит профиля образа:

```yaml
- name: Run SecAudit
  run: |
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    secaudit audit --profile profiles/base/server.yml --fail-level medium
```

Используйте код выхода для принятия решения о прохождении пайплайна.

### GitHub Actions

Файл `docs/examples/github_actions_golden_image.yml` демонстрирует полный workflow: checkout образа, установка зависимостей, запуск `secaudit audit` и публикация артефактов. Ключевые шаги:

1. Установите SecAudit: `pip install -e .`.
2. Выполните аудит golden-образа и сохраните результаты: `secaudit audit --profile profiles/base/server.yml --fail-level medium`.
3. Загрузите отчёты в артефакты (`actions/upload-artifact`) и отправьте `results/report.sarif` через `github/codeql-action/upload-sarif` для отображения в разделе Security.
4. Подключите `results/report.junit.xml` к `actions/upload-test-results`, чтобы сводка проверок появилась в Summary.

### GitLab CI

Пример `.gitlab-ci.yml` находится в `docs/examples/gitlab_ci_golden_image.yml`. Он выполняет аудит в job `secaudit_audit`, публикует каталог `results/` как артефакты и объявляет `results/report.junit.xml` как `junit`-отчёт, который GitLab отобразит на вкладке Tests. SARIF можно выгрузить в артефакты или использовать сторонние интеграции, например загрузку в DefectDojo.

## 7. Частые вопросы

**Как добавить новый профиль?**
1. Создайте файл в подходящем слое (`profiles/os/`, `profiles/roles/` и т.п.).
2. Укажите `schema_version`, `profile_name`, `description` и список `extends`.
3. Добавьте проверки с уникальными `id`; запустите `pytest`, чтобы убедиться в отсутствии коллизий.
4. Пропишите значения в секции `vars` и обновите документацию при необходимости.

**Как быстро проверить конкретную проверку?**
Используйте `secaudit describe-check <ID>` для просмотра команды, затем запустите её вручную на целевой системе.

**Что делать с `UNDEF`?**
`UNDEF` означает, что команда завершилась ошибкой или превысила таймаут. Проверьте наличие зависимостей на целевой системе и повторите аудит. Для строгих пайплайнов добавьте `--fail-on-undef`.

## 8. Интеграция с конфигурационными менеджерами

### 8.1. Ansible

Для автоматизации аудита в инфраструктуре добавьте задачу в плейбук. Пример ниже выполняет SecAudit на целевой машине и собирает отчёты как артефакты:

```yaml
- name: Проверка профиля SecAudit
  hosts: all
  become: true
  vars:
    secaudit_repo: /opt/secaudit-core
    secaudit_bin: /opt/secaudit-core/.venv/bin/secaudit
  tasks:
    - name: Выполнить аудит
      ansible.builtin.command:
        cmd: >-
          {{ secaudit_bin }} audit
          --profile profiles/base/linux.yml
          --level strict
          --fail-level medium
          --evidence results/evidence
      args:
        chdir: "{{ secaudit_repo }}"
      register: secaudit_run
      changed_when: false
      failed_when: secaudit_run.rc not in [0, 2]

    - name: Сохранить HTML-отчёт локально
      ansible.builtin.fetch:
        src: "{{ secaudit_repo }}/results/report_{{ inventory_hostname }}.html"
        dest: "artifacts/"
        flat: false

    - name: Остановить плейбук при обнаружении критичных отклонений
      ansible.builtin.fail:
        msg: "SecAudit нашёл несоответствия уровня medium и выше"
      when: secaudit_run.rc == 2
```

### 8.2. SaltStack

Salt позволяет запускать аудит как часть highstate или оркестрации. Следующее состояние запускает SecAudit и принимает коды возврата `0` и `2` как успешные:

```yaml
secaudit_audit:
  cmd.run:
    - name: >-
        /opt/secaudit-core/.venv/bin/secaudit audit
        --profile profiles/base/server.yml
        --level baseline
        --fail-level low
        --evidence results/evidence
    - cwd: /opt/secaudit-core
    - env:
        SECAUDIT_WORKERS: '4'
    - success_retcodes:
        - 0
        - 2

secaudit_reports:
  file.recurse:
    - name: salt://artifacts/{{ grains['id'] }}/
    - source: salt://{{ salt['config.get']('cachedir') }}/secaudit/results/
    - require:
        - cmd: secaudit_audit
```

Отчёты можно загружать в системы тикетирования или в SIEM. При необходимости используйте новые поля `remediation` для автоматического создания задач по устранению.

---

При возникновении вопросов создавайте issue или обсуждение в репозитории. Вклады и pull-request'ы приветствуются.
