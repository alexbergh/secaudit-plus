# Создание безопасного audit пользователя

## ⚠️ Важно: НЕ используйте root!

Использование root для аудита - **серьёзная угроза безопасности**:
- ❌ Полный доступ ко всей системе
- ❌ Возможность повреждения системы
- ❌ Нарушение принципа наименьших привилегий
- ❌ Сложно отследить действия

## ✅ Правильный подход: выделенный пользователь

Создайте пользователя `secaudituser` с **минимальными необходимыми правами**.

---

## 📋 Инструкция для каждой VM

### Шаг 1: Создание пользователя

На **каждой** целевой VM (192.168.1.60, 192.168.1.122, 192.168.1.67):

```bash
# Подключитесь как root или через sudo
ssh root@192.168.1.60

# Создайте пользователя
sudo useradd -m -s /bin/bash secaudituser

# Установите пароль (временно, для первого подключения)
sudo passwd secaudituser
# Введите: SecAudit2025! (или ваш пароль)

# Проверка
id secaudituser
```

### Шаг 2: Настройка минимальных sudo прав

Создайте файл с **строго ограниченными** правами:

```bash
sudo tee /etc/sudoers.d/secaudituser << 'EOF'
# SecAudit пользователь - ТОЛЬКО для чтения конфигураций
# НЕ давайте права на изменение системы!

# Чтение системных файлов
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/cat /etc/*
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/cat /proc/*
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/cat /sys/*

# Статус сервисов (только просмотр)
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/systemctl status *
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-enabled *
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active *
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/systemctl list-units *

# Просмотр процессов
secaudituser ALL=(ALL) NOPASSWD: /bin/ps aux
secaudituser ALL=(ALL) NOPASSWD: /bin/ps -ef

# Сетевые подключения (только просмотр)
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/netstat -tulpn
secaudituser ALL=(ALL) NOPASSWD: /bin/ss -tulpn
secaudituser ALL=(ALL) NOPASSWD: /usr/sbin/iptables -L
secaudituser ALL=(ALL) NOPASSWD: /usr/sbin/iptables -S
secaudituser ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables -L

# Поиск файлов (безопасный)
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/find /etc -type f -perm /022
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/find /etc -type f -perm /002

# Просмотр пакетов
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/dpkg -l
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/apt list --installed
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/rpm -qa
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/yum list installed

# Логи (только чтение)
secaudituser ALL=(ALL) NOPASSWD: /usr/bin/journalctl *

# ЗАПРЕЩЕНО всё остальное - НЕ добавляйте команды изменения системы!
# НЕ добавляйте: systemctl start/stop/restart, apt install, rm, chmod, chown и т.д.
EOF

# Установите правильные права
sudo chmod 0440 /etc/sudoers.d/secaudituser

# Проверьте синтаксис
sudo visudo -c
```

### Шаг 3: Настройка SSH для secaudituser

#### На вашей хост-машине (Windows):

```powershell
# 1. Генерация SSH ключа (если ещё не создан)
ssh-keygen -t ed25519 -f ~/.ssh/secaudit_key -N "" -C "secaudit@local"

# 2. Просмотр публичного ключа
cat ~/.ssh/secaudit_key.pub
# Скопируйте вывод
```

#### На каждой VM:

```bash
# Переключитесь на secaudituser
sudo su - secaudituser

# Создайте директорию SSH
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Создайте authorized_keys
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Добавьте публичный ключ (вставьте скопированный ключ)
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... secaudit@local" >> ~/.ssh/authorized_keys

# Проверьте
cat ~/.ssh/authorized_keys
```

Или автоматически с хост-машины:

```powershell
# Используйте ssh-copy-id (если доступен)
ssh-copy-id -i ~/.ssh/secaudit_key.pub secaudituser@192.168.1.60
ssh-copy-id -i ~/.ssh/secaudit_key.pub secaudituser@192.168.1.122
ssh-copy-id -i ~/.ssh/secaudit_key.pub secaudituser@192.168.1.67
```

### Шаг 4: Тестирование доступа

```powershell
# Проверьте SSH подключение
ssh -i ~/.ssh/secaudit_key secaudituser@192.168.1.60 "echo 'Connection OK'"

# Проверьте sudo права (должны работать БЕЗ пароля)
ssh -i ~/.ssh/secaudit_key secaudituser@192.168.1.60 "sudo systemctl status sshd"

# Проверьте чтение /etc
ssh -i ~/.ssh/secaudit_key secaudituser@192.168.1.60 "sudo cat /etc/passwd | wc -l"

# Проверьте, что НЕТ прав на опасные действия (должна быть ошибка)
ssh -i ~/.ssh/secaudit_key secaudituser@192.168.1.60 "sudo systemctl restart sshd"
# Должно быть: "Sorry, user secaudituser is not allowed to execute..."
```

### Шаг 5: Запрет root через SSH (рекомендуется)

После настройки secaudituser, запретите root логин:

```bash
# На каждой VM
sudo sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# Проверьте
sudo grep PermitRootLogin /etc/ssh/sshd_config

# Перезапустите SSH
sudo systemctl restart sshd
```

---

## 🚀 Запуск agentless аудита

После настройки всех VM:

