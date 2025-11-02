# Настройка SSH доступа для agentless аудита

## ⚠️ ВАЖНО: Безопасность превыше всего!

**НЕ используйте root для аудита!**

Используйте выделенного пользователя с минимальными правами:
- ✅ **Рекомендуется**: См. [SECURE_AUDIT_USER_SETUP.md](SECURE_AUDIT_USER_SETUP.md)
- ❌ **НЕ используйте**: root или admin

---

## 🎯 Обнаружены хосты

После сканирования сети 192.168.1.0/24 найдено:

| Хост | IP | ОС | SSH |
|------|-----|-----|-----|
| vm-host-1 | 192.168.1.60 | Linux (OpenSSH 7.4) | ✅ |
| vm-debian | 192.168.1.122 | Debian (OpenSSH 10.0) | ✅ |
| host-67 | 192.168.1.67 | Unknown | ✅ |

## 📋 Варианты настройки SSH

### ⭐ Рекомендуемый подход: Безопасный audit пользователь

**См. полную инструкцию**: [SECURE_AUDIT_USER_SETUP.md](SECURE_AUDIT_USER_SETUP.md)

Краткая версия:
1. Создайте пользователя `secaudituser` на каждой VM
2. Настройте минимальные sudo права (ТОЛЬКО чтение)
3. Настройте SSH ключи
4. Запретите root login

---

### Вариант 1: SSH ключи (для уже существующего пользователя)

#### На хост-машине (Windows):

```powershell
# 1. Генерация SSH ключа
ssh-keygen -t ed25519 -f ~/.ssh/secaudit_local_key -N ""

# 2. Копирование на VM (для каждого хоста)
# ⚠️ ИСПОЛЬЗУЙТЕ secaudituser, НЕ root!
ssh-copy-id -i ~/.ssh/secaudit_local_key.pub secaudituser@192.168.1.60
ssh-copy-id -i ~/.ssh/secaudit_local_key.pub secaudituser@192.168.1.122
ssh-copy-id -i ~/.ssh/secaudit_local_key.pub secaudituser@192.168.1.67

# 3. Проверка доступа
ssh -i ~/.ssh/secaudit_local_key secaudituser@192.168.1.60 "hostname"
ssh -i ~/.ssh/secaudit_local_key secaudituser@192.168.1.122 "hostname"
ssh -i ~/.ssh/secaudit_local_key secaudituser@192.168.1.67 "hostname"
```

#### Обновите инвентори:

```yaml
groups:
  linux_servers:
    vars:
      ssh_user: secaudituser  # НЕ root!
      ssh_key: ~/.ssh/secaudit_local_key
```

### Вариант 2: Password authentication (Для тестирования)

#### На каждой VM:

```bash
# Разрешите password authentication
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Перезапустите SSH
sudo systemctl restart sshd

# Установите пароль для root (если нужно)
sudo passwd root
```

#### Установите sshpass на Windows:

К сожалению, `sshpass` не доступен нативно на Windows. Используйте WSL или SSH ключи.

#### Альтернатива для Windows - используйте PowerShell с ключами:

```powershell
# Используйте встроенный SSH клиент Windows с ключами
```

### Вариант 3: Создание audit пользователя (Production)

#### На каждой VM:

```bash
# 1. Создание пользователя
sudo useradd -m -s /bin/bash audituser
sudo passwd audituser  # Установите пароль

# 2. Добавление в sudoers
sudo tee /etc/sudoers.d/audituser << EOF
audituser ALL=(ALL) NOPASSWD: /usr/bin/systemctl status *
audituser ALL=(ALL) NOPASSWD: /usr/bin/cat /etc/*
audituser ALL=(ALL) NOPASSWD: /usr/sbin/iptables -L
audituser ALL=(ALL) NOPASSWD: /usr/bin/find /etc -type f -perm /022
audituser ALL=(ALL) NOPASSWD: /bin/ps aux
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/netstat -tulpn
EOF

sudo chmod 0440 /etc/sudoers.d/secaudituser

# 3. Копирование SSH ключа
mkdir -p ~/.ssh
chmod 700 ~/.ssh
# Скопируйте публичный ключ в ~/.ssh/authorized_keys
```

#### Обновите инвентори:

```yaml
groups:
  linux_servers:
    vars:
      ssh_user: audituser
      ssh_key: ~/.ssh/secaudit_local_key
```

## 🚀 Быстрый старт после настройки

### Если используете SSH ключи:

```bash
# 1. Проверьте доступ
ssh -i ~/.ssh/secaudit_local_key root@192.168.1.60 "echo test"

# 2. Запустите agentless аудит
secaudit audit-agentless \
  --inventory local_network_inventory.yml \
  --profile profiles/common/baseline.yml \
  --output-dir results/agentless_local \
  --level baseline
```

### Если пользователь имеет пароль:

На Windows это сложнее. Рекомендуется использовать WSL:

```bash
# В WSL
sudo apt-get install sshpass

# Добавьте пароль в инвентори (НЕ безопасно для production!)
# В local_network_inventory.yml:
groups:
  linux_servers:
    vars:
      ssh_user: root
      ssh_password: "your_password_here"
```

## 📊 Пример успешного аудита

После настройки SSH вы должны увидеть:

```
============================================================
СВОДКА AGENTLESS АУДИТА
============================================================
Всего хостов: 3
Успешно: 3
С ошибками: 0
Средний security score: 78.5/100
============================================================

Результаты по хостам:
Хост              Score      Pass/Fail/Undef      Status    
--------------------------------------------------------------
vm-host-1         76.2/100   28/8/1               ✓ OK      
vm-debian         82.4/100   31/6/0               ✓ OK      
host-67           76.9/100   29/7/1               ✓ OK      

Отчёты сохранены в: results/agentless_local
============================================================
```

## 🐛 Устранение неполадок

### Ошибка: SSH подключение недоступно

```bash
# Проверьте доступность хоста
ping 192.168.1.60

# Проверьте SSH порт
nc -zv 192.168.1.60 22

# Проверьте SSH вручную
ssh root@192.168.1.60

# Проверьте SSH ключ
ssh -i ~/.ssh/secaudit_local_key -v root@192.168.1.60
```

### Ошибка: Permission denied

```bash
# Проверьте права на ключ
chmod 600 ~/.ssh/secaudit_local_key

# Проверьте authorized_keys на VM
ssh root@192.168.1.60 "cat ~/.ssh/authorized_keys"
chmod 600 ~/.ssh/authorized_keys  # на VM
```

### Ошибка: Connection timeout

```bash
# Проверьте firewall на VM
sudo ufw status
sudo ufw allow 22/tcp

# Проверьте SSH daemon
sudo systemctl status sshd
sudo systemctl start sshd
```

## 📝 Следующие шаги

1. **Настройте SSH ключи** для всех хостов
2. **Проверьте подключение** вручную
3. **Запустите agentless аудит** снова
4. **Проверьте отчёты** в `results/agentless_local/`
5. **Настройте регулярные аудиты** через cron/Task Scheduler

## 🎉 Готово!

После настройки SSH доступа agentless аудит будет работать полностью автоматически:

```bash
# Полный цикл:
# 1. Сканирование
secaudit scan --networks 192.168.1.0/24 -o scan.json

# 2. Создание инвентори
secaudit inventory create --from-scan scan.json -o inventory.yml

# 3. Agentless аудит
secaudit audit-agentless \
  --inventory inventory.yml \
  --profile profiles/common/baseline.yml \
  --output-dir ./reports
```
