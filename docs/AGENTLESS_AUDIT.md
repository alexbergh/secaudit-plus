# Agentless аудит с SecAudit+

## 🎯 Рекомендуемый подход

**Agentless** - это предпочтительный способ проведения security аудита в SecAudit+.

### Почему agentless?

✅ **Не требует установки** на целевые хосты  
✅ **Меньше attack surface** - нет дополнительного ПО  
✅ **Централизованное управление** - всё на сервере  
✅ **Типично для security** - Nessus, OpenVAS работают так  
✅ **Проще в использовании** - указал хосты и запустил  

## Как это работает

```
┌──────────────────────────────────┐
│  Сервер SecAudit                 │
│  ✅ Все модули установлены       │
│                                  │
│  1. Загружает профиль            │
│  2. Выполняет команды через SSH  │
│  3. Собирает результаты          │
│  4. Анализирует локально         │
│  5. Генерирует отчёты            │
└──────────┬───────────────────────┘
           │ SSH: только команды
           │ cat /etc/passwd
           │ systemctl status sshd
           ▼
┌──────────────────────────────────┐
│  Целевой хост                    │
│  ❌ НЕ требует secaudit          │
│  ✅ Только SSH доступ            │
│                                  │
│  - Выполняет команды             │
│  - Возвращает результат          │
└──────────────────────────────────┘
```

## Быстрый старт

### 1. Создайте инвентори

```yaml
# inventory.yml
version: "1.0"
groups:
  production:
    vars:
      ssh_user: secsecaudituser
      ssh_key: ~/.ssh/audit_key
    hosts:
      - hostname: web-server-01
        ip: 10.0.1.10
      - hostname: db-server-01
        ip: 10.0.1.20
```

### 2. Запустите agentless аудит

```bash
secaudit audit-agentless \
  --inventory inventory.yml \
  --profile profiles/base/server.yml \
  --level baseline \
  --output-dir ./reports
```

### 3. Просмотрите результаты

```
./reports/
├── summary.json              # Сводка по всем хостам
└── hosts/
    ├── web-server-01/
    │   └── latest/
    │       └── report.json   # Детальный отчёт
    └── db-server-01/
        └── latest/
            └── report.json
```

## Параметры команды

```bash
secaudit audit-agentless \
  --inventory <path>          # Путь к инвентори (обязательно)
  --profile <path>            # Путь к профилю (обязательно)
  --output-dir <path>         # Директория для отчётов
  --level baseline|strict|paranoid  # Уровень строгости
  --workers 10                # Количество параллельных workers
  --timeout 30                # Таймаут на одну команду (сек)
  --ssh-timeout 10            # Таймаут SSH подключения (сек)
  --group <name>              # Фильтр по группе
  --tags <tag1,tag2>          # Фильтр по тегам
  --os <os_name>              # Фильтр по ОС
```

## Примеры использования

### Базовый аудит

```bash
secaudit audit-agentless \
  --inventory prod_inventory.yml \
  --profile profiles/common/baseline.yml \
  --output-dir ./reports
```

### Строгий аудит production серверов

```bash
secaudit audit-agentless \
  --inventory prod_inventory.yml \
  --profile profiles/base/server.yml \
  --group production \
  --level paranoid \
  --output-dir ./critical_audit
```

### Аудит с фильтрацией

```bash
# Только критичные веб-серверы
secaudit audit-agentless \
  --inventory inventory.yml \
  --profile profiles/roles/webserver.yml \
  --tags "critical,webserver" \
  --level strict
```

```bash
# Только Ubuntu серверы
secaudit audit-agentless \
  --inventory inventory.yml \
  --profile profiles/base/linux.yml \
  --os ubuntu \
  --level baseline
```

### Быстрая проверка с большим параллелизмом

```bash
secaudit audit-agentless \
  --inventory inventory.yml \
  --profile profiles/common/baseline.yml \
  --workers 50 \
  --timeout 15 \
  --output-dir ./quick_check
```

## Настройка SSH доступа

### Рекомендуется: SSH ключи

```bash
# 1. Генерация ключа
ssh-keygen -t ed25519 -f ~/.ssh/secaudit_key -C "secaudit"

# 2. Копирование на целевые хосты
ssh-copy-id -i ~/.ssh/secaudit_key.pub secaudituser@host

# 3. В инвентори
groups:
  production:
    vars:
      ssh_user: secaudituser
      ssh_key: ~/.ssh/secaudit_key
```

### Опционально: пароли (не рекомендуется)

Требует `sshpass` (доступен на Linux):

```yaml
groups:
  test:
    vars:
      ssh_user: root
      ssh_password: "your_password"  # Не безопасно!
```

### Создание audit пользователя

```bash
# На целевом хосте
useradd -m -s /bin/bash secsecaudituser

# Минимальные sudo права для аудита
# /etc/sudoers.d/secsecaudituser
secsecaudituser ALL=(ALL) NOPASSWD: /usr/bin/systemctl status *
secsecaudituser ALL=(ALL) NOPASSWD: /usr/bin/cat /etc/*
secsecaudituser ALL=(ALL) NOPASSWD: /usr/sbin/iptables -L
secsecaudituser ALL=(ALL) NOPASSWD: /usr/bin/find /etc -type f -perm /022
```

## Формат отчётов

### Сводный отчёт (summary.json)

