# Encryption для SecAudit+

**Версия**: 1.0  
**Дата**: 2025-01-28

## Содержание

- [Обзор](#обзор)
- [GPG Encryption для отчетов](#gpg-encryption-для-отчетов)
- [AES Encryption](#aes-encryption)
- [Secrets Management](#secrets-management)
- [TLS Configuration](#tls-configuration)
- [Encryption at Rest](#encryption-at-rest)
- [Best Practices](#best-practices)

---

## Обзор

SecAudit+ поддерживает multiple layers of encryption:

1. **GPG Encryption** - для отчетов и sensitive данных
2. **AES Encryption** - для temporary data и session encryption
3. **TLS/mTLS** - для передачи данных
4. **Secrets Management** - Kubernetes Secrets, Vault, External Secrets
5. **Encryption at Rest** - для persistent storage

### Архитектура

```
┌─────────────────────────────────────────┐
│         Data Protection Layers          │
├─────────────────────────────────────────┤
│  Application Layer                      │
│  ├─ GPG Encryption (Reports)            │
│  └─ AES Encryption (Temp Data)          │
├─────────────────────────────────────────┤
│  Transport Layer                        │
│  ├─ TLS 1.3 (HTTPS)                     │
│  └─ mTLS (Client Certificates)          │
├─────────────────────────────────────────┤
│  Storage Layer                          │
│  ├─ Encrypted PVC                       │
│  └─ Encrypted etcd                      │
├─────────────────────────────────────────┤
│  Secrets Management                     │
│  ├─ Kubernetes Secrets                  │
│  ├─ HashiCorp Vault                     │
│  └─ External Secrets Operator           │
└─────────────────────────────────────────┘
```

---

## GPG Encryption для отчетов

### Использование

```python
from seclib.encryption import get_gpg_encryption
from pathlib import Path

gpg = get_gpg_encryption()

# Encrypt report
result = gpg.encrypt_report(
    report_file=Path("results/report.json"),
    recipients=["security-team@example.com"],
    sign=True,
    remove_original=False
)

if result.success:
    print(f"Encrypted: {result.output_file}")
else:
    print(f"Error: {result.error}")
```

### Setup GPG Keys

```bash
# Generate key pair
gpg --full-generate-key

# Export public key
gpg --armor --export security-team@example.com > public.key

# Export private key (keep secure!)
gpg --armor --export-secret-keys security-team@example.com > private.key

# Import to Kubernetes
kubectl create secret generic secaudit-encryption \
  --from-file=gpg-public-key=public.key \
  --from-file=gpg-private-key=private.key \
  --from-literal=gpg-passphrase="your-passphrase" \
  -n secaudit
```

### Helm Configuration

```yaml
# values.yaml
encryption:
  enabled: true
  gpg:
    enabled: true
    recipients:
      - security-team@example.com
      - compliance@example.com
    sign: true
    removeOriginal: false
```

```bash
# Install with encryption
helm install secaudit ./helm/secaudit \
  --set encryption.enabled=true \
  --set encryption.gpg.enabled=true \
  --set-file encryption.gpg.publicKey=public.key \
  --set encryption.gpg.passphrase="your-passphrase"
```

### Decryption

```bash
# Decrypt report
gpg --decrypt results/report.json.gpg > report.json

# Verify signature
gpg --verify results/report.json.gpg
```

---

## AES Encryption

### Использование

```python
from seclib.encryption import AESEncryption
from pathlib import Path

# Generate key
key = AESEncryption.generate_key()
print(f"AES Key: {key.hex()}")

# Initialize
aes = AESEncryption(key=key)

# Encrypt data
data = b"Sensitive information"
encrypted = aes.encrypt(data)

# Decrypt data
decrypted = aes.decrypt(encrypted)
assert data == decrypted

# Encrypt file
aes.encrypt_file(
    input_file=Path("data.txt"),
    output_file=Path("data.txt.enc")
)
```

### Helm Configuration

```yaml
# values.yaml
encryption:
  aes:
    enabled: true
    key: ""  # Generated automatically if empty
```

```bash
# Generate AES key
AES_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Install with AES
helm install secaudit ./helm/secaudit \
  --set encryption.aes.enabled=true \
  --set encryption.aes.key="$AES_KEY"
```

---

## Secrets Management

### Kubernetes Secrets

**Basic usage**:
```bash
# Create secret
kubectl create secret generic secaudit-secrets \
  --from-literal=jwt-secret="$(openssl rand -hex 32)" \
  --from-literal=api-key="$(openssl rand -hex 32)" \
  -n secaudit

# Use in pod
kubectl set env deployment/secaudit \
  --from=secret/secaudit-secrets \
  -n secaudit
```

**Helm values**:
```yaml
authentication:
  jwt:
    secret: ""  # Set via --set or external secret
  apiKeys:
    keys:
      - name: ci-pipeline
        key: ""  # Set via --set or external secret
```

### HashiCorp Vault

**Setup**:
```bash
# Enable Vault
vault secrets enable -path=secaudit kv-v2

# Store secrets
vault kv put secaudit/config \
  gpg_passphrase="your-passphrase" \
  jwt_secret="$(openssl rand -hex 32)" \
  aes_key="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# Create policy
vault policy write secaudit - <<EOF
path "secaudit/data/config" {
  capabilities = ["read"]
}
EOF

# Create role
vault write auth/kubernetes/role/secaudit \
  bound_service_account_names=secaudit \
  bound_service_account_namespaces=secaudit \
  policies=secaudit \
  ttl=24h
```

**Helm configuration**:
```yaml
vault:
  enabled: true
  role: secaudit
  secretPath: secret/data/secaudit/config
  agentInject: true
```

**Pod annotations** (automatic):
```yaml
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/role: "secaudit"
  vault.hashicorp.com/agent-inject-secret-config: "secret/data/secaudit/config"
```

### External Secrets Operator

**Setup**:
```bash
# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets-system --create-namespace

# Create SecretStore
kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: secaudit
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secaudit"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "secaudit"
EOF
```

**Helm configuration**:
```yaml
externalSecrets:
  enabled: true
  secretStore: vault-backend
  secretStoreKind: SecretStore
  refreshInterval: 1h
  data:
    - secretKey: gpg-passphrase
      remoteKey: secaudit/config
      property: gpg_passphrase
    - secretKey: jwt-secret
      remoteKey: secaudit/config
      property: jwt_secret
    - secretKey: aes-key
      remoteKey: secaudit/config
      property: aes_key
```

---

## TLS Configuration

### Self-Signed Certificates

```bash
# Generate CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/CN=SecAudit CA"

# Generate server certificate
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/CN=secaudit.example.com"

# Sign with CA
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 365

# Create Kubernetes secret
kubectl create secret tls secaudit-tls \
  --cert=server.crt \
  --key=server.key \
  -n secaudit
```

### Cert-Manager (Let's Encrypt)

**Install cert-manager**:
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

**Create ClusterIssuer**:
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```

**Helm configuration**:
```yaml
tls:
  enabled: true
  certManager:
    enabled: true
    issuer: letsencrypt-prod
    issuerKind: ClusterIssuer
    challengeType: http01
    duration: 2160h  # 90 days
    renewBefore: 360h  # 15 days

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: secaudit.example.com
      paths:
        - path: /
          pathType: Prefix
```

### mTLS (Mutual TLS)

**Generate client certificates**:
```bash
# Client key
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr \
  -subj "/CN=client@example.com"

# Sign with CA
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out client.crt -days 365
```

**Helm configuration**:
```yaml
tls:
  mtls:
    enabled: true
    requireClientCert: true
    clientCA: |
      -----BEGIN CERTIFICATE-----
      ... CA certificate ...
      -----END CERTIFICATE-----
```

**Nginx Ingress annotations**:
```yaml
annotations:
  nginx.ingress.kubernetes.io/auth-tls-verify-client: "on"
  nginx.ingress.kubernetes.io/auth-tls-secret: "secaudit/client-ca"
  nginx.ingress.kubernetes.io/auth-tls-verify-depth: "1"
```

---

## Encryption at Rest

### Encrypted Storage Class

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: encrypted-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  encrypted: "true"
  kmsKeyId: "arn:aws:kms:region:account:key/key-id"
```

**Helm configuration**:
```yaml
encryption:
  atRest:
    enabled: true
    storageClass: encrypted-ssd

persistence:
  enabled: true
  storageClass: encrypted-ssd
  size: 10Gi
```

### Encrypted etcd

**Kubernetes encryption config**:
```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64 encoded secret>
      - identity: {}
```

---

## Best Practices

### Key Management

1. **Rotation** - меняйте ключи регулярно (90-365 дней)
2. **Separation** - разные ключи для разных целей
3. **Backup** - храните backup ключей в secure location
4. **Access Control** - ограничьте доступ к ключам
5. **Audit** - логируйте все операции с ключами

### Encryption Strategy

1. **Defense in Depth** - используйте multiple layers
2. **Encrypt Sensitive Data** - всегда шифруйте PII, credentials
3. **Use Strong Algorithms** - AES-256, RSA-4096, TLS 1.3
4. **Verify Integrity** - используйте signatures и MACs
5. **Secure Transport** - всегда используйте TLS

### Secrets Management

1. **Never Commit Secrets** - используйте .gitignore
2. **Use Secret Managers** - Vault, External Secrets
3. **Principle of Least Privilege** - минимальный доступ
4. **Rotate Regularly** - автоматическая ротация
5. **Monitor Access** - audit logging для secrets

### Compliance

1. **GDPR** - encryption для personal data
2. **PCI DSS** - encryption для payment data
3. **HIPAA** - encryption для health data
4. **SOC 2** - encryption controls
5. **ISO 27001** - cryptographic controls

---

## Examples

### Complete Setup

```bash
# 1. Generate keys
GPG_KEY=$(gpg --gen-key --batch <<EOF
%no-protection
Key-Type: RSA
Key-Length: 4096
Name-Real: SecAudit
Name-Email: secaudit@example.com
Expire-Date: 1y
EOF
)

AES_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
JWT_SECRET=$(openssl rand -hex 32)

# 2. Create secrets
kubectl create secret generic secaudit-encryption \
  --from-file=gpg-public-key=<(gpg --armor --export secaudit@example.com) \
  --from-file=gpg-private-key=<(gpg --armor --export-secret-keys secaudit@example.com) \
  --from-literal=gpg-passphrase="" \
  -n secaudit

kubectl create secret generic secaudit-auth \
  --from-literal=jwt-secret="$JWT_SECRET" \
  --from-literal=aes-key="$AES_KEY" \
  -n secaudit

# 3. Install with encryption
helm install secaudit ./helm/secaudit \
  --set encryption.enabled=true \
  --set encryption.gpg.enabled=true \
  --set encryption.aes.enabled=true \
  --set tls.enabled=true \
  --set tls.certManager.enabled=true \
  -n secaudit
```

### Encrypt Report Manually

```bash
# Using CLI
secaudit audit --profile profiles/base/linux.yml --encrypt --recipients security-team@example.com

# Using Python
python3 << 'EOF'
from seclib.encryption import get_gpg_encryption
from pathlib import Path

gpg = get_gpg_encryption()
result = gpg.encrypt_report(
    report_file=Path("results/report.json"),
    recipients=["security-team@example.com"],
    sign=True
)
print(f"Encrypted: {result.output_file}")
EOF
```

---

## Troubleshooting

### GPG encryption fails

```bash
# Check GPG keys
gpg --list-keys
gpg --list-secret-keys

# Import key
gpg --import public.key

# Trust key
gpg --edit-key secaudit@example.com
> trust
> 5 (ultimate)
> quit
```

### TLS certificate issues

```bash
# Check certificate
openssl x509 -in server.crt -text -noout

# Verify certificate chain
openssl verify -CAfile ca.crt server.crt

# Check cert-manager
kubectl get certificate -n secaudit
kubectl describe certificate secaudit-cert -n secaudit
```

### Vault connection fails

```bash
# Check Vault status
kubectl exec -it deployment/secaudit -n secaudit -- vault status

# Check service account
kubectl get sa secaudit -n secaudit -o yaml

# Check Vault logs
kubectl logs -l app=vault -n vault
```

---

## References

- [GPG Documentation](https://gnupg.org/documentation/)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [HashiCorp Vault](https://www.vaultproject.io/docs)
- [External Secrets Operator](https://external-secrets.io/)
- [Cert-Manager](https://cert-manager.io/docs/)

---

**Последнее обновление**: 2025-01-28  
**Владелец**: Security Team
