# Руководство по развертыванию SecAudit+

## Содержание

- [Docker](#docker)
- [Docker Compose](#docker-compose)
- [Kubernetes](#kubernetes)
- [Helm](#helm)
- [Мониторинг](#мониторинг)
- [Troubleshooting](#troubleshooting)

---

## Docker

### Сборка образа

```bash
docker build -t secaudit-plus:latest .
```

### Запуск контейнера

```bash
docker run --rm \
  --privileged \
  -v $(pwd)/profiles:/app/profiles:ro \
  -v $(pwd)/results:/app/results \
  -v /etc:/host/etc:ro \
  -v /var:/host/var:ro \
  secaudit-plus:latest audit --profile profiles/base/linux.yml
```

### Использование образа из GitHub Container Registry

```bash
# Pull образа
docker pull ghcr.io/alexbergh/secaudit-core:latest

# Запуск
docker run --rm ghcr.io/alexbergh/secaudit-core:latest --help
```

---

## Docker Compose

### Быстрый старт

```bash
# Запуск аудита
docker-compose run --rm secaudit

# Development режим
docker-compose run --rm secaudit-dev

# Запуск тестов
docker-compose run --rm secaudit-test
```

### Конфигурация

Отредактируйте `docker-compose.yml` для изменения:
- Профилей аудита
- Уровня проверок (baseline/strict/paranoid)
- Количества workers
- Resource limits

---

## Kubernetes

### Прямое развертывание

#### 1. Создание Namespace

```bash
kubectl create namespace secaudit
```

#### 2. Создание ConfigMap для профилей

```bash
kubectl create configmap secaudit-profiles \
  --from-file=profiles/ \
  -n secaudit
```

#### 3. Создание PVC для результатов

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: secaudit-results
  namespace: secaudit
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

```bash
kubectl apply -f pvc.yaml
```

#### 4. Развертывание приложения

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secaudit
  namespace: secaudit
spec:
  replicas: 1
  selector:
    matchLabels:
      app: secaudit
  template:
    metadata:
      labels:
        app: secaudit
    spec:
      containers:
      - name: secaudit
        image: ghcr.io/alexbergh/secaudit-core:latest
        command: ["secaudit", "audit", "--profile", "/profiles/base/linux.yml"]
        volumeMounts:
        - name: profiles
          mountPath: /profiles
        - name: results
          mountPath: /app/results
        - name: host-etc
          mountPath: /host/etc
          readOnly: true
      volumes:
      - name: profiles
        configMap:
          name: secaudit-profiles
      - name: results
        persistentVolumeClaim:
          claimName: secaudit-results
      - name: host-etc
        hostPath:
          path: /etc
```

```bash
kubectl apply -f deployment.yaml
```

---

## Helm

### Установка

#### 1. Добавление Helm репозитория (если опубликован)

```bash
helm repo add secaudit https://alexbergh.github.io/secaudit-core
helm repo update
```

#### 2. Установка из локального chart

```bash
cd helm/secaudit
helm install secaudit . -n secaudit --create-namespace
```

#### 3. Установка с кастомными значениями

```bash
helm install secaudit ./helm/secaudit \
  -n secaudit \
  --create-namespace \
  -f custom-values.yaml
```

### Конфигурация

Создайте `custom-values.yaml`:

```yaml
image:
  tag: "1.0.0"

config:
  level: strict
  workers: 8
  profiles:
    - profiles/base/linux.yml
    - profiles/os/debian.yml

resources:
  limits:
    cpu: 4000m
    memory: 2Gi
  requests:
    cpu: 1000m
    memory: 1Gi

persistence:
  enabled: true
  size: 20Gi

cronjob:
  enabled: true
  schedule: "0 2 * * *"

monitoring:
  serviceMonitor:
    enabled: true
```

### Обновление

```bash
helm upgrade secaudit ./helm/secaudit -n secaudit -f custom-values.yaml
```

### Удаление

```bash
helm uninstall secaudit -n secaudit
```

---

## Мониторинг

### Prometheus

#### Установка ServiceMonitor

```bash
kubectl apply -f helm/secaudit/templates/servicemonitor.yaml
```

#### Prometheus Rules

```bash
kubectl apply -f monitoring/prometheus-rules.yaml
```

### Grafana

#### Импорт Dashboard

1. Откройте Grafana UI
2. Перейдите в Dashboards -> Import
3. Загрузите `monitoring/grafana-dashboard.json`
4. Выберите Prometheus data source
5. Нажмите Import

#### Доступные метрики

- `secaudit_score` - общий балл аудита (0-100)
- `secaudit_checks_total` - количество проверок по результатам
- `secaudit_audit_duration_seconds` - длительность аудита
- `secaudit_last_audit_timestamp` - timestamp последнего аудита

### Алерты

Настроены следующие алерты:
- **SecAuditLowScore** - балл < 50%
- **SecAuditCriticalScore** - балл < 30%
- **SecAuditHighFailureRate** - высокая частота провалов
- **SecAuditAuditNotRunning** - аудит не запускался > 24ч
- **SecAuditHighSeverityFailures** - > 5 критичных провалов

---

## Автоматизация

### CronJob для периодических аудитов

```yaml
cronjob:
  enabled: true
  schedule: "0 2 * * *"  # Ежедневно в 2:00
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
```

### CI/CD Integration

#### GitHub Actions

Workflow автоматически:
- Собирает Docker образ
- Публикует в GHCR
- Генерирует SBOM
- Сканирует на уязвимости (Trivy)
- Загружает результаты в GitHub Security

#### GitLab CI

```yaml
stages:
  - build
  - deploy

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  script:
    - helm upgrade --install secaudit ./helm/secaudit \
        --set image.tag=$CI_COMMIT_SHA \
        -n secaudit
```

---

## Troubleshooting

### Проблема: Контейнер требует privileged режим

**Решение**: SecAudit+ требует доступ к системным ресурсам хоста.

```yaml
securityContext:
  privileged: true
```

### Проблема: Недостаточно прав для чтения /etc

**Решение**: Используйте hostPath volumes:

```yaml
volumes:
- name: host-etc
  hostPath:
    path: /etc
    type: Directory
```

### Проблема: Результаты не сохраняются

**Решение**: Проверьте PVC и права доступа:

```bash
kubectl get pvc -n secaudit
kubectl describe pvc secaudit-results -n secaudit
```

### Проблема: Helm chart не устанавливается

**Решение**: Проверьте values и зависимости:

```bash
helm lint ./helm/secaudit
helm template secaudit ./helm/secaudit --debug
```

### Проблема: Метрики не собираются

**Решение**: Проверьте ServiceMonitor и Prometheus:

```bash
kubectl get servicemonitor -n secaudit
kubectl logs -n monitoring prometheus-xxx
```

---

## Best Practices

### Security

1. Используйте конкретные теги образов, не `latest`
2. Сканируйте образы на уязвимости перед деплоем
3. Ограничивайте ресурсы (CPU/Memory)
4. Используйте NetworkPolicies для изоляции
5. Регулярно обновляйте зависимости

### Performance

1. Настройте количество workers под ваше окружение
2. Используйте SSD для PVC с результатами
3. Включите кэширование для повторяющихся проверок
4. Мониторьте использование ресурсов

### Reliability

1. Настройте health checks
2. Используйте PodDisruptionBudget
3. Настройте автоматические бэкапы результатов
4. Включите алерты в Prometheus
5. Логируйте в централизованную систему

---

## Примеры использования

### Одноразовый аудит

```bash
kubectl run secaudit-once \
  --image=ghcr.io/alexbergh/secaudit-core:latest \
  --restart=Never \
  --rm -it \
  -- audit --profile profiles/base/linux.yml
```

### Аудит с кастомными переменными

```bash
helm install secaudit ./helm/secaudit \
  --set config.level=paranoid \
  --set config.workers=16 \
  --set resources.limits.cpu=8000m
```

### Экспорт результатов

```bash
kubectl cp secaudit/secaudit-pod:/app/results ./local-results
```

---

## Поддержка

- GitHub Issues: https://github.com/alexbergh/secaudit-core/issues
- Documentation: https://github.com/alexbergh/secaudit-core/tree/main/docs
- Security: См. SECURITY.md
