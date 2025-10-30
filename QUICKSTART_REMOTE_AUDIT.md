# Quick Start: Удалённый аудит с SecAudit+

Быстрое руководство по запуску удалённых аудитов безопасности.

## За 3 минуты

```bash
# 1. Сканирование сети (30 сек)
# Укажите ВАШУ сеть вместо примера ниже
secaudit scan --networks 10.0.0.0/24 -o scan.json

# 2. Создание инвентори (5 сек)
secaudit inventory create --from-scan scan.json -o inventory.yml --auto-group

# 3. Настройка SSH ключей (1 мин)
# Отредактируйте inventory.yml и добавьте путь к SSH ключу:
# ssh_key: /path/to/your/key

# 4. Запуск удалённого аудита (1-2 мин)
secaudit audit-remote --inventory inventory.yml --output-dir ./reports
```

## Результаты

После выполнения команд вы получите:

```
./reports/
├── summary.json              # Сводка по всем хостам
└── hosts/
    ├── host1/
    │   └── latest/
    │       ├── report.json   # Детальный JSON отчёт
    │       └── report.html   # HTML отчёт для браузера
    └── host2/
        └── latest/
            └── ...
```

## Основные команды

### Сканирование

```bash
# Простое сканирование одной сети
secaudit scan --networks 10.20.30.0/24 -o scan.json

# С множественными сетями и портами (для разных подразделений/ЦОД)
secaudit scan --networks 172.16.10.0/24,172.16.20.0/24,10.0.100.0/24 --ssh-ports 22,2222 -o scan.json

# С фильтром по ОС (только Ubuntu серверы)
secaudit scan --networks 10.50.0.0/16 --filter-os ubuntu -o ubuntu_hosts.json

# Сканирование DMZ зоны с нестандартными портами
secaudit scan --networks 203.0.113.0/24 --ssh-ports 22000,22001 -o dmz_scan.json
```

### Инвентори

```bash
# Создание
secaudit inventory create --from-scan scan.json -o inventory.yml --auto-group

# Просмотр
secaudit inventory list --inventory inventory.yml

# Добавление хоста
secaudit inventory add-host --inventory inventory.yml --ip 192.168.1.100 --hostname server-01
```

### Удалённый аудит

```bash
# Базовый
secaudit audit-remote --inventory inventory.yml --output-dir ./reports

# С параметрами
secaudit audit-remote \
  --inventory inventory.yml \
  --output-dir ./reports \
  --level strict \
  --workers 20 \
  --evidence

# Фильтрация по группе
secaudit audit-remote --inventory inventory.yml --group production

# Фильтрация по тегам
secaudit audit-remote --inventory inventory.yml --tags "critical,webserver"
```

## Структура инвентори

Минимальный пример `inventory.yml`:

```yaml
version: "1.0"
groups:
  production:
    vars:
      ssh_key: /path/to/key
      ssh_user: root
    hosts:
      - ip: 192.168.1.10
        hostname: web-server-01
      - ip: 192.168.1.20
        hostname: db-server-01
```

Полный пример: [docs/examples/inventory_example.yml](docs/examples/inventory_example.yml)

## Требования

- Python 3.10+
- SSH клиент (`ssh`, `scp`) установлен в системе
- SSH доступ к целевым хостам
- SecAudit+ установлен на целевых хостах (будет скопирован автоматически)

## Подготовка SSH

```bash
# Генерация SSH ключа для аудита
ssh-keygen -t ed25519 -f ~/.ssh/secaudit_key -C "secaudit"

# Копирование на целевой хост
ssh-copy-id -i ~/.ssh/secaudit_key.pub user@host

# Использование в инвентори
# inventory.yml:
#   groups:
#     production:
#       vars:
#         ssh_key: ~/.ssh/secaudit_key
```

## Автоматизация (Cron)

Ежедневный аудит в 2:00:

```bash
0 2 * * * /usr/local/bin/secaudit audit-remote \
  --inventory /etc/secaudit/inventory.yml \
  --output-dir /var/secaudit/reports \
  --level baseline \
  >> /var/log/secaudit/audit.log 2>&1
```

## Полная документация

- [Архитектура](docs/NETWORK_SCANNING_ARCHITECTURE.md)
- [Руководство пользователя](docs/REMOTE_AUDIT_GUIDE.md)
- [Сводка реализации](docs/IMPLEMENTATION_SUMMARY.md)
- [Основной README](README.md)

## Помощь

```bash
secaudit scan --help
secaudit inventory --help
secaudit audit-remote --help
```

## Примеры workflow

### Workflow 1: Новая инфраструктура

```bash
# Обнаружение хостов в корпоративной сети (измените на вашу сеть)
# Пример 1: Сеть офиса
secaudit scan --networks 172.20.0.0/16 -o office_discovery.json

# Пример 2: Несколько подсетей дата-центра
secaudit scan --networks 10.100.0.0/22,10.100.4.0/22,10.100.8.0/22 -o dc_discovery.json

# Создание структурированного инвентори
secaudit inventory create \
  --from-scan dc_discovery.json \
  -o infrastructure.yml \
  --auto-group \
  --ssh-key ~/.ssh/prod_key

# Редактирование для группировки (prod/dev/test)
vim infrastructure.yml

# Первый аудит
secaudit audit-remote \
  --inventory infrastructure.yml \
  --output-dir ./initial_audit \
  --level baseline
```

### Workflow 2: Compliance check

```bash
# Аудит критичных хостов с высоким уровнем строгости
secaudit audit-remote \
  --inventory inventory.yml \
  --tags critical \
  --level paranoid \
  --fail-level high \
  --evidence \
  --output-dir ./compliance_$(date +%Y%m%d)

# Проверка результатов
cat ./compliance_*/summary.json | jq '.successful, .failed'
```

### Workflow 3: Регулярный мониторинг

```bash
#!/bin/bash
# daily_audit.sh

DATE=$(date +%Y%m%d)
REPORT_DIR="/var/secaudit/reports/${DATE}"

# Обновление инвентори (укажите ваши сети)
# Пример: производственная сеть компании
secaudit inventory update \
  --inventory /etc/secaudit/inventory.yml \
  --scan \
  --networks 10.200.0.0/16,10.201.0.0/16

# Аудит
secaudit audit-remote \
  --inventory /etc/secaudit/inventory.yml \
  --output-dir "${REPORT_DIR}" \
  --level strict \
  --workers 20

# Отправка уведомления
if [ $? -ne 0 ]; then
    echo "Найдены проблемы безопасности" | mail -s "SecAudit Alert" admin@company.com
fi
```

## Устранение проблем

### SSH не подключается

```bash
# Проверка доступности
ping <host_ip>

# Проверка SSH
ssh -v user@host_ip

# Проверка ключа
ssh-add -l
ls -l ~/.ssh/
```

### Медленное сканирование

```bash
# Увеличьте workers
secaudit scan --networks ... --workers 100

# Используйте TCP ping (быстрее ICMP)
secaudit scan --networks ... --ping-method tcp
```

### Timeout при аудите

```bash
# Увеличьте timeout
secaudit audit-remote --inventory ... --timeout 600

# Уменьшите workers (если проблемы с нагрузкой)
secaudit audit-remote --inventory ... --workers 5
```

---

**Готово к использованию!** Следуйте примерам выше для быстрого старта.
