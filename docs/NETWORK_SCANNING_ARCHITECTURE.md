# Архитектура сканирования сети и удалённого аудита

## Обзор

Данный документ описывает архитектуру для внедрения функциональности сканирования сети, управления инвентори хостов и удалённого запуска аудитов безопасности в проекте SecAudit+.

## Цели

1. **Сканирование сети**: Обнаружение активных хостов в заданных подсетях
2. **Управление инвентори**: Создание и управление списком обнаруженных хостов с их метаданными
3. **Удалённое выполнение**: Запуск аудитов безопасности на удалённых хостах
4. **Централизованное хранение**: Сбор и хранение отчётов на центральном сервере SecAudit+

## Компоненты системы

### 1. Модуль сканирования сети (`modules/network_scanner.py`)

**Назначение**: Обнаружение активных хостов в сети

**Основные функции**:
- Ping-сканирование подсетей (ICMP/TCP)
- Определение доступности SSH порта (22, 2222, кастомные)
- Определение ОС по баннеру SSH
- Параллельное сканирование для производительности
- Поддержка множественных сетей

**Зависимости**:
```python
# Добавить в requirements.txt:
# nmap-python>=0.7.1  # Python wrapper для nmap
# paramiko>=3.4.0     # SSH клиент
# netaddr>=0.10.1     # Работа с IP адресами
```

**Пример использования**:
```bash
# Сканирование одной сети
secaudit scan --network 192.168.1.0/24 --output inventory.yml

# Сканирование множественных сетей
secaudit scan --networks 192.168.1.0/24,10.0.0.0/24 --ssh-ports 22,2222

# Сканирование с фильтрацией по ОС
secaudit scan --network 192.168.1.0/24 --filter-os ubuntu,debian
```

### 2. Модуль управления инвентори (`modules/inventory_manager.py`)

**Назначение**: Управление списком обнаруженных хостов

**Структура данных инвентори** (YAML):
```yaml
version: "1.0"
updated: "2025-10-30T19:20:00Z"
groups:
  production:
    vars:
      ssh_port: 22
      ssh_user: audituser
      profile: profiles/base/server.yml
    hosts:
      - hostname: web-server-01
        ip: 192.168.1.10
        os: ubuntu-22.04
        ssh_key: /etc/secaudit/keys/prod_key
        tags:
          - webserver
          - critical
      - hostname: db-server-01
        ip: 192.168.1.20
        os: ubuntu-22.04
        profile: profiles/roles/db.yml
        tags:
          - database
          - critical
  development:
    vars:
      ssh_port: 22
      ssh_user: devuser
      profile: profiles/base/linux.yml
    hosts:
      - hostname: dev-01
        ip: 10.0.0.10
        os: ubuntu-20.04
```

**Основные функции**:
- Создание и обновление инвентори из результатов сканирования
- Группировка хостов (prod, dev, test и т.д.)
- Управление метаданными хостов
- Фильтрация хостов по тегам, группам, ОС
- Импорт/экспорт в различных форматах (YAML, JSON, Ansible inventory)

**Пример использования**:
```bash
# Создание инвентори из сканирования
secaudit inventory create --from-scan scan_results.json --output inventory.yml

# Добавление хоста вручную
secaudit inventory add-host \
  --ip 192.168.1.100 \
  --hostname custom-server \
  --group production \
  --tags "custom,important"

# Просмотр инвентори
secaudit inventory list --group production
secaudit inventory list --tags critical

# Обновление инвентори (повторное сканирование)
secaudit inventory update --scan --networks 192.168.1.0/24
```

### 3. Модуль удалённого выполнения (`modules/remote_executor.py`)

**Назначение**: Выполнение аудитов на удалённых хостах

**Режимы работы**:

#### A. SSH режим (агентлесс)
- Подключение по SSH к каждому хосту
- Копирование необходимых файлов (профили, скрипты)
- Выполнение аудита удалённо
- Сбор результатов обратно на сервер

#### B. Agent режим (опциональный)
- Установка лёгкого агента на целевых хостах
- Агент получает задачи через API/очередь
- Выполнение аудита локально
- Отправка результатов на сервер

**Основные функции**:
- Параллельное выполнение на множестве хостов
- Управление SSH ключами и credentials
- Обработка ошибок и retry логика
- Прогресс бар и логирование
- Сбор и централизованное хранение отчётов

