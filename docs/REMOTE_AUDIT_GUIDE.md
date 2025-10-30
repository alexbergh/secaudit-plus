# Руководство по удалённому аудиту

Это руководство описывает использование функций сканирования сети и удалённого аудита в SecAudit+.

## Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Сканирование сети](#сканирование-сети)
3. [Управление инвентори](#управление-инвентори)
4. [Удалённый аудит](#удалённый-аудит)
5. [Примеры использования](#примеры-использования)
6. [Устранение неполадок](#устранение-неполадок)

## Быстрый старт

Полный цикл от сканирования до получения отчётов:

```bash
# 1. Сканирование сети
secaudit scan --networks 192.168.1.0/24 -o scan.json

# 2. Создание инвентори
secaudit inventory create --from-scan scan.json -o inventory.yml --auto-group

# 3. Настройка инвентори (опционально)
# Отредактируйте inventory.yml для добавления SSH ключей, профилей и т.д.

# 4. Запуск удалённого аудита
secaudit audit-remote --inventory inventory.yml --output-dir ./reports --workers 10

# 5. Просмотр результатов
ls -la ./reports/hosts/
```

## Сканирование сети

### Базовое сканирование

Сканирование одной подсети (замените на вашу сеть):

```bash
# Пример 1: Подсеть офиса
secaudit scan --networks 172.16.10.0/24 -o office_scan.json

# Пример 2: Подсеть серверов
secaudit scan --networks 10.50.100.0/24 -o servers_scan.json
```

### Расширенное сканирование

Сканирование множественных сетей с дополнительными параметрами:

```bash
# Пример: Сканирование разных зон инфраструктуры
secaudit scan \
  --networks 10.10.0.0/22,10.20.0.0/22,172.30.0.0/24 \
  --ssh-ports 22,2222,22000 \
  --timeout 5 \
  --workers 100 \
  --ping-method both \
  -o multi_zone_scan.json

# Пример: Сканирование DMZ с нестандартными портами
secaudit scan \
  --networks 203.0.113.0/25 \
  --ssh-ports 22000,22001,22002 \
  --timeout 10 \
  -o dmz_scan.json
```

### Фильтрация результатов

Сканирование с фильтрацией по ОС:

```bash
# Только Ubuntu и Debian серверы
secaudit scan \
  --networks 10.100.0.0/16 \
  --filter-os ubuntu,debian \
  -o linux_debian_based.json

# Только CentOS/RHEL серверы
secaudit scan \
  --networks 10.200.0.0/16 \
  --filter-os centos,rhel,rocky \
  -o redhat_based.json
```

### Параметры команды scan

- `--networks` - Список сетей в формате CIDR через запятую (обязательно)
- `--ssh-ports` - Список SSH портов для проверки (по умолчанию: 22)
- `--timeout` - Таймаут для каждого хоста в секундах (по умолчанию: 2)
- `--workers` - Количество параллельных потоков (по умолчанию: 50)
- `--ping-method` - Метод проверки доступности: tcp, icmp, both (по умолчанию: tcp)
- `--no-resolve` - Не резолвить hostname'ы
- `--no-detect-os` - Не определять ОС
- `--filter-os` - Фильтр по ОС
- `-o, --output` - Путь к выходному файлу (обязательно)

### Формат результатов сканирования

Результат сохраняется в JSON:

```json
{
  "scan_time": "2025-10-30 19:20:00",
  "total_hosts": 254,
  "alive_hosts": 12,
  "hosts": [
    {
      "ip": "192.168.1.10",
      "hostname": "web-server-01",
      "is_alive": true,
      "ssh_port": 22,
      "ssh_banner": "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5",
      "os_detected": "ubuntu",
      "scan_duration": 0.234
    }
  ]
}
```

## Управление инвентори

### Создание инвентори

Создание из результатов сканирования:

```bash
secaudit inventory create \
  --from-scan scan_results.json \
  -o inventory.yml \
  --auto-group \
  --ssh-user audituser \
  --ssh-key /etc/secaudit/keys/default_key \
  --profile profiles/base/server.yml
```

### Просмотр инвентори

Показать все хосты:

```bash
secaudit inventory list --inventory inventory.yml
```

Показать хосты конкретной группы:

```bash
secaudit inventory list --inventory inventory.yml --group production
```

Фильтрация по тегам:

```bash
secaudit inventory list --inventory inventory.yml --tags critical,webserver
```

Подробный вывод:

```bash
secaudit inventory list --inventory inventory.yml --group production -v
```

### Добавление хоста вручную

```bash
secaudit inventory add-host \
  --inventory inventory.yml \
  --ip 192.168.1.100 \
  --hostname custom-server \
  --group production \
  --ssh-port 22 \
  --ssh-user root \
  --ssh-key /etc/secaudit/keys/prod_key \
  --profile profiles/roles/webserver.yml \
  --tags "custom,important"
```

### Обновление инвентори

Обновление через повторное сканирование:

```bash
secaudit inventory update \
  --inventory inventory.yml \
  --scan \
  --networks 192.168.1.0/24
```

### Структура инвентори

Пример файла `inventory.yml`:

```yaml
version: "1.0"
updated: "2025-10-30 19:20:00"

groups:
  production:
    vars:
      ssh_port: 22
      ssh_user: audituser
      ssh_key: /etc/secaudit/keys/prod_key
      profile: profiles/base/server.yml
    
    hosts:
      - hostname: web-server-01
        ip: 192.168.1.10
        os: ubuntu-22.04
        tags: [webserver, critical]
      
      - hostname: db-server-01
        ip: 192.168.1.20
        ssh_port: 2222
        profile: profiles/roles/db.yml
        tags: [database, critical]
```

Полный пример: [inventory_example.yml](examples/inventory_example.yml)

## Удалённый аудит

### Базовый запуск

Аудит всех хостов из инвентори:

```bash
secaudit audit-remote \
  --inventory inventory.yml \
  --output-dir /var/secaudit/reports
```

### Аудит с параметрами

```bash
secaudit audit-remote \
  --inventory inventory.yml \
  --output-dir /var/secaudit/reports \
  --workers 20 \
  --level strict \
  --fail-level high \
  --evidence
```

### Фильтрация хостов

Аудит конкретной группы:

```bash
secaudit audit-remote \
  --inventory inventory.yml \
  --group production \
  --output-dir ./reports
```

Аудит по тегам:

```bash
secaudit audit-remote \
  --inventory inventory.yml \
  --tags "critical,webserver" \
  --output-dir ./reports
```

Фильтрация по ОС:

```bash
secaudit audit-remote \
  --inventory inventory.yml \
  --os ubuntu \
  --output-dir ./reports
```

### Параметры команды audit-remote

- `--inventory` - Путь к файлу инвентори (обязательно)
- `--output-dir` - Директория для сохранения результатов (по умолчанию: results/remote)
- `--workers` - Количество параллельных потоков (по умолчанию: 10)
- `--profile` - Профиль аудита (переопределяет профили из инвентори)
- `--level` - Уровень строгости: baseline, strict, paranoid (по умолчанию: baseline)
- `--fail-level` - Порог для fail: none, low, medium, high (по умолчанию: none)
- `--evidence` - Собирать evidence (улики команд)
- `--group` - Фильтр по группе хостов
- `--tags` - Фильтр по тегам через запятую
- `--os` - Фильтр по ОС
- `--timeout` - Таймаут выполнения на одном хосте в секундах (по умолчанию: 300)

### Структура результатов

Результаты сохраняются в следующей структуре:

```
/var/secaudit/reports/
├── summary.json                          # Сводный отчёт
├── hosts/
│   ├── web-server-01/
│   │   ├── 20251030_192000/
│   │   │   ├── report.json
│   │   │   ├── report.html
│   │   │   ├── report.md
│   │   │   └── evidence/
│   │   └── latest -> 20251030_192000
│   └── db-server-01/
│       └── 20251030_192100/
│           ├── report.json
│           └── report.html
```

### Анализ результатов

Просмотр сводного отчёта:

```bash
cat /var/secaudit/reports/summary.json | jq
```

Просмотр отчёта конкретного хоста:

```bash
cat /var/secaudit/reports/hosts/web-server-01/latest/report.json | jq .summary
```

## Примеры использования

### Пример 1: Аудит новой инфраструктуры

```bash
# Сценарий: Аудит нового дата-центра с несколькими подсетями

# Сканируем все подсети дата-центра (замените на ваши сети)
secaudit scan \
  --networks 10.100.10.0/24,10.100.20.0/24,10.100.30.0/24 \
  -o dc_scan.json

# Создаём инвентори с автоматической группировкой по подсетям
secaudit inventory create \
  --from-scan dc_scan.json \
  -o dc_inventory.yml \
  --auto-group \
  --ssh-key ~/.ssh/audit_key

# Редактируем dc_inventory.yml для настройки групп и профилей
# Например, переименовываем группы:
# - subnet_10_100_10_0 -> web_servers
# - subnet_10_100_20_0 -> app_servers
# - subnet_10_100_30_0 -> db_servers

# Запускаем аудит
secaudit audit-remote \
  --inventory dc_inventory.yml \
  --output-dir ./dc_audit_reports \
  --level baseline \
  --workers 20
```

### Пример 2: Регулярный мониторинг production

```bash
# Cron задача: ежедневный аудит в 2:00
0 2 * * * /usr/local/bin/secaudit audit-remote \
  --inventory /etc/secaudit/prod_inventory.yml \
  --output-dir /var/secaudit/reports \
  --group production \
  --level strict \
  --workers 10 \
  >> /var/log/secaudit/remote_audit.log 2>&1
```

### Пример 3: Аудит критичных хостов

```bash
secaudit audit-remote \
  --inventory inventory.yml \
  --tags critical \
  --level paranoid \
  --fail-level medium \
  --evidence \
  --output-dir ./critical_audit
```

### Пример 4: Быстрая проверка новых хостов

```bash
# Сценарий: Проверка вновь добавленных серверов в разных локациях

# Сканирование новых серверов (разные подсети)
secaudit scan \
  --networks 172.25.100.0/26,172.25.200.0/26 \
  -o new_servers.json

# Создание временного инвентори
secaudit inventory create \
  --from-scan new_servers.json \
  -o temp_inventory.yml

# Быстрый аудит
secaudit audit-remote \
  --inventory temp_inventory.yml \
  --output-dir ./new_servers_check \
  --level baseline \
  --workers 50
```

## Устранение неполадок

### SSH подключение не работает

**Проблема**: Ошибка "SSH подключение недоступно"

**Решение**:
1. Проверьте доступность хоста: `ping <IP>`
2. Проверьте SSH: `ssh -p <PORT> <USER>@<IP>`
3. Убедитесь, что SSH ключ правильный: `ssh-add -l`
4. Проверьте права на ключ: `chmod 600 /path/to/key`

### Timeout при выполнении аудита

**Проблема**: Аудит не завершается в установленное время

**Решение**:
1. Увеличьте timeout: `--timeout 600`
2. Проверьте нагрузку на хост
3. Упростите профиль аудита

### Не удаётся собрать результаты

**Проблема**: Аудит выполнен, но файлы не скопированы

**Решение**:
1. Проверьте наличие `scp` на целевом хосте
2. Проверьте доступное место на диске
3. Проверьте права доступа к директориям

### Большое количество хостов

**Проблема**: Медленное выполнение при сканировании > 500 хостов

**Решение**:
1. Увеличьте workers: `--workers 100`
2. Разбейте на подсети и сканируйте параллельно
3. Используйте более быстрый ping-method: `--ping-method tcp`

### Проблемы с памятью

**Проблема**: Out of memory при большом количестве хостов

**Решение**:
1. Уменьшите workers
2. Разбейте аудит на группы
3. Увеличьте swap на сервере

## Безопасность

### SSH ключи

Используйте выделенные SSH ключи для аудита:

```bash
# Генерация ключа
ssh-keygen -t ed25519 -f /etc/secaudit/keys/audit_key -C "secaudit"

# Копирование на целевые хосты
ssh-copy-id -i /etc/secaudit/keys/audit_key.pub user@host
```

### Пользователь для аудита

Создайте выделенного пользователя с минимальными правами:

```bash
# На целевом хосте
useradd -m -s /bin/bash audituser

# Добавьте sudo права только для необходимых команд
# /etc/sudoers.d/audituser
audituser ALL=(ALL) NOPASSWD: /usr/bin/systemctl status *
audituser ALL=(ALL) NOPASSWD: /usr/bin/cat /etc/*
```

### Защита credentials

Не храните пароли в инвентори. Используйте:
- SSH ключи
- Vault для управления secrets
- Переменные окружения

## Дополнительные ресурсы

- [Архитектура сетевого сканирования](NETWORK_SCANNING_ARCHITECTURE.md)
- [Пример инвентори](examples/inventory_example.yml)
- [Основная документация](../README.md)
