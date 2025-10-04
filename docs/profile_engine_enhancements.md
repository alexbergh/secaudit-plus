# План расширения проверок и улучшений движка

Документ дополняет текущие профили `profiles/*.yml` и описывает, какие новые проверки и
функциональность движка помогут сделать результаты аудита богаче, устойчивее к ложным срабатываниям.


## 1. Расширение покрытия проверок

### 1.1 Учётные записи и аутентификация

- Контроль заблокированных системных аккаунтов (`UID < 1000` → shell `nologin/false`).
  ```bash
  awk -F: '($3<1000 && $7!="/usr/sbin/nologin" && $7!="/bin/false"){print $1":"$7}' /etc/passwd
  ```
- Выявление пустых/отключённых паролей и просрочки через `/etc/shadow` и `chage -l`.
  ```bash
  awk -F: '($2=="!"||$2=="*"||$2==""){print $1}' /etc/shadow
  chage -l root
  ```
  Повторите `chage -l` для сервисных учётных записей.
  ```bash
  awk -F: '($3>=100 && $3<1000){print $1}' /etc/passwd | xargs -r -I{} sh -c 'echo "[{}]"; chage -l {}'
  ```
- Базлайн sudoers: запрет `NOPASSWD`, `requiretty` (при необходимости), включённый аудит
  (`Defaults log_output mail_badpass`).
  ```bash
  visudo -c
  grep -R "NOPASSWD" /etc/sudoers*
  ```

### 1.2 Журналы, аудит, время

- Настройки journald: `Storage=persistent`, лимиты, rate-limiting, форвардинг.
  ```bash
  grep -E '^(Storage|SystemMaxUse|RateLimitInterval|RateLimitBurst|ForwardToSyslog)=' /etc/systemd/journald.conf
  ```
- Аудит высокорисковых действий: изменение времени, загрузчик, модули ядра, `sudo/su/passwd`.
  Проверьте наличие правил вроде `-w /etc/shadow -p wa -k auth` и системных вызовов `adjtimex`,
  `settimeofday`, `init_module`, `delete_module` в профиле auditd.
- Проверка службы синхронизации времени (`chronyd`/`ntpd`), политика NTP, `makestep`.
  ```bash
  chronyc sources -v
  systemctl is-active chronyd || systemctl is-active ntpd
  ```

### 1.3 Ядро и модули

- Денай-листы модулей (Wi-Fi, Bluetooth, камера, звук) и файловых систем (`cramfs`, `freevxfs`, `squashfs`, `udf`).
  ```bash
  grep -E '^blacklist (ath9k|btusb|uvcvideo|snd_hda_intel)' /etc/modprobe.d/*.conf
  ```
- Дополнительные `sysctl`: `kernel.kptr_restrict`, `kernel.unprivileged_bpf_disabled`, `net.ipv4.tcp_syncookies`,
  `net.ipv6.conf.all.disable_ipv6` (если IPv6 не используется).
- Опциональный `kernel.modules_disabled=1` после инициализации.

### 1.4 Диски, загрузка, шифрование

- Secure Boot (`mokutil --sb-state`), контроль параметров ядра (`/proc/cmdline`).
  ```bash
  mokutil --sb-state
  grep -E '(^| )((selinux|apparmor|audit)=0|init=/bin/bash)' /proc/cmdline
  ```
- Анализ конфигурации LUKS: шифрованные разделы, непустые keyslots, надёжный PBKDF.
  ```bash
  lsblk -o NAME,TYPE,FSTYPE
  cryptsetup luksDump /dev/mapper/<volume>
  ```
  Убедитесь, что ключевые слоты (`Keyslot`) активны, а `PBKDF` установлен на `argon2id`/`pbkdf2` с достаточными
  `Iterations`, и нет отключённых или пустых слотов, требующих закрытия.

### 1.5 Файловые права и временные каталоги

- Сканирование SUID/SGID с проверкой по allowlist.
  ```bash
  find / -xdev \( -perm -4000 -o -perm -2000 \) -type f -printf '%p %m\n'
  ```
- Каталоги с мировой записью без `sticky` бита.
  ```bash
  find / -xdev -type d -perm -0002 ! -perm -1000 -print
  ```
- Опции монтирования `nodev/nosuid/noexec` для `/tmp`, `/var/tmp`, `/home`.
  ```bash
  mount | grep -E ' /(tmp|var/tmp|home) '
  ```

### 1.6 Сеть и службы

- Управление IPv6 (жёсткая настройка или отключение) и проверка фильтров (ip6tables/nftables).
  ```bash
  sysctl net.ipv6.conf.all.disable_ipv6
  ip6tables -L -n || nft list table ip6 filter
  ```
- Инвентаризация слушающих портов против allowlist.
  ```bash
  ss -tulpen
  ```
- Контроль вспомогательных служб (CUPS, Avahi, SSH-agent, XDMCP), `fail2ban` и SSH.
  ```bash
  systemctl list-unit-files | grep -E 'cups|avahi|xdmcp'
  systemctl is-enabled fail2ban
  systemctl is-enabled sshd
  fail2ban-client status 2>/dev/null
  ```

### 1.7 Пакеты, репозитории, обновления