**Пример использования**:
```bash
# Запуск аудита на всех хостах из инвентори
secaudit audit-remote \
  --inventory inventory.yml \
  --workers 10 \
  --output-dir /var/secaudit/reports

# Запуск на конкретной группе
secaudit audit-remote \
  --inventory inventory.yml \
  --group production \
  --level strict

# Запуск на хостах с тегами
secaudit audit-remote \
  --inventory inventory.yml \
  --tags "critical,webserver" \
  --fail-level high

# Запуск с кастомным профилем
secaudit audit-remote \
  --inventory inventory.yml \
  --profile profiles/custom/hardened.yml
```

### 4. Модуль централизованного хранения (`modules/report_storage.py`)

**Назначение**: Управление отчётами от множественных хостов

**Структура хранения**:
```
/var/secaudit/reports/
├── inventory.yml
├── hosts/
│   ├── web-server-01/
│   │   ├── 2025-10-30_192000/
│   │   │   ├── report.json
│   │   │   ├── report.html
│   │   │   ├── evidence/
│   │   │   └── metadata.yml
│   │   └── latest -> 2025-10-30_192000
│   └── db-server-01/
│       └── 2025-10-30_192100/
│           ├── report.json
│           └── report.html
└── aggregated/
    ├── 2025-10-30_summary.json
    └── 2025-10-30_dashboard.html
```

**Основные функции**:
- Организация отчётов по хостам и времени
- Агрегированные отчёты по всей инфраструктуре
- История аудитов для каждого хоста
- Сравнение результатов между аудитами
- Web-интерфейс для просмотра (опционально)

## Архитектура взаимодействия

```
┌─────────────────────────────────────────────────────────────┐
│                    SecAudit+ Server                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                CLI Interface                          │   │
│  │  scan | inventory | audit-remote | report             │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Core Modules                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │ Network  │  │Inventory │  │ Remote   │           │   │
│  │  │ Scanner  │→ │ Manager  │→ │ Executor │           │   │
│  │  └──────────┘  └──────────┘  └──────────┘           │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Report Storage & Aggregation                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓ SSH/Agent
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Target      │   │  Target      │   │  Target      │
│  Host 1      │   │  Host 2      │   │  Host N      │
│              │   │              │   │              │
│ ┌──────────┐ │   │ ┌──────────┐ │   │ ┌──────────┐ │
│ │ secaudit │ │   │ │ secaudit │ │   │ │ secaudit │ │
│ │ (local)  │ │   │ │ (local)  │ │   │ │ (local)  │ │
│ └──────────┘ │   │ └──────────┘ │   │ └──────────┘ │
└──────────────┘   └──────────────┘   └──────────────┘
```

## Протокол работы

### Сценарий 1: Полный цикл аудита инфраструктуры

```bash
# Шаг 1: Сканирование сети
secaudit scan \
  --networks 192.168.1.0/24,10.0.0.0/16 \
  --ssh-ports 22,2222 \
  --timeout 5 \
  --output scan_results.json

# Шаг 2: Создание инвентори
secaudit inventory create \
  --from-scan scan_results.json \
  --output inventory.yml \
  --auto-group  # Автоматическая группировка по подсетям

# Шаг 3: Настройка инвентори (опционально)
# Редактирование inventory.yml для добавления групп, тегов, профилей

# Шаг 4: Запуск аудита на всех хостах
secaudit audit-remote \
  --inventory inventory.yml \
  --level strict \
  --workers 20 \
  --output-dir /var/secaudit/reports \
  --fail-level medium \
  --evidence

# Шаг 5: Генерация агрегированного отчёта
secaudit report aggregate \
  --reports-dir /var/secaudit/reports/hosts \
  --output /var/secaudit/reports/aggregated/summary.html
```

### Сценарий 2: Регулярный мониторинг

```bash
# Cron задача для ежедневного аудита
0 2 * * * /usr/local/bin/secaudit audit-remote \
  --inventory /etc/secaudit/inventory.yml \
  --level baseline \
  --workers 20 \
  --output-dir /var/secaudit/reports \
  --quiet

# Оповещение при обнаружении критичных проблем
0 3 * * * /usr/local/bin/secaudit report check-compliance \
  --reports-dir /var/secaudit/reports/hosts \
  --threshold critical \
  --notify-email security@company.com
```

## Безопасность

### Управление credentials

1. **SSH ключи**:
   ```yaml
   # inventory.yml
   security:
     ssh_keys:
       default: /etc/secaudit/keys/default_key
       production: /etc/secaudit/keys/prod_key
       development: /etc/secaudit/keys/dev_key
   ```

2. **Vault интеграция** (опционально):
   - Хранение credentials в HashiCorp Vault
   - Динамическое получение SSH credentials
   - Ротация ключей

3. **Least privilege**:
   - Выделенный пользователь для аудита (read-only где возможно)
   - Sudo права только для необходимых команд
   - Аудит действий пользователя

