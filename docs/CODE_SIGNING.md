# Code Signing для SecAudit+

**Версия**: 1.0  
**Дата**: 2025-01-28

## Содержание

- [Обзор](#обзор)
- [Docker Image Signing (Cosign)](#docker-image-signing-cosign)
- [Release Signing (GPG)](#release-signing-gpg)
- [Verification](#verification)
- [Setup Instructions](#setup-instructions)

---

## Обзор

SecAudit+ использует два метода подписи:

1. **Cosign** - для подписи Docker образов (keyless signing с GitHub OIDC)
2. **GPG** - для подписи релизов и артефактов

### Преимущества

- **Integrity** - гарантия неизменности артефактов
- **Authenticity** - подтверждение происхождения от официального источника
- **Non-repudiation** - невозможность отказа от авторства
- **Supply chain security** - защита от подмены в цепочке поставок

---

## Docker Image Signing (Cosign)

### Как это работает

1. GitHub Actions строит Docker образ
2. Cosign подписывает образ используя GitHub OIDC (keyless)
3. Подпись хранится в GHCR вместе с образом
4. Пользователи могут верифицировать подпись

### Автоматическая подпись

Workflow `.github/workflows/docker-publish.yml` автоматически:
- Устанавливает Cosign
- Подписывает все теги образа
- Верифицирует подпись
- Публикует в GHCR

### Verification

```bash
# Verify latest image
cosign verify \
  --certificate-identity-regexp="https://github.com/alexbergh/secaudit-core" \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  ghcr.io/alexbergh/secaudit-core:latest

# Verify specific tag
cosign verify \
  --certificate-identity-regexp="https://github.com/alexbergh/secaudit-core" \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  ghcr.io/alexbergh/secaudit-core:v1.0.0
```

### Успешная верификация

```json
{
  "critical": {
    "identity": {
      "docker-reference": "ghcr.io/alexbergh/secaudit-core"
    },
    "image": {
      "docker-manifest-digest": "sha256:..."
    },
    "type": "cosign container image signature"
  },
  "optional": {
    "Bundle": {...},
    "Issuer": "https://token.actions.githubusercontent.com",
    "Subject": "https://github.com/alexbergh/secaudit-core/.github/workflows/docker-publish.yml@refs/heads/main"
  }
}
```

---

## Release Signing (GPG)

### Что подписывается

Для каждого релиза создаются подписи:
- `.whl` файлы (Python wheels)
- `.tar.gz` файлы (source distributions)
- `SHA256SUMS` - контрольные суммы
- `SHA512SUMS` - контрольные суммы

### Автоматическая подпись

Workflow `.github/workflows/release-signing.yml` автоматически:
- Строит distribution packages
- Подписывает все файлы GPG ключом
- Генерирует checksums
- Подписывает checksums
- Загружает в GitHub Release

### Verification

#### 1. Импорт публичного ключа

```bash
# From keyserver
gpg --keyserver keys.openpgp.org --recv-keys <KEY_ID>

# Or from file
curl -sL https://github.com/alexbergh/secaudit-core/releases/download/v1.0.0/public.key | gpg --import
```

#### 2. Verify signature

```bash
# Download files
wget https://github.com/alexbergh/secaudit-core/releases/download/v1.0.0/secaudit_plus-1.0.0-py3-none-any.whl
wget https://github.com/alexbergh/secaudit-core/releases/download/v1.0.0/secaudit_plus-1.0.0-py3-none-any.whl.asc

# Verify
gpg --verify secaudit_plus-1.0.0-py3-none-any.whl.asc secaudit_plus-1.0.0-py3-none-any.whl
```

#### 3. Verify checksums

```bash
# Download checksums
wget https://github.com/alexbergh/secaudit-core/releases/download/v1.0.0/SHA256SUMS.asc

# Verify signature
gpg --verify SHA256SUMS.asc

# Check integrity
sha256sum -c SHA256SUMS
```

---

## Setup Instructions

### For Maintainers

#### 1. Generate GPG Key

```bash
# Generate key
gpg --full-generate-key

# Choose:
# - RSA and RSA
# - 4096 bits
# - Key does not expire (or set expiration)
# - Real name: SecAudit+ Release Bot
# - Email: releases@secaudit.example.com
```

#### 2. Export Keys

```bash
# Export private key (keep secure!)
gpg --armor --export-secret-keys <KEY_ID> > private.key

# Export public key
gpg --armor --export <KEY_ID> > public.key

# Get key fingerprint
gpg --fingerprint <KEY_ID>
```

#### 3. Add to GitHub Secrets

В GitHub repository settings → Secrets and variables → Actions:

- `GPG_PRIVATE_KEY` - содержимое `private.key`
- `GPG_PASSPHRASE` - passphrase для ключа

#### 4. Publish Public Key

```bash
# Upload to keyserver
gpg --keyserver keys.openpgp.org --send-keys <KEY_ID>

# Or add to repository
cp public.key docs/GPG_PUBLIC_KEY.asc
git add docs/GPG_PUBLIC_KEY.asc
git commit -m "docs: add GPG public key"
```

### For Users

#### Install Cosign

```bash
# Linux
wget https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64
sudo mv cosign-linux-amd64 /usr/local/bin/cosign
sudo chmod +x /usr/local/bin/cosign

# macOS
brew install cosign

# Windows
choco install cosign
```

#### Install GPG

```bash
# Debian/Ubuntu
sudo apt-get install gnupg

# RHEL/CentOS
sudo yum install gnupg2

# macOS
brew install gnupg

# Windows
choco install gnupg
```

---

## Kubernetes Admission Control

### Verify images in Kubernetes

Используйте admission controller для автоматической верификации:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cosign-policy
  namespace: secaudit
data:
  policy.yaml: |
    apiVersion: policy.sigstore.dev/v1beta1
    kind: ClusterImagePolicy
    metadata:
      name: secaudit-images
    spec:
      images:
      - glob: "ghcr.io/alexbergh/secaudit-core**"
      authorities:
      - keyless:
          url: https://fulcio.sigstore.dev
          identities:
          - issuerRegExp: "https://token.actions.githubusercontent.com"
            subjectRegExp: "https://github.com/alexbergh/secaudit-core/.*"
```

### Policy Controller

```bash
# Install Sigstore Policy Controller
kubectl apply -f https://github.com/sigstore/policy-controller/releases/latest/download/release.yaml

# Apply policy
kubectl apply -f cosign-policy.yaml
```

---

## CI/CD Integration

### Verify before deployment

```yaml
# .github/workflows/deploy.yml
- name: Verify image signature
  run: |
    cosign verify \
      --certificate-identity-regexp="https://github.com/${{ github.repository }}" \
      --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
      ${{ env.IMAGE }}
```

### Verify in Dockerfile

```dockerfile
FROM ghcr.io/alexbergh/secaudit-core:latest

# Verify signature at build time
RUN cosign verify \
    --certificate-identity-regexp="https://github.com/alexbergh/secaudit-core" \
    --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
    ghcr.io/alexbergh/secaudit-core:latest
```

---

## Troubleshooting

### Cosign verification fails

**Problem**: `Error: no matching signatures`

**Solution**:
1. Проверьте, что образ был опубликован после внедрения Cosign
2. Убедитесь в правильности certificate-identity и issuer
3. Проверьте network connectivity к Rekor

### GPG verification fails

**Problem**: `gpg: Can't check signature: No public key`

**Solution**:
```bash
# Import key from keyserver
gpg --keyserver keys.openpgp.org --recv-keys <KEY_ID>

# Or import from file
gpg --import public.key
```

### Expired GPG key

**Problem**: `gpg: Note: This key has expired!`

**Solution**:
```bash
# Extend expiration
gpg --edit-key <KEY_ID>
> expire
> (select new expiration)
> save

# Re-export and update
gpg --armor --export <KEY_ID> > public.key
```

---

## Security Considerations

### Key Management

- **Private keys** хранятся только в GitHub Secrets
- **Rotation** - меняйте ключи ежегодно
- **Backup** - храните backup ключей в secure location
- **Access control** - ограничьте доступ к secrets

### Keyless Signing (Cosign)

**Преимущества**:
- Нет необходимости управлять ключами
- Автоматическая ротация
- Audit trail в Rekor

**Ограничения**:
- Требует доверия к Sigstore infrastructure
- Зависимость от GitHub OIDC

### Best Practices

1. **Always verify** перед использованием
2. **Pin digests** вместо tags в production
3. **Monitor** Rekor transparency log
4. **Automate** verification в CI/CD
5. **Document** процесс для пользователей

---

## References

- [Cosign Documentation](https://docs.sigstore.dev/cosign/overview/)
- [Sigstore](https://www.sigstore.dev/)
- [GPG Documentation](https://gnupg.org/documentation/)
- [GitHub OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)

---

**Последнее обновление**: 2025-01-28  
**Владелец**: Security Team
