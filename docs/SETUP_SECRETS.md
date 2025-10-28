# Setup GitHub Secrets для Code Signing

## Требуемые Secrets

Для работы code signing workflows необходимо добавить следующие secrets в GitHub repository:

### GPG Signing Secrets

| Secret Name | Description | Required For |
|-------------|-------------|--------------|
| `GPG_PRIVATE_KEY` | Приватный GPG ключ в ASCII armor формате | Release signing |
| `GPG_PASSPHRASE` | Passphrase для GPG ключа | Release signing |

## Инструкция по настройке

### 1. Генерация GPG ключа

```bash
# Генерация нового ключа
gpg --full-generate-key

# Параметры:
# - Тип: RSA and RSA
# - Размер: 4096 bits
# - Expiration: 1 year (рекомендуется)
# - Name: SecAudit+ Release Bot
# - Email: releases@secaudit.example.com
# - Passphrase: (создайте надежный пароль)
```

### 2. Экспорт ключей

```bash
# Получить KEY_ID
gpg --list-secret-keys --keyid-format=long

# Экспорт приватного ключа
gpg --armor --export-secret-keys <KEY_ID> > private.key

# Экспорт публичного ключа
gpg --armor --export <KEY_ID> > public.key
```

### 3. Добавление secrets в GitHub

1. Перейдите в Settings → Secrets and variables → Actions
2. Нажмите "New repository secret"
3. Добавьте secrets:

**GPG_PRIVATE_KEY**:
```
Скопируйте содержимое файла private.key полностью, включая:
-----BEGIN PGP PRIVATE KEY BLOCK-----
...
-----END PGP PRIVATE KEY BLOCK-----
```

**GPG_PASSPHRASE**:
```
Введите passphrase, который вы использовали при создании ключа
```

### 4. Публикация публичного ключа

```bash
# Загрузка на keyserver
gpg --keyserver keys.openpgp.org --send-keys <KEY_ID>

# Добавление в репозиторий
cp public.key docs/GPG_PUBLIC_KEY.asc
git add docs/GPG_PUBLIC_KEY.asc
git commit -m "docs: add GPG public key for release verification"
git push
```

### 5. Проверка настройки

После добавления secrets, создайте тестовый release:

```bash
git tag v1.0.0-test
git push origin v1.0.0-test
```

Workflow `.github/workflows/release-signing.yml` должен:
- ✅ Успешно импортировать GPG ключ
- ✅ Подписать все артефакты
- ✅ Загрузить подписи в release

## Безопасность

### Хранение приватного ключа

- ❌ **НЕ** коммитьте `private.key` в репозиторий
- ✅ Храните backup в secure location (password manager, encrypted storage)
- ✅ Используйте надежный passphrase
- ✅ Ограничьте доступ к GitHub secrets

### Ротация ключей

Рекомендуется менять GPG ключи ежегодно:

1. Сгенерируйте новый ключ
2. Обновите secrets в GitHub
3. Опубликуйте новый публичный ключ
4. Отзовите старый ключ (если необходимо)

```bash
# Отзыв старого ключа
gpg --gen-revoke <OLD_KEY_ID> > revoke.asc
gpg --import revoke.asc
gpg --keyserver keys.openpgp.org --send-keys <OLD_KEY_ID>
```

## Troubleshooting

### Workflow fails: "gpg: decryption failed: No secret key"

**Причина**: Неправильно скопирован приватный ключ

**Решение**:
1. Убедитесь, что скопировали весь ключ включая header/footer
2. Проверьте отсутствие лишних пробелов/переносов строк
3. Пересоздайте secret

### Workflow fails: "gpg: signing failed: Inappropriate ioctl for device"

**Причина**: Проблема с passphrase

**Решение**: Используйте `--pinentry-mode loopback` (уже добавлено в workflow)

### Verification fails: "gpg: Can't check signature: No public key"

**Причина**: Публичный ключ не опубликован

**Решение**:
```bash
gpg --keyserver keys.openpgp.org --send-keys <KEY_ID>
```

## Дополнительная информация

См. [CODE_SIGNING.md](CODE_SIGNING.md) для полной документации по code signing.
