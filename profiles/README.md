# Руководство по профилям проверки

Этот каталог содержит прикладные профили для движка **secaudit**. Чтобы повысить полноту
и качество проверок при подготовке к защите на комитете, рекомендуется придерживаться
следующих соглашений.

## Структура каталогов

```
profiles/
  base/
    linux.yml          # Базовые проверки для всех систем
    workstation.yml    # Настольные рабочие станции
    server.yml         # Серверные роли
  os/
    astra-1.7.yml      # Специфика Astra Linux 1.7
    alt-8sp.yml        # ALT 8 СП
    redos-7.3-8.yml    # Ред ОС 7.3/8
  roles/
    kiosk.yml          # Терминальные/киосковые решения
    db.yml             # Серверы БД
  szi/
    snlsp.yml          # Средства защиты информации (пример: Secret Net)
  include/
    allowlist_suid_sgid.txt
    allowlist_ports.txt
    vars_baseline.env
    vars_strict.env
```

*Каталоги `base/`, `os/`, `roles/`, `szi/` и `include/` пока необязательны, но рекомендуются к созданию при
расширении набора профилей.*

## Слои профилей и уровень строгости

- Базовые профили (`base/*.yml`) содержат минимально необходимый набор контролей.
- Ролевые профили (`roles/*.yml`) добавляют отраслевые или прикладные требования.
- Профили конкретных ОС (`os/*.yml`) переопределяют параметры под особенности дистрибутива.
- Уровень строгости задавайте переменной `SECAUDIT_LEVEL=baseline|strict|paranoid`. Пороговые
  значения (например, `FAILLOCK_DENY`) и списки allowlist/denylist читайте из `vars_*.env` через
  `include_vars`.

## Allowlist/Denylist

- Для проверок SUID/SGID, слушающих портов, cron/systemd-таймеров и прочих потенциально «шумных»
  артефактов используйте файлы allowlist в `profiles/include/`.
- В профиле используйте `assert_type: set_allowlist` и указывайте путь к файлу в `expect`, чтобы
  движок сравнивал фактическое множество значений с эталоном. Пустые строки и комментарии (`# ...`)
  игнорируются.

## Оформление правил

Каждое правило должно содержать:

- `id` — уникальный идентификатор в формате `<слой>_<подсистема>_<краткое-имя>`.
- `desc` или `name` — краткое описание, понятное аттестационной комиссии.
- `module` — одно из `system`, `integrity`, `network`, `packages`, `custom`.
- `tags` и `ref` — ссылки на нормативные документы (ФСТЭК, ГОСТ, CIS и т.д.).
- `remediation` — пошаговое описание устранения несоответствия, если оно обнаружено.

### Нормализация конфигураций

Перед сопоставлением значений нормализуйте вывод команд:

- удаляйте комментарии (`sed -E 's/#.*$//'`),
- схлопывайте пробелы (`awk '{$1=$1};1'`),
- агрегируйте значения из `*.d` каталогов.

Для сложных сервисов (SSH, journald, sysctl) фиксируйте итоговую конфигурацию (`sshd -T`,
`systemd-analyze cat-config`, `sysctl -a`) и проверяйте уже результат, а не отдельные файлы.

### Кеширование фактов

Чтобы сократить время выполнения профиля:

1. Собирайте долгие факты один раз (`sysctl -a`, `ss -tulpen`, `mount`, `systemctl list-unit-files`).
2. Переиспользуйте результаты в нескольких правилах через переменные профиля.
3. Устанавливайте таймауты для «тяжёлых» команд и обрабатывайте статус `UNDEF`, если команда
   завершилась по таймауту.

### Примеры правил

```yaml
- id: suid_sgid_scan
  desc: "SUID/SGID-бинарники соответствуют allowlist"
  module: "system"
  command: "find / -xdev \\( -perm -4000 -o -perm -2000 \\) -type f 2>/dev/null | sort"
  expect: "profiles/include/allowlist_suid_sgid.txt"
  assert_type: "set_allowlist"
  remediation: |
    Обновите эталонный список или удалите лишние биты SUID/SGID.
```

```yaml
- id: journald_persistent_and_rl
  desc: "journald: persistent + rate limit + forward"
  module: "system"
  command: "systemd-analyze cat-config systemd/journald.conf 2>/dev/null | awk -F= '/^(Storage|SystemMaxUse|RateLimitInterval|RateLimitBurst|ForwardToSyslog)=/{print $1"="$2}'"
  asserts:
    - regexp: "Storage=persistent"
    - regexp: "RateLimitInterval="
    - regexp: "RateLimitBurst="
  remediation: |
    Установите значения Storage=persistent, RateLimitInterval=30s, RateLimitBurst=1000 в /etc/systemd/journald.conf.
```

```yaml
- id: sshd_effective_rootlogin
  desc: "SSHD (итог): root-вход запрещён"
  module: "network"
  command: "sshd -T 2>/dev/null | awk '{$1=$1};1'"
  expect: "(?i)^permitrootlogin\\s+no$"
  assert_type: "regexp"
  remediation: |
    Установите `PermitRootLogin no` в /etc/ssh/sshd_config и перезагрузите сервис.
```

## Трассируемость и отчётность

- Используйте статусы `PASS/FAIL/WARN/UNDEF/SKIP` для тонкой градации.
- Добавляйте поле `evidence` в отчёт, чтобы сохранить небольшой фрагмент проверяемого файла
  (без чувствительных данных).
- Храните время выполнения каждой проверки, чтобы выявлять «тяжёлые» места.

## Интеграции

- Готовьте экспорт результатов в SARIF/JUnit для CI/CD.
- Поддерживайте формирование отчётов в HTML/Markdown с подсветкой remediation.

## Контакт

Вопросы по ведению профилей оформляйте через issues/PR в репозитории или в профильном чате.