```json
{
  "audit_time": "2025-10-30 20:00:00",
  "total_hosts": 10,
  "successful": 9,
  "failed": 1,
  "average_score": 78.5,
  "hosts": [
    {
      "host": "web-server-01",
      "ip": "10.0.1.10",
      "success": true,
      "summary": {
        "total": 45,
        "pass": 38,
        "fail": 5,
        "undef": 2,
        "score": 84.4
      }
    }
  ]
}
```

### Отчёт по хосту (hosts/hostname/latest/report.json)

```json
{
  "host": "web-server-01",
  "ip": "10.0.1.10",
  "group": "production",
  "audit_time": "2025-10-30 20:00:15",
  "duration": 12.5,
  "summary": {
    "total": 45,
    "pass": 38,
    "fail": 5,
    "undef": 2,
    "score": 84.4
  },
  "results": [
    {
      "id": "check_ssh_root_login",
      "name": "Запрещен ли root-вход по SSH",
      "module": "system",
      "severity": "high",
      "command": "sshd -T 2>/dev/null | awk '/^permitrootlogin / {print $2}'",
      "rc": 0,
      "output": "no\n",
      "stderr": "",
      "result": "PASS",
      "reason": "exact match 'no'",
      "duration": 0.234
    }
  ]
}
```

## Производительность

### Оптимизация для больших инфраструктур

```bash
# 100+ хостов
secaudit audit-agentless \
  --inventory large_inventory.yml \
  --profile profiles/common/baseline.yml \
  --workers 50 \              # Больше параллелизма
  --timeout 20 \              # Меньше timeout
  --ssh-timeout 5             # Быстрее обнаружение недоступных
```

### Типичная производительность

| Хостов | Workers | Время |
|--------|---------|-------|
| 10 | 10 | ~2 мин |
| 50 | 25 | ~5 мин |
| 100 | 50 | ~8 мин |
| 500 | 50 | ~40 мин |

## Сравнение: Agentless vs Remote

| Критерий | Agentless ✅ | Remote (agent-based) |
|----------|-------------|----------------------|
| Установка на хосты | ❌ Не требуется | ✅ Требуется |
| Attack surface | Минимальный | Увеличенный |
| Скорость | Средняя | Быстрая |
| Нагрузка на сеть | Низкая | Средняя |
| Сложность | Простая | Средняя |
| Обновление | Централизованное | На каждом хосте |
| **Рекомендуется** | **ДА** | Для специальных случаев |

## Устранение неполадок

### SSH подключение не работает

```bash
# Проверка вручную
ssh -p 22 secsecaudituser@host echo "test"

# Проверка ключа
ssh-add -l

# Проверка прав
chmod 600 ~/.ssh/secaudit_key
```

### Команды не выполняются

```bash
# Проверка sudo прав
ssh secsecaudituser@host "sudo systemctl status sshd"

# Проверка оболочки
ssh secsecaudituser@host "echo \$SHELL"
```

### Медленное выполнение

```bash
# Уменьшите timeout
--timeout 15

# Увеличьте workers
--workers 30

# Упростите профиль (меньше проверок)
--level baseline
```

## Регулярный аудит (Cron)

```bash
#!/bin/bash
# /etc/cron.daily/secaudit-agentless

DATE=$(date +%Y%m%d)
REPORT_DIR="/var/secaudit/agentless/${DATE}"

secaudit audit-agentless \
  --inventory /etc/secaudit/prod_inventory.yml \
  --profile /etc/secaudit/profiles/server.yml \
  --level strict \
  --output-dir "${REPORT_DIR}" \
  --workers 20

# Отправка уведомления при ошибках
if [ $? -ne 0 ]; then
    mail -s "SecAudit Alert: Failures detected" admin@company.com < "${REPORT_DIR}/summary.json"
fi
```

## Интеграция с CI/CD

```yaml
# .gitlab-ci.yml
security_audit:
  stage: security
  script:
    - pip install -r requirements.txt
    - |
      secaudit audit-agentless \
        --inventory environments/production.yml \
        --profile profiles/ci/baseline.yml \
        --output-dir ./audit_reports \
        --level strict
  artifacts:
    paths:
      - audit_reports/
    expire_in: 30 days
  only:
    - schedules
```

## Best Practices

### 1. Используйте выделенного пользователя
```bash
# Создайте secsecaudituser с минимальными правами
useradd -m -s /bin/bash secsecaudituser
```

### 2. Используйте SSH ключи
```bash
# Никогда не используйте пароли в production
ssh_key: ~/.ssh/secaudit_key
```

### 3. Разделяйте окружения
```yaml
# dev_inventory.yml
# staging_inventory.yml  
# prod_inventory.yml
```

### 4. Версионируйте профили
```bash
git commit -m "Update security baseline"
```

### 5. Автоматизируйте
```bash
# Ежедневный cron
0 2 * * * /usr/local/bin/secaudit-daily.sh
```

## Заключение

**Agentless аудит** - рекомендуемый подход для SecAudit+:

✅ Простой в использовании  
✅ Безопасный (минимальный attack surface)  
✅ Эффективный (централизованное управление)  
✅ Типичный для security аудита  

**Начните прямо сейчас**:
```bash
secaudit audit-agentless --inventory inventory.yml --profile profiles/common/baseline.yml
```
