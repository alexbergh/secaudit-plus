> SecAudit-core

**SecAudit-core** —  CLI-инструмент для аудита безопасности Linux-систем по профилям ФСТЭК, СТЭК, NIST и ISO.
Ориентирован на автоматизацию, масштабируемость и гибкость (через YAML).

- Поддержка YAML-профилей
- Аудит SSH, PAM, SUDO, root-настроек
- JSON-отчёт с PASS/FAIL
- Расширяемая архитектура

## Профили и уровни строгости

Каталог `profiles/` реорганизован по ролям и семействам ОС. Базовые проверки, отраслевые роли и требования конкретных дистрибутивов подключаются слоями через `extends`, а параметры подставляются переменными `{{ VAR }}`. Готовые профили:

| Путь профиля | Назначение |
|--------------|------------|
| `profiles/base/linux.yml` | Базовый baseline для любых GNU/Linux (PAM, аудит, firewall) |
| `profiles/base/workstation.yml` | Рабочие станции и ноутбуки |
| `profiles/base/server.yml` | Серверы общего назначения |
| `profiles/os/astra-1.7.yml` | Astra Linux 1.7 (КСЗ, режим Киоск-2) |
| `profiles/os/alt-8sp.yml` | ALT 8 СП с ГОСТ-криптографией |
| `profiles/os/redos-7.3-8.yml` | РЕД ОС 7.3/8: лимиты, монтирование, сетевой экран |
| `profiles/roles/kiosk.yml` | Терминалы/киоски с закреплённым приложением |
| `profiles/roles/db.yml` | Серверы СУБД |
| `profiles/szi/snlsp.yml` | Средства защиты информации (пример: Secret Net LSP) |

Дополнительные переменные, allowlist/denylist и пороги строгости лежат в `profiles/include/`. Для переключения порогов используйте флаг `--level baseline|strict|paranoid` (или переменную окружения `SECAUDIT_LEVEL`). Один и тот же YAML может покрывать несколько версий ОС — проверяйте `os_id`, `os_like` и `os_version_id` через условие `when:`.

Каждая проверка содержит `ref` с обоснованием, `remediation` с пошаговым исправлением, а также может сохранять фрагмент вывода в «улики». Итоговый отчёт выводит веса, баллы и топ-несоответствия.

### Быстрый запуск профилей

```bash
# Валидация синтаксиса
python3 main.py validate --profile profiles/base/linux.yml
python3 main.py validate --profile profiles/os/astra-1.7.yml
python3 main.py validate --profile profiles/os/alt-8sp.yml
python3 main.py validate --profile profiles/os/redos-7.3-8.yml
python3 main.py validate --profile profiles/szi/snlsp.yml

# Пример аудита: строгий уровень, 4 воркера, кастомный порог блокировок
python3 main.py audit \
  --profile profiles/base/server.yml \
  --level strict \
  --workers 4 \
  --var FAILLOCK_DENY=3 \
  --fail-level medium
```

```bash
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
# Запуск аудита с уликами и проверкой UNDEF
python3 main.py audit --profile profiles/base/linux.yml --evidence results/evidence --fail-on-undef

```

---

##  Тест

Для проверки логики assert'ов (`exact`, `contains`, `regexp`, `not_contains`) реализованы модульные юнит-тесты на `pytest`.

### Установка

```bash
pip install -r requirements.txt

```

## Установка из исходников

```bash
python3 -m venv venv
source venv/bin/activate
pip install .

```

## Документация
- [Руководство пользователя](USAGE.md)

