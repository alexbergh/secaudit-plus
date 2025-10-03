# Руководство пользователя — SecAudit-core

SecAudit-core — CLI-инструмент для аудита безопасности Linux-систем по YAML-профилям (ФСТЭК № 17/21, CIS, STIG и др.). Позволяет быстро запустить аудит ОС и получить подробный отчёт в формате JSON, Markdown или HTML.

## Установка

### 1. Клонирование и установка из исходников
```bash
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core
python3 -m venv venv
source venv/bin/activate       # Windows: .\venv\Scripts\activate
pip install -e .
```

### 2. Проверка установки
```bash
secaudit --help
```

## Структура проекта
```
secaudit-core/
├─ secaudit/                # точка входа (main.py)
├─ modules/                 # cli, audit_runner, bash_executor, ...
├─ profiles/                # YAML-профили: alt.yml, astra.yml, centos.yml, ...
├─ results/                 # отчёты (создаётся при запуске)
├─ report_template.md.j2    # шаблон Markdown
├─ report_template.html.j2  # шаблон HTML
├─ README.md
├─ LICENSE
└─ USAGE.md                 # это руководство
```

##  Использование CLI

### Общий синтаксис
```bash
secaudit [GLOBAL OPTIONS] <command> [OPTIONS]
```

## Специализированные профили и классы ФСТЭК

SecAudit-core поставляется с готовыми профилями для разных семейств ОС и классов защищённости:

| Профиль | Файл | Основные проверки | Рекомендованный класс |
|---------|------|-------------------|-----------------------|
| Базовый Linux | `profiles/base-linux.yml` | PAM, аудит, фаервол | К4–К3 |
| Astra Linux 1.7 КСЗ/Киоск-2 | `profiles/astra-1.7-ksz.yml` | PAM, КСЗ, Киоск-2 | К1–К2 |
| ALT 8 СП | `profiles/alt-8sp.yml` | iptables, ГОСТ, dm-secdel | К2 |
| РЕД ОС 7.3/8 | `profiles/redos-7.3-8.yml` | лимиты, монтирование, firewall | К3 |
| SN LSP | `profiles/snlsp.yml` | службы, политики, носители | К1 |

Каждый профиль снабжён блоком `meta` с прямыми ссылками на нормативные документы и `tags` с конкретными пунктами требований. Проверки объединены в модули (`system`, `network`, `services`, `integrity`, `media`, `snlsp` и др.) и используют расширенные типы проверок (`regexp`, `jsonpath`, `exit_code`).

### Быстрая проверка профилей

```bash
# Проверка синтаксиса
python3 main.py validate --profile profiles/base-linux.yml
python3 main.py validate --profile profiles/astra-1.7-ksz.yml
python3 main.py validate --profile profiles/alt-8sp.yml
python3 main.py validate --profile profiles/redos-7.3-8.yml
python3 main.py validate --profile profiles/snlsp.yml

# Запуск аудита (пример)
python3 main.py audit --profile profiles/snlsp.yml --fail-level high
```

##  CLI команды SecAudit++

###  Глобальные опции

| Флаг              | Описание                                                                     | По умолчанию                         |
|-------------------|------------------------------------------------------------------------------|--------------------------------------|
| `--profile PATH`  | Путь к YAML-профилю                                                          | `profiles/common/baseline.yml`       |
| `--fail-level LEVEL` | Пороговый уровень FAIL (`low`, `medium`, `high`) для выхода с ненулевым кодом при `audit` | `high`                               |
| `-h`, `--help`    | Вывод справки                                                               | —                                    |

###  Список доступных команд

| Команда                | Назначение                                                             | Пример                                                                 |
|------------------------|------------------------------------------------------------------------|------------------------------------------------------------------------|
| `list-modules`         | Выводит список всех модулей в выбранном профиле                       | `secaudit --profile profiles/alt.yml list-modules`                    |
| `list-checks`          | Выводит список всех проверок, опционально с фильтром по модулю        | `secaudit --profile profiles/alt.yml list-checks --module system`     |
| `describe-check <ID>`  | Отображает подробности конкретной проверки по её `id`                 | `secaudit --profile profiles/alt.yml describe-check check_ssh_root_login` |
| `validate`             | Проверяет YAML-профиль на соответствие встроенной JSON-схеме          | `secaudit --profile profiles/alt.yml validate`                        |
| `audit`                | Запускает аудит выбранного профиля и формирует отчёты                 | `secaudit --profile profiles/alt.yml audit --fail-level medium`       |

###  Примеры

```bash
# Список всех модулей
secaudit --profile profiles/alt.yml list-modules

# Список всех проверок в модуле system
secaudit --profile profiles/alt.yml list-checks --module system

# Детали конкретной проверки
secaudit --profile profiles/alt.yml describe-check check_ssh_root_login

# Проверка корректности профиля
secaudit --profile profiles/alt.yml validate

# Запуск аудита с порогом FAIL на medium
secaudit --profile profiles/alt.yml audit --fail-level medium
```
=======
### Глобальные опции
- `--profile PATH` — путь к YAML-профилю (по умолчанию `profiles/common/baseline.yml`).
- `--fail-level {low|medium|high}` — уровень, начиная с которого аудит считается неуспешным (для команды `audit`).

### Основные команды
1. **Список модулей в профиле**
   ```bash
   secaudit --profile profiles/alt.yml list-modules
   ```
2. **Список проверок**
   ```bash
   secaudit --profile profiles/alt.yml list-checks
   secaudit --profile profiles/alt.yml list-checks --module system
   ```
3. **Описание конкретной проверки**
   ```bash
   secaudit --profile profiles/alt.yml describe-check check_ssh_root_login
   ```
4. **Валидация профиля**
   ```bash
   secaudit --profile profiles/alt.yml validate
   ```
5. **Запуск аудита**
   ```bash
   secaudit --profile profiles/alt.yml audit --fail-level medium
   ```

### Результаты выполнения
После завершения аудита отчёты сохраняются в каталоге `results/`:
- `results/report.json` — полный список проверок.
- `results/report_grouped.json` — сгруппированные результаты.
- `results/report.md` — Markdown-отчёт.
- `results/report_<hostname>_<datetime>.html` — HTML-отчёт с аккордеонами по модулям (имя хоста и дата в названии).

##  Пример YAML-профиля
```yaml
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
```

> **Важно:** теги `fstec` должны быть строкой, а не YAML-списком.
> ```yaml
> fstec: "ИАФ.1, УПД.5"      # ✅ правильно
> fstec: ['ИАФ.1', 'УПД.5']  # ❌ вызовет ошибку валидации
> ```

##  Требования к запуску
- Часть проверок требует root-прав или наличия `sudo`.
- Запускайте аудит в активном виртуальном окружении Python или после глобальной установки `pip install -e .`.
- Для корректной работы HTML-отчёта необходим доступ к CDN Bootstrap (или локальная копия CSS/JS).
