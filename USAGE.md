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
├─ secaudit/                # основной лаунчер и CLI-утилиты
├─ modules/                 # audit_runner, cli, bash_executor, report_generator, ...
├─ profiles/
│  ├─ base/                # базовые роли: linux.yml, workstation.yml, server.yml
│  ├─ os/                  # специфичные требования дистрибутивов
│  ├─ roles/               # прикладные роли (kiosk, db и др.)
│  ├─ szi/                 # профили средств защиты информации
│  └─ include/             # allowlist/denylist и vars_baseline/strict/paranoid.env
├─ reports/                # шаблоны HTML/Markdown отчётов
├─ results/                # артефакты аудита (создаются при запуске)
├─ README.md
├─ USAGE.md
└─ pyproject.toml
```

##  Использование CLI

### Общий синтаксис
```bash
secaudit [GLOBAL OPTIONS] <command> [OPTIONS]
```

## Специализированные профили и классы ФСТЭК

SecAudit-core поставляется с готовыми профилями для разных семейств ОС и классов защищённости:

| Профиль | Файл | Основные проверки |
|---------|------|-------------------|
| Базовый Linux | `profiles/base/linux.yml` | PAM, аудит, firewall |
| Рабочая станция | `profiles/base/workstation.yml` | Блокировки устройств, обновления |
| Сервер | `profiles/base/server.yml` | Службы, журналирование, резервирование |
| Astra Linux 1.7 | `profiles/os/astra-1.7.yml` | КСЗ, режим Киоск, жесткие монтирования |
| ALT 8 СП | `profiles/os/alt-8sp.yml` | ГОСТ-криптография, iptables |
| РЕД ОС 7.3/8 | `profiles/os/redos-7.3-8.yml` | Лимиты, sysctl, firewall |
| Киоск | `profiles/roles/kiosk.yml` | Заблокированный интерфейс, автологин |
| Сервер БД | `profiles/roles/db.yml` | Параметры PostgreSQL/MySQL, резервные копии |
| SN LSP | `profiles/szi/snlsp.yml` | Политики СЗИ, контроль устройств |

Каждый профиль снабжён блоком `meta` с прямыми ссылками на нормативные документы и `tags` с конкретными пунктами требований. Проверки объединены в модули (`system`, `network`, `services`, `integrity`, `media`, `snlsp` и др.) и используют расширенные типы проверок (`regexp`, `jsonpath`, `exit_code`).

### Быстрая проверка профилей

```bash
# Проверка синтаксиса
python3 main.py validate --profile profiles/base/linux.yml
python3 main.py validate --profile profiles/os/astra-1.7.yml
python3 main.py validate --profile profiles/os/alt-8sp.yml
python3 main.py validate --profile profiles/os/redos-7.3-8.yml
python3 main.py validate --profile profiles/szi/snlsp.yml

# Запуск аудита (пример)
python3 main.py audit --profile profiles/szi/snlsp.yml --fail-level high
```

##  CLI команды SecAudit++

###  Глобальные опции

| Флаг | Описание | По умолчанию |
|------|----------|--------------|
| `--profile PATH` | Путь к YAML-профилю. Можно также передать путь позиционным аргументом. | `profiles/common/baseline.yml` |
| `--level {baseline,strict,paranoid}` | Уровень строгости: влияет на переменные (`SECAUDIT_LEVEL` переопределяет). | `baseline` |
| `--var KEY=VALUE` | Переопределение переменных профиля (можно указывать несколько раз). | — |
| `--workers N` | Количество потоков. `0` — авто (берётся из `SECAUDIT_WORKERS`). | `0` |
| `--fail-level LEVEL` | Пороговый уровень FAIL (`low`, `medium`, `high`) для возврата кода 2. | `none` |
| `--fail-on-undef` | Возвращать код 2, если есть результаты `UNDEF`. | `false` |
| `--evidence DIR` | Сохранять вывод команд (улики) в каталог. | — |
| `-h`, `--help` | Вывод справки. | — |


###  Список доступных команд

| Команда                | Назначение                                                             | Пример                                                                 |
|------------------------|------------------------------------------------------------------------|------------------------------------------------------------------------|
| `list-modules`         | Выводит список всех модулей в выбранном профиле                       | `secaudit --profile profiles/os/alt-8sp.yml list-modules`                    |
| `list-checks`          | Выводит список всех проверок, опционально с фильтром по модулю        | `secaudit --profile profiles/os/alt-8sp.yml list-checks --module system`     |
| `describe-check <ID>`  | Отображает подробности конкретной проверки по её `id`                 | `secaudit --profile profiles/os/alt-8sp.yml describe-check check_ssh_root_login` |
| `validate`             | Проверяет YAML-профиль на соответствие встроенной JSON-схеме          | `secaudit --profile profiles/os/alt-8sp.yml validate`                        |
| `audit`                | Запускает аудит выбранного профиля и формирует отчёты                 | `secaudit --profile profiles/os/alt-8sp.yml audit --fail-level medium`       |

###  Примеры

```bash
# Список всех модулей
secaudit --profile profiles/os/alt-8sp.yml list-modules

# Список всех проверок в модуле system
secaudit --profile profiles/os/alt-8sp.yml list-checks --module system

# Детали конкретной проверки
secaudit --profile profiles/os/alt-8sp.yml describe-check check_ssh_root_login

# Проверка корректности профиля
secaudit --profile profiles/os/alt-8sp.yml validate

# Запуск аудита с порогом FAIL на medium
secaudit --profile profiles/os/alt-8sp.yml audit --fail-level medium
```
=======
### Глобальные опции
- `--profile PATH` — путь к YAML-профилю (по умолчанию `profiles/common/baseline.yml`).
- `--level {baseline|strict|paranoid}` — переключение уровня строгости (можно задать через `SECAUDIT_LEVEL`).
- `--var KEY=VALUE` — переопределение переменных профиля (повторяется несколько раз).
- `--workers N` — количество параллельных потоков (`SECAUDIT_WORKERS` или авто при `0`).
- `--fail-level {low|medium|high}` — уровень, начиная с которого аудит считается неуспешным (код возврата 2).
- `--fail-on-undef` — завершать аудит с кодом 2, если есть результаты `UNDEF`.
- `--evidence DIR` — сохранять вывод команд в отдельный каталог.
### Основные команды
1. **Список модулей в профиле**
   ```bash
   secaudit --profile profiles/os/alt-8sp.yml list-modules
   ```
2. **Список проверок**
   ```bash
   secaudit --profile profiles/os/alt-8sp.yml list-checks
   secaudit --profile profiles/os/alt-8sp.yml list-checks --module system
   ```
3. **Описание конкретной проверки**
   ```bash
   secaudit --profile profiles/os/alt-8sp.yml describe-check check_ssh_root_login
   ```
4. **Валидация профиля**
   ```bash
   secaudit --profile profiles/os/alt-8sp.yml validate
   ```
5. **Запуск аудита**
   ```bash
   secaudit --profile profiles/os/alt-8sp.yml audit --fail-level medium
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