- Проверка подписей репозиториев (`gpgcheck=1`, `Signed-By`).
  ```bash
  grep -R "gpgcheck=0" /etc/yum.repos.d
  grep -R "Signed-By" /etc/apt/sources.list* /etc/apt/sources.list.d
  ```
- Контроль минимально допустимых версий ядра и критичных пакетов.
- Верификация целостности пакетов (`rpm -Va`/`dpkg -V`).

### 1.8 Рабочие станции и GUI

- Запрет автологина, скрытие списка пользователей.
  ```bash
  grep -E '^(AutomaticLogin|TimedLogin)Enable' /etc/gdm/custom.conf
  grep -E '^(IncludeAll|EnableManualLogin|greeter-hide-users|greeter-show-manual-login)' /etc/lightdm/lightdm.conf
  ```
  Для GDM требуется `AutomaticLoginEnable=false`, `TimedLoginEnable=false` и `IncludeAll=false` (список пользователей скрыт).
  Для LightDM ожидайте `greeter-hide-users=true` и `greeter-show-manual-login=true`.
- Политики браузеров (policies.json, WebUSB/WebBluetooth, прокси, DoH).

### 1.9 Контейнеры/виртуализация

- Конфигурация Docker/Podman (нет `--privileged`, ограниченные capabilities, iptables/nft).
  ```bash
  ps aux | grep dockerd
  grep -R '"iptables":' /etc/docker/daemon.json
  docker info --format '{{json .SecurityOptions}}'
  docker inspect --format '{{.Name}} {{.HostConfig.Privileged}} {{.HostConfig.CapAdd}} {{.Config.Image}}' $(docker ps -q)
  docker image ls --format '{{.Repository}}:{{.Tag}}' | grep ':latest'
  ```
  Проверяйте, что `iptables`/`nftables` не отключены, контейнеры не запускаются в `Privileged`, не добавляют
  лишних capabilities, а образы не используют плавающие теги `:latest` и подписаны согласно политике.
- Контроль libvirt/KVM: аудит файлов ВМ, ограничения к сокетам, профили AppArmor/SELinux.

### 1.10 Secret Net LSP

- Расширенный опрос статуса служб, политик устройств, ZPS, firewall, аудита событий,
  сроков лицензии и проверка, что параметры не пустые.

## 2. Улучшения профилей

### 2.1 Ролевые и уровневые профили

- Разделение на роли (`base-linux`, `workstation`, `server`, `kiosk`, `db`, `szi-snlsp`).
- Параметризация строгости: `baseline/strict/paranoid` с переменными окружения и `include_vars`.
- Условия по ОС (`ID`, `VERSION_ID` из `/etc/os-release`) внутри одного YAML.

### 2.2 Allowlist/Denylist и исключения

- Файлы `profiles/include/*.txt` для SUID/портов/cron.
- Механизм локальных исключений без перевода проверки в статус FAIL.

### 2.3 Снижение ложных срабатываний

- Нормализация конфигов перед анализом, исключение комментариев.
- Проверка итоговой конфигурации сервисов (`sshd -T`, `systemctl show`, `sysctl -n`).
- Поддержка нескольких `assert` в одном правиле и логическое объединение.

### 2.4 Производительность

- Кеширование дорогих фактов (`sysctl -a`, `systemctl is-active`, `ss -tulpen`).
- Параллельный запуск правил пулами с таймаутами и мягким завершением (`UNDEF`).
- Метрики времени/CPU для каждого правила в отчёте.

### 2.5 Отчётность

- Поля `ref` и `tags` с указанием нормативных документов.
- `PASS/FAIL/WARN/UNDEF/SKIP` + веса для итогового скоринга.
- Сохранение артефактов (вырезки конфигов) с маскированием секретов.
- Экспорт в SARIF/JUnit и генерация remediation-гайдов.

## 3. Изменения в движке

### 3.1 Новый функционал

- Поддержка `custom_allowlist_file` и сравнение множеств.
- Автоматическое чтение `vars_*.env`, CLI-переключение уровней строгости.
- Универсальные агрегаторы вывода (нормализация пробелов, фильтрация комментариев).

### 3.2 UX и стабильность

- Кеш фактов между правилами, разгрузка повторных вызовов команд.
- Асинхронное выполнение с ограничением ресурсов, аккуратная обработка таймаутов.
- Логирование артефактов и объяснение FAIL/WARN прямо в отчёте.

### 3.3 Интеграция с CI/CD

- Формирование отчётов в SARIF/JUnit, публикация в GitHub/GitLab CI.
- Примеры GitHub Actions/CI сценариев в `workflows/` для проверки golden-образов.

## 4. Приоритетные следующие шаги

1. **Создать allowlist-инфраструктуру** (`profiles/include`, поддержка в движке).
2. **Добавить проверки по аутентификации, journald и SUID/SGID** в базовый профиль.
3. **Реализовать уровни строгости** и параметризацию порогов через переменные.
4. **Внедрить кеш фактов и артефакты доказательств** в отчётах.
5. **Подготовить экспорт SARIF/JUnit** и пример GitHub Actions для регрессионного анализа.

Документ может служить чек-листом при постановке задач в issue tracker и планировании
релизов.
