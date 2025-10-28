## RBAC для SecAudit+

**Версия**: 1.0  
**Дата**: 2025-01-28

## Содержание

- [Обзор](#обзор)
- [Роли и права](#роли-и-права)
- [Kubernetes RBAC](#kubernetes-rbac)
- [API Authentication](#api-authentication)
- [Audit Logging](#audit-logging)
- [Setup Guide](#setup-guide)

---

## Обзор

SecAudit+ поддерживает role-based access control (RBAC) для multi-user deployments:

- **3 роли**: Viewer, Auditor, Admin
- **Kubernetes RBAC** - native integration
- **API Authentication** - JWT и API keys
- **Audit Logging** - полный audit trail всех действий

### Архитектура

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ├─ Authentication (JWT/API Key)
       │
       ├─ Authorization (Role Check)
       │
       ├─ Action Execution
       │
       └─ Audit Logging
```

---

## Роли и права

### Viewer (Просмотр)

**Назначение**: Просмотр результатов аудита

**Права**:
- ✅ Просмотр результатов аудита
- ✅ Просмотр логов
- ✅ Просмотр статуса pods
- ❌ Запуск аудитов
- ❌ Изменение конфигурации
- ❌ Управление пользователями

**Use cases**:
- Security team members
- Compliance officers
- Stakeholders

### Auditor (Аудитор)

**Назначение**: Выполнение аудитов и управление результатами

**Права**:
- ✅ Все права Viewer
- ✅ Запуск аудитов
- ✅ Управление pods
- ✅ Создание/обновление ConfigMaps
- ✅ Управление Jobs/CronJobs
- ✅ Выполнение команд в pods
- ❌ Управление пользователями
- ❌ Изменение RBAC

**Use cases**:
- Security engineers
- DevOps engineers
- CI/CD pipelines

### Admin (Администратор)

**Назначение**: Полный контроль над системой

**Права**:
- ✅ Все права Auditor
- ✅ Управление пользователями
- ✅ Изменение конфигурации
- ✅ Управление RBAC
- ✅ Полный доступ ко всем ресурсам

**Use cases**:
- Security administrators
- Platform administrators

---

## Kubernetes RBAC

### Roles

SecAudit+ создает 4 Kubernetes роли:

#### 1. secaudit-viewer (Role)
```yaml
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["secaudit-results"]
    verbs: ["get", "list", "watch"]
  
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get", "list"]
  
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
```

#### 2. secaudit-auditor (Role)
```yaml
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
  
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch", "create", "delete"]
  
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

#### 3. secaudit-admin (Role)
```yaml
rules:
  - apiGroups: [""]
    resources: ["*"]
    verbs: ["*"]
  
  - apiGroups: ["apps", "batch"]
    resources: ["*"]
    verbs: ["*"]
```

#### 4. secaudit-node-auditor (ClusterRole)
```yaml
rules:
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list", "watch"]
  
  - apiGroups: ["policy"]
    resources: ["podsecuritypolicies"]
    verbs: ["get", "list", "watch"]
  
  - apiGroups: ["networking.k8s.io"]
    resources: ["networkpolicies"]
    verbs: ["get", "list", "watch"]
```

### Настройка в Helm

**values.yaml**:
```yaml
rbac:
  create: true
  
  viewers:
    - name: security-team
      kind: Group
    - name: viewer@example.com
      kind: User
  
  auditors:
    - name: audit-operators
      kind: Group
    - name: ci-pipeline
      kind: ServiceAccount
      namespace: ci-cd
  
  admins:
    - name: security-admins
      kind: Group
    - name: admin@example.com
      kind: User
```

**Установка**:
```bash
helm install secaudit ./helm/secaudit \
  --set rbac.create=true \
  --set rbac.viewers[0].name=security-team \
  --set rbac.viewers[0].kind=Group
```

### Проверка прав

```bash
# Check as viewer
kubectl auth can-i get configmaps --as=viewer@example.com -n secaudit
# yes

kubectl auth can-i create pods --as=viewer@example.com -n secaudit
# no

# Check as auditor
kubectl auth can-i create jobs --as=auditor@example.com -n secaudit
# yes
```

---

## API Authentication

### JWT Authentication

#### Генерация токена

```python
from seclib.auth import JWTAuth, Role

jwt_auth = JWTAuth(secret="your-secret-key", issuer="secaudit")
token = jwt_auth.create_token(
    username="user@example.com",
    roles=[Role.AUDITOR]
)
print(token)
```

#### Использование токена

```bash
# HTTP header
curl -H "Authorization: Bearer ${TOKEN}" \
     https://secaudit.example.com/api/audit/start
```

#### Верификация

```python
from seclib.auth import JWTAuth

jwt_auth = JWTAuth(secret="your-secret-key")
user = jwt_auth.verify_token(token)

if user:
    print(f"Authenticated: {user.username}")
    print(f"Roles: {[r.value for r in user.roles]}")
```

### API Key Authentication

#### Генерация ключа

```python
from seclib.auth import APIKeyAuth

# Generate new key
api_key = APIKeyAuth.generate_key()
print(f"API Key: {api_key}")

# Hash for storage
key_hash = APIKeyAuth.hash_key(api_key)
print(f"Hash: {key_hash}")
```

#### Конфигурация

```yaml
# values.yaml
authentication:
  apiKeys:
    enabled: true
    keys:
      - name: ci-pipeline
        hash: "sha256_hash_here"
        roles: [auditor]
      
      - name: monitoring
        hash: "sha256_hash_here"
        roles: [viewer]
```

#### Использование

```bash
# HTTP header
curl -H "X-API-Key: ${API_KEY}" \
     https://secaudit.example.com/api/results
```

### OIDC Integration

```yaml
# values.yaml
authentication:
  oidc:
    enabled: true
    issuerUrl: https://accounts.google.com
    clientId: your-client-id
    clientSecret: your-client-secret
```

---

## Audit Logging

### Типы событий

SecAudit+ логирует все security-relevant события:

#### Authentication Events
- `auth.success` - Успешная аутентификация
- `auth.failure` - Неудачная аутентификация
- `auth.logout` - Выход из системы

#### Audit Execution Events
- `audit.start` - Начало аудита
- `audit.complete` - Завершение аудита
- `audit.failed` - Ошибка аудита
- `audit.cancelled` - Отмена аудита

#### Resource Access Events
- `results.view` - Просмотр результатов
- `results.download` - Скачивание результатов
- `results.delete` - Удаление результатов

#### Configuration Events
- `config.view` - Просмотр конфигурации
- `config.update` - Изменение конфигурации
- `profile.load` - Загрузка профиля

#### User Management Events
- `user.create` - Создание пользователя
- `user.update` - Обновление пользователя
- `user.delete` - Удаление пользователя
- `role.assign` - Назначение роли
- `role.revoke` - Отзыв роли

### Формат логов

**JSON format**:
```json
{
  "timestamp": "2025-01-28T10:15:30Z",
  "event_type": "audit.start",
  "severity": "info",
  "username": "user@example.com",
  "source_ip": "192.168.1.100",
  "action": "start_audit",
  "resource": "profiles/base/linux.yml",
  "result": "success",
  "details": {
    "level": "strict",
    "workers": 4
  },
  "session_id": "abc123"
}
```

### Конфигурация

```yaml
# values.yaml
auditLog:
  enabled: true
  logLevel: INFO
  retentionDays: 90
  
  destinations:
    # File logging
    - type: file
      path: /app/logs/audit.log
    
    # Syslog
    - type: syslog
      host: syslog.example.com
      port: 514
    
    # Elasticsearch
    - type: elasticsearch
      url: https://elasticsearch.example.com
      index: secaudit-audit
```

### Использование

```python
from utils.audit_logger import get_audit_logger

audit_log = get_audit_logger()

# Log authentication
audit_log.log_auth_success(
    username="user@example.com",
    source_ip="192.168.1.100"
)

# Log audit execution
audit_log.log_audit_start(
    username="user@example.com",
    profile="profiles/base/linux.yml",
    level="strict",
    source_ip="192.168.1.100"
)

# Log audit completion
audit_log.log_audit_complete(
    username="user@example.com",
    profile="profiles/base/linux.yml",
    duration=120.5,
    score=85.0,
    checks_total=100,
    checks_passed=85,
    checks_failed=15
)
```

### Просмотр логов

```bash
# Tail audit log
kubectl logs -f deployment/secaudit -n secaudit | grep audit.log

# Search for specific user
kubectl exec -it deployment/secaudit -n secaudit -- \
  grep "user@example.com" /app/logs/audit.log

# Export to file
kubectl cp secaudit/secaudit-pod:/app/logs/audit.log ./audit.log
```

---

## Setup Guide

### 1. Enable RBAC в Helm

```bash
helm install secaudit ./helm/secaudit \
  --set rbac.create=true \
  --set rbac.viewers[0].name=security-team \
  --set rbac.viewers[0].kind=Group \
  --set rbac.auditors[0].name=audit-operators \
  --set rbac.auditors[0].kind=Group \
  --set rbac.admins[0].name=security-admins \
  --set rbac.admins[0].kind=Group
```

### 2. Configure Authentication

```bash
# Generate JWT secret
JWT_SECRET=$(openssl rand -hex 32)

# Generate API key
API_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
API_KEY_HASH=$(echo -n "$API_KEY" | sha256sum | cut -d' ' -f1)

# Install with authentication
helm install secaudit ./helm/secaudit \
  --set authentication.jwt.enabled=true \
  --set authentication.jwt.secret="$JWT_SECRET" \
  --set authentication.apiKeys.enabled=true \
  --set authentication.apiKeys.keys[0].name=ci-pipeline \
  --set authentication.apiKeys.keys[0].hash="$API_KEY_HASH"
```

### 3. Enable Audit Logging

```bash
helm install secaudit ./helm/secaudit \
  --set auditLog.enabled=true \
  --set auditLog.logLevel=INFO \
  --set auditLog.retentionDays=90
```

### 4. Verify Setup

```bash
# Check RBAC roles
kubectl get roles -n secaudit

# Check role bindings
kubectl get rolebindings -n secaudit

# Check audit logs
kubectl logs deployment/secaudit -n secaudit | tail -20
```

---

## Best Practices

### Security

1. **Principle of Least Privilege** - назначайте минимально необходимые роли
2. **Regular Audits** - регулярно проверяйте назначенные роли
3. **Token Rotation** - меняйте JWT secrets и API keys регулярно
4. **Audit Log Monitoring** - настройте алерты на подозрительные события
5. **Secure Storage** - храните secrets в Kubernetes Secrets или Vault

### Operational

1. **Use Groups** - назначайте роли группам, а не отдельным пользователям
2. **Document Access** - документируйте кто и почему имеет доступ
3. **Automate Provisioning** - автоматизируйте создание пользователей
4. **Monitor Usage** - отслеживайте использование API
5. **Backup Audit Logs** - регулярно делайте backup логов

### Compliance

1. **Retention Policy** - определите политику хранения логов
2. **Access Reviews** - проводите регулярные ревью доступов
3. **Separation of Duties** - разделяйте обязанности между ролями
4. **Audit Trail** - обеспечьте полный audit trail
5. **Incident Response** - подготовьте процедуры реагирования

---

## Troubleshooting

### User cannot access resources

```bash
# Check role bindings
kubectl get rolebindings -n secaudit -o yaml

# Check user permissions
kubectl auth can-i --list --as=user@example.com -n secaudit
```

### Authentication fails

```bash
# Check JWT secret
kubectl get secret secaudit-jwt -n secaudit -o yaml

# Verify API key hash
python3 -c "import hashlib; print(hashlib.sha256(b'your-api-key').hexdigest())"
```

### Audit logs not appearing

```bash
# Check audit logger configuration
kubectl describe configmap secaudit-config -n secaudit

# Check pod logs
kubectl logs deployment/secaudit -n secaudit --tail=100
```

---

## References

- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [NIST Access Control](https://csrc.nist.gov/projects/role-based-access-control)

---

**Последнее обновление**: 2025-01-28  
**Владелец**: Security Team
