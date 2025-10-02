# Руководство пользователя — SecAudit-core

SecAudit-core — CLI-инструмент для аудита безопасности Linux-систем по YAML-профилям (ФСТЭК № 17/21, CIS, STIG и др.). Позволяет быстро запустить аудит ОС и получить подробный отчёт в формате JSON, Markdown или HTML.

## ⚙️ Установка

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

## 📂 Структура проекта
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

## 🚀 Использование CLI

### Общий синтаксис
```bash
secaudit [GLOBAL OPTIONS] <command> [OPTIONS]
```

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
- `results/report.html` — HTML-отчёт с аккордеонами по модулям.

## 📝 Пример YAML-профиля
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

## 🔒 Требования к запуску
- Часть проверок требует root-прав или наличия `sudo`.
- Запускайте аудит в активном виртуальном окружении Python или после глобальной установки `pip install -e .`.
- Для корректной работы HTML-отчёта необходим доступ к CDN Bootstrap (или локальная копия CSS/JS).

## 📄 Лицензия

Проект распространяется по лицензии GPL-3.0.
