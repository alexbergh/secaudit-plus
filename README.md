> SecAudit-core

**SecAudit-core** —  CLI-инструмент для аудита безопасности Linux-систем по профилям ФСТЭК, СТЭК, NIST и ISO.
Ориентирован на автоматизацию, масштабируемость и гибкость (через YAML).

- Поддержка YAML-профилей
- Аудит SSH, PAM, SUDO, root-настроек
- JSON-отчёт с PASS/FAIL
- Расширяемая архитектура

## Специализированные профили 2024

В репозитории появились дополнительные профили с аннотациями на разделы ФСТЭК/КСЗ и отраслевых руководств:

| Файл профиля | Назначение | Рекомендованный класс ФСТЭК |
|--------------|------------|-----------------------------|
| `profiles/base-linux.yml` | Базовый baseline для типовых GNU/Linux (PAM, аудит, фаервол) | К4–К3 |
| `profiles/astra-1.7-ksz.yml` | Astra Linux 1.7 c модулями КСЗ и режимом Киоск-2 | К1–К2 |
| `profiles/alt-8sp.yml` | ALT 8 СП с контролем iptables, ГОСТ-криптографии и dm-secdel | К2 |
| `profiles/redos-7.3-8.yml` | РЕД ОС 7.3/8: лимиты, монтирование, сетевой экран | К3 |
| `profiles/snlsp.yml` | Комплекс SN LSP: службы безопасности, политики, носители | К1 |

Каждый профиль содержит блок `meta` со ссылками на нормативные документы (приказ 239, руководства вендоров, методички по КСЗ) и `tags` с конкретными пунктами требований. Проверки сгруппированы по модулям (`system`, `network`, `integrity`, `media`, `snlsp` и др.) и используют расширенные типы проверок (`regexp`, `jsonpath`, `exit_code`).

### Быстрый запуск профилей

```bash
# Валидация синтаксиса
python3 main.py validate --profile profiles/base-linux.yml
python3 main.py validate --profile profiles/astra-1.7-ksz.yml
python3 main.py validate --profile profiles/alt-8sp.yml
python3 main.py validate --profile profiles/redos-7.3-8.yml
python3 main.py validate --profile profiles/snlsp.yml

# Пример аудита с порогом medium
python3 main.py audit --profile profiles/alt-8sp.yml --fail-level medium
```

```bash
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
# Запуск аудита с ошибкой при UNDEF
python3 main.py audit --fail-on-undef

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
- [Статус доработок](secondary_tail_coverage.md)
- [План расширения](docs/profile_engine_enhancements.md)