```bash
# Проверьте инвентори
cat local_network_inventory.yml
# Должно быть: ssh_user: secaudituser

# Запустите agentless аудит
secaudit audit-agentless \
  --inventory local_network_inventory.yml \
  --profile profiles/common/baseline.yml \
  --output-dir results/agentless_secure \
  --level baseline
```

Ожидаемый результат:

```
============================================================
СВОДКА AGENTLESS АУДИТА
============================================================
Всего хостов: 3
Успешно: 3
С ошибками: 0
Средний security score: 78.5/100
============================================================
```

---

## 🔒 Дополнительные меры безопасности

### 1. Ограничение по IP

На VM разрешите SSH только с хост-машины:

```bash
# Узнайте IP хост-машины
# Например: 192.168.1.100

# Настройте firewall
sudo ufw allow from 192.168.1.100 to any port 22
sudo ufw deny 22
sudo ufw enable
```

### 2. Ограничение по времени

Разрешите secaudituser логин только в определённое время:

```bash
# Установите pam_time
sudo apt-get install libpam-modules

# Настройте /etc/security/time.conf
echo "sshd;*;secaudituser;MoTuWeThFr0800-1800" | sudo tee -a /etc/security/time.conf
```

### 3. Логирование действий

Включите детальное логирование:

```bash
# Настройте auditd для secaudituser
sudo apt-get install auditd

# Создайте правило
sudo tee /etc/audit/rules.d/secaudituser.rules << 'EOF'
# Логировать все команды secaudituser
-a always,exit -F arch=b64 -S execve -F uid=secaudituser -k secaudit_commands
-a always,exit -F arch=b32 -S execve -F uid=secaudituser -k secaudit_commands
EOF

# Перезапустите auditd
sudo systemctl restart auditd

# Просмотр логов
sudo ausearch -k secaudit_commands
```

### 4. Ротация SSH ключей

Меняйте SSH ключи регулярно:

```bash
# Каждые 90 дней
ssh-keygen -t ed25519 -f ~/.ssh/secaudit_key_$(date +%Y%m%d) -N ""
# Распространите новый ключ
# Удалите старый ключ через неделю
```

---

## 📋 Чеклист безопасности

### На целевых VM:

- [x] Создан пользователь `secaudituser`
- [x] Настроены минимальные sudo права (ТОЛЬКО чтение)
- [x] Настроен SSH доступ по ключу
- [x] Отключён password authentication для secaudituser
- [x] Запрещён root login через SSH
- [x] Включено логирование auditd
- [ ] Настроен firewall (опционально)
- [ ] Настроено ограничение по времени (опционально)

### На хост-машине:

- [x] Создан SSH ключ `~/.ssh/secaudit_key`
- [x] Публичный ключ скопирован на все VM
- [x] Обновлён инвентори (ssh_user: secaudituser)
- [x] Права на ключ: `chmod 600 ~/.ssh/secaudit_key`

---

## 🐛 Устранение неполадок

### Ошибка: Permission denied

```bash
# Проверьте права на файлы
ssh secaudituser@192.168.1.60 "ls -la ~/.ssh/"
# authorized_keys должен быть 600
# .ssh должен быть 700

# Исправьте если нужно
ssh secaudituser@192.168.1.60 "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

### Ошибка: sudo требует пароль

```bash
# Проверьте sudoers
ssh secaudituser@192.168.1.60 "sudo -l"

# Проверьте права файла
ssh secaudituser@192.168.1.60 "sudo ls -la /etc/sudoers.d/secaudituser"
# Должно быть: -r--r----- 0440

# Проверьте синтаксис
sudo visudo -c -f /etc/sudoers.d/secaudituser
```

### Ошибка: Command not permitted

```bash
# Команда не разрешена в sudoers
# Добавьте нужную команду в /etc/sudoers.d/secaudituser
# НО: убедитесь что она безопасна (только чтение)!

# Пример: добавить просмотр логов
echo "secaudituser ALL=(ALL) NOPASSWD: /usr/bin/tail -f /var/log/syslog" | \
  sudo tee -a /etc/sudoers.d/secaudituser
```

---

## 📊 Сравнение: root vs secaudituser

| Аспект | root ❌ | secaudituser ✅ |
|--------|---------|-----------------|
| Права | Полные | Минимальные (только чтение) |
| Риск | Критический | Минимальный |
| Аудит | Сложно отследить | Легко логировать |
| Compliance | Нарушение | Соответствие |
| Восстановление | Сложное | Простое |
| Best Practice | НЕТ | ДА |

---

## ✅ Готово!

После выполнения всех шагов у вас будет:

✅ Безопасный audit пользователь с минимальными правами  
✅ SSH доступ по ключам (без паролей)  
✅ Запрещён root login  
✅ Включено логирование действий  
✅ Соответствие best practices безопасности  

**Теперь можно безопасно запускать agentless аудит!**

```bash
secaudit audit-agentless \
  --inventory local_network_inventory.yml \
  --profile profiles/common/baseline.yml \
  --level paranoid
```

---

## 📚 Ссылки

- [CIS Benchmark - User Accounts](https://www.cisecurity.org/)
- [NIST 800-53 - Least Privilege](https://csrc.nist.gov/)
- [SSH Hardening Guide](https://www.ssh.com/academy/ssh/hardening)