### Шифрование

- Передача отчётов по зашифрованным каналам (SSH/TLS)
- Опциональное шифрование отчётов at-rest (GPG)
- Редактирование чувствительных данных в отчётах (уже реализовано)

## Производительность и масштабирование

### Оптимизация сканирования

- Параллельное сканирование с настраиваемым числом workers
- Кеширование результатов сканирования
- Incremental сканирование (только новые/изменённые хосты)

### Оптимизация удалённого выполнения

- Connection pooling для SSH соединений
- Batch выполнение на группах хостов
- Приоритизация критичных хостов

### Масштабирование

- Горизонтальное масштабирование: несколько серверов SecAudit+
- Распределённая очередь задач (Celery + Redis/RabbitMQ)
- Load balancing для больших инфраструктур (1000+ хостов)

## Интеграция с существующими инструментами

### Ansible

```yaml
# Использование существующего Ansible inventory
secaudit inventory import-ansible \
  --ansible-inventory /etc/ansible/hosts \
  --output secaudit_inventory.yml
```

### Kubernetes

```bash
# Сканирование узлов k8s кластера
secaudit scan-k8s \
  --kubeconfig ~/.kube/config \
  --namespace default \
  --output k8s_inventory.yml

# Аудит узлов через DaemonSet
kubectl apply -f helm/secaudit/daemonset.yaml
```

### CI/CD

```yaml
# .gitlab-ci.yml
infrastructure-audit:
  stage: security
  script:
    - secaudit audit-remote --inventory inventory.yml --level strict
  artifacts:
    reports:
      junit: results/report.junit.xml
    paths:
      - results/
  allow_failure: true
```

## Мониторинг и alerting

### Метрики

```python
# Дополнительные метрики Prometheus
secaudit_remote_hosts_total{status="success|failed|timeout"}
secaudit_remote_duration_seconds{host="..."}
secaudit_scan_hosts_discovered{network="..."}
secaudit_inventory_hosts_total{group="..."}
```

### Grafana Dashboard

- Общее количество хостов в инвентори
- Статус последнего аудита по хостам
- Тренды compliance по времени
- Top хосты с наибольшим числом проблем
- Карта сети с цветовой индикацией статуса

## План реализации

### Фаза 1: Базовая функциональность (MVP)
1. ✅ Модуль сканирования сети (ping + SSH port check)
2. ✅ Базовое управление инвентори (YAML формат)
3. ✅ SSH удалённое выполнение (агентлесс)
4. ✅ Централизованное хранение отчётов
5. ✅ CLI команды: scan, inventory, audit-remote

### Фаза 2: Расширенная функциональность
1. ⏳ Более глубокое сканирование (OS detection, service discovery)
2. ⏳ Поддержка Ansible inventory формата
3. ⏳ Агрегированные отчёты
4. ⏳ Web UI для просмотра результатов
5. ⏳ Интеграция с Vault для credentials

### Фаза 3: Enterprise функции
1. ⏳ Agent режим для крупных инфраструктур
2. ⏳ Distributed scanning
3. ⏳ API сервер для интеграций
4. ⏳ Real-time мониторинг
5. ⏳ Compliance трекинг и reporting

## Примеры использования

### Малая инфраструктура (< 50 хостов)

```bash
# Простой workflow
secaudit scan --network 192.168.1.0/24 -o scan.json
secaudit inventory create --from-scan scan.json -o inventory.yml
secaudit audit-remote --inventory inventory.yml --workers 10
```

### Средняя инфраструктура (50-500 хостов)

```bash
# С группировкой и планированием
secaudit scan --networks-file networks.txt -o scan.json
secaudit inventory create --from-scan scan.json --auto-group -o inventory.yml
# Настройка inventory.yml
secaudit audit-remote --inventory inventory.yml --workers 50 --schedule "0 2 * * *"
```

### Крупная инфраструктура (> 500 хостов)

```bash
# Распределённое выполнение
# На сервере 1 (prod)
secaudit audit-remote --inventory inventory.yml --group production --workers 100

# На сервере 2 (dev/test)
secaudit audit-remote --inventory inventory.yml --group "development,testing" --workers 50

# Агрегация результатов
secaudit report aggregate --reports-dir /var/secaudit/reports
```

## Заключение

Предложенная архитектура позволяет:
- Автоматизировать обнаружение хостов в сети
- Централизованно управлять инвентори инфраструктуры
- Выполнять масштабируемые аудиты безопасности
- Хранить и анализировать результаты централизованно
- Интегрироваться с существующими инструментами

Реализация будет происходить итеративно, начиная с MVP функциональности и постепенно добавляя расширенные возможности.
