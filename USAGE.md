Руководство пользователя SecAudit++
📦 Установка
1. Клонирование репозитория
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core

2. Установка в editable-режиме

Рекомендуется работать в виртуальном окружении Python.

python3 -m venv venv
source venv/bin/activate          # Linux / macOS
# .\venv\Scripts\activate          # Windows

pip install -e .


Проверить, что утилита установлена:

secaudit --help

🗂️ Структура проекта
secaudit-core/
│
├── secaudit/                # Основной код утилиты
│   └── main.py
├── modules/                 # Модули: audit_runner, cli, bash_executor и др.
├── profiles/                # YAML-профили для различных ОС
│   ├── alt.yml
│   ├── astra.yml
│   ├── centos.yml
│   ├── debian.yml
│   └── common/baseline.yml
├── results/                 # Сюда сохраняются отчёты (создаётся при запуске)
├── report_template.md.j2    # Jinja2-шаблон отчёта (Markdown)
├── report_template.html.j2  # Jinja2-шаблон отчёта (HTML)
├── README.md
├── LICENSE
└── USAGE.md                 # Этот файл с инструкцией

🚀 Основные команды CLI
secaudit [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]

Глобальные опции

--profile PATH — путь к YAML-профилю (по умолчанию: profiles/common/baseline.yml)

--fail-level {low|medium|high} — уровень, начиная с которого аудит считается неуспешным (для audit)

🔹 1. Просмотр доступных модулей
secaudit --profile profiles/alt.yml list-modules

🔹 2. Просмотр всех проверок
secaudit --profile profiles/alt.yml list-checks


С фильтром по модулю:

secaudit --profile profiles/alt.yml list-checks --module system

🔹 3. Детальное описание конкретной проверки
secaudit --profile profiles/alt.yml describe-check check_ssh_root_login

🔹 4. Валидация профиля
secaudit --profile profiles/alt.yml validate

🔹 5. Запуск аудита
secaudit --profile profiles/alt.yml audit --fail-level medium


Результаты сохраняются в:

results/report.json – полный список проверок

results/report_grouped.json – сгруппированные результаты по модулям

results/report.md – отчёт в Markdown

results/report.html – отчёт в HTML с аккордеонами

📄 Формат YAML-профиля (пример)
profile_name: "ALT Linux 8 SP"
description: "Базовые меры защиты для Alt Linux по ФСТЭК №21"
checks:
  - id: check_ssh_root_login
    name: "SSH: RootLogin запрещён"
    module: "system"
    severity: "high"
    command: "sshd -T | grep -i '^permitrootlogin' | awk '{print $2}'"
    expect: "no"
    assert_type: "exact"
    tags:
      fstec: "ИАФ.1, УПД.5"
      cis: "5.2.8"
      stig: "SSH-RootLogin"

⚠️ Примечания

Для корректной работы bash-проверок требуется запускать аудит из-под пользователя с нужными правами (часть команд требует root).

Если теги fstec указаны списком (['ИАФ.1', 'УПД.5']), замените их на строку с запятыми ("ИАФ.1, УПД.5"), чтобы пройти валидацию схемы YAML.

В Linux убедитесь, что скрипт установлен в активном venv или в $PATH.

📝 Лицензия

Проект распространяется под лицензией GPL-3.0
.
