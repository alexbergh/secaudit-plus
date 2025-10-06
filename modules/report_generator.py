# modules/report_generator.py
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, date
from pathlib import Path
import json
import platform
import socket
from collections import defaultdict
from collections.abc import Mapping, Sequence


FSTEK21_DESCRIPTIONS = {
    "ИАФ.1": "Идентификация/аутентификация работников",
    "ИАФ.2": "Идентификация/аутентификация устройств",
    "ИАФ.3": "Управление идентификаторами",
    "ИАФ.4": "Управление средствами аутентификации",
    "ИАФ.5": "Защита обратной связи при вводе",
    "ИАФ.6": "ИА внешних пользователей",

    "УПД.1": "Управление учётными записями",
    "УПД.2": "Разграничение доступа",
    "УПД.3": "Управление инфопотоками",
    "УПД.4": "Разделение ролей",
    "УПД.5": "Минимальные привилегии",
    "УПД.6": "Ограничение неуспешных входов",
    "УПД.7": "Баннер безопасности",
    "УПД.8": "Оповещение о предыдущем входе",
    "УПД.9": "Лимит параллельных сессий",
    "УПД.10": "Таймаут сессии",
    "УПД.11": "Права до аутентификации",
    "УПД.12": "Атрибуты безопасности",
    "УПД.13": "Защищённый удалённый доступ",
    "УПД.14": "Контроль Wi-Fi",
    "УПД.15": "Контроль мобильных ТС",
    "УПД.16": "Внешние ИС",
    "УПД.17": "Доверенная загрузка",

    "ОПС.1": "Управление запуском ПО",
    "ОПС.2": "Управление установкой ПО",
    "ОПС.3": "Только разрешённое ПО",
    "ОПС.4": "Управление временными файлами",

    "ЗНИ.1": "Учёт носителей ПДн",
    "ЗНИ.2": "Доступ к носителям ПДн",
    "ЗНИ.3": "Контроль перемещения носителей",
    "ЗНИ.4": "Исключить НСД к ПДн на носителях",
    "ЗНИ.5": "Контроль интерфейсов ввода/вывода",
    "ЗНИ.6": "Контроль ввода/вывода",
    "ЗНИ.7": "Контроль подключения носителей",
    "ЗНИ.8": "Уничтожение/обезличивание ПДн",

    "РСБ.1": "События и сроки хранения",
    "РСБ.2": "Состав записей",
    "РСБ.3": "Сбор/запись/хранение",
    "РСБ.4": "Сбои регистрации",
    "РСБ.5": "Мониторинг журналов",
    "РСБ.6": "Синхронизация времени",
    "РСБ.7": "Защита информации о событиях",

    "АВЗ.1": "Антивирусная защита",
    "АВЗ.2": "Обновление сигнатур",

    "СОВ.1": "Обнаружение вторжений",
    "СОВ.2": "Обновление правил",

    "АНЗ.1": "Управление уязвимостями",
    "АНЗ.2": "Контроль обновлений",
    "АНЗ.3": "Контроль СЗИ/настроек",
    "АНЗ.4": "Контроль состава ТС/ПО/СЗИ",
    "АНЗ.5": "Контроль паролей/аккаунтов/ролей",

    "ОЦЛ.1": "Целостность ПО",
    "ОЦЛ.2": "Целостность ПДн в БД",
    "ОЦЛ.3": "Восстановление ПО",
    "ОЦЛ.4": "Защита от спама",
    "ОЦЛ.5": "Контроль исходящего контента",
    "ОЦЛ.6": "Ограничение прав ввода",
    "ОЦЛ.7": "Точность вводимых данных",
    "ОЦЛ.8": "Предупреждение об ошибках",

    "ОДТ.1": "Отказоустойчивые ТС",
    "ОДТ.2": "Резервирование",
    "ОДТ.3": "Контроль безотказности",
    "ОДТ.4": "Бэкап ПДн",
    "ОДТ.5": "Восстановление ПДн",

    "ЗСВ.1": "ИАФ в ВИ",
    "ЗСВ.2": "Доступ в ВИ",
    "ЗСВ.3": "Журналы в ВИ",
    "ЗСВ.4": "Потоки/периметр ВИ",
    "ЗСВ.5": "Доверенная загрузка в ВИ",
    "ЗСВ.6": "Миграция ВМ/контейнеров",
    "ЗСВ.7": "Целостность ВИ/конфигураций",
    "ЗСВ.8": "Резерв в ВИ",
    "ЗСВ.9": "Антивирус в ВИ",
    "ЗСВ.10": "Сегментирование ВИ",

    "ЗТС.1": "Утечки по ТКУ",
    "ЗТС.2": "Контролируемая зона",
    "ЗТС.3": "Физический доступ",
    "ЗТС.4": "Размещение дисплеев",
    "ЗТС.5": "Внешние воздействия",

    "ЗИС.1": "Разделение функций",
    "ЗИС.2": "Приоритетные процессы",
    "ЗИС.3": "Защита ПДн при передаче",
    "ЗИС.4": "Доверенные каналы/маршруты",
    "ЗИС.5": "Запрет удалённой периферии",
    "ЗИС.6": "Атрибуты безопасности при обмене",
    "ЗИС.7": "Мобильный код",
    "ЗИС.8": "Передача речи",
    "ЗИС.9": "Видеоинформация",
    "ЗИС.10": "Происхождение имён/адресов",
    "ЗИС.11": "Подлинность соединений",
    "ЗИС.12": "Неотрекаемость отправки",
    "ЗИС.13": "Неотрекаемость получения",
    "ЗИС.14": "Терминальный доступ",
    "ЗИС.15": "Защита архивов/настроек",
    "ЗИС.16": "Скрытые каналы",
    "ЗИС.17": "Сегментирование ИС",
    "ЗИС.18": "Чтение-только носители + целостность",
    "ЗИС.19": "Изоляция процессов",
    "ЗИС.20": "Защита беспроводных соединений",
}


def _normalize_fstek_code(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\u00a0", "").replace(" ", "")
    text = text.upper()
    for token in ("ФСТЭК", "FSTEK", "МЕРА", "MEASURE"):
        text = text.replace(token, "")
    text = text.replace("№", "")
    for ch in ("-", "_", ",", ";", ":"):
        text = text.replace(ch, ".")
    text = text.strip(".")
    if not text:
        return None
    if "." not in text:
        for idx, char in enumerate(text):
            if char.isdigit():
                text = f"{text[:idx]}.{text[idx:]}"
                break
    while ".." in text:
        text = text.replace("..", ".")
    text = text.strip(".")
    return text or None


def _extract_fstek_codes(result):
    tags = None
    if isinstance(result, Mapping):
        tags = result.get("tags")
    else:
        tags = getattr(result, "tags", None)

    if not isinstance(tags, Mapping):
        return []

    raw = tags.get("fstec")
    if raw is None:
        return []

    if isinstance(raw, (str, bytes)):
        values = [raw]
    elif isinstance(raw, Mapping):
        values = [raw]
    elif isinstance(raw, Sequence):
        values = list(raw)
    else:
        values = [raw]

    codes = []
    seen = set()
    for item in values:
        candidate = None
        if isinstance(item, Mapping):
            for key in ("code", "id", "name", "value"):
                if item.get(key):
                    candidate = item[key]
                    break
        else:
            candidate = item

        code = _normalize_fstek_code(candidate)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)

    return codes


def _fstek_details(result):
    details = []
    for code in _extract_fstek_codes(result):
        details.append({
            "code": code,
            "description": FSTEK21_DESCRIPTIONS.get(code),
        })
    return details


def _canonical_status(record):
    """Normalize status/result fields to PASS/FAIL/ERROR/UNKNOWN."""

    if isinstance(record, Mapping):
        raw = record.get("status") or record.get("result")
    else:
        raw = getattr(record, "status", None) or getattr(record, "result", None)

    if raw is None:
        return "UNKNOWN"

    text = str(raw).strip().upper()
    if not text:
        return "UNKNOWN"

    if text in {"PASS", "OK", "SUCCESS", "PASSED"}:
        return "PASS"
    if text in {"FAIL", "FAILED"}:
        return "FAIL"
    if text in {"ERR", "ERROR"}:
        return "ERROR"
    if text in {"WARN", "WARNING"}:
        return "WARN"
    if text in {"UNDEF", "UNDEFINED"}:
        return "ERROR"
    if text in {"SKIP", "SKIPPED"}:
        return "SKIP"

    return text


def _aggregate_fstek_summary(results):
    summary = {}

    for record in results or []:
        status = _canonical_status(record)
        for code in _extract_fstek_codes(record):
            entry = summary.setdefault(code, {
                "code": code,
                "description": FSTEK21_DESCRIPTIONS.get(code),
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errored": 0,
                "other": 0,
            })

            entry["total"] += 1
            if status == "PASS":
                entry["passed"] += 1
            elif status == "FAIL":
                entry["failed"] += 1
            elif status == "ERROR":
                entry["errored"] += 1
            else:
                entry["other"] += 1

    ordered = sorted(summary.values(), key=lambda item: item["code"])
    return ordered


def _collect_high_findings(results):
    highs = []
    for record in results or []:
        if not isinstance(record, Mapping):
            continue
        severity = str(record.get("severity", "")).strip().lower()
        if severity != "high":
            continue

        if _canonical_status(record) != "FAIL":
            continue

        highs.append(record)

    return highs


_HOST_FIELD_MAP = {
    "hostname": "hostname",
    "host": "hostname",
    "name": "hostname",
    "node": "hostname",
    "fqdn": "hostname",
    "computername": "hostname",
    "ip": "ip",
    "ips": "ip",
    "ip_address": "ip",
    "ipaddress": "ip",
    "ip_addresses": "ip",
    "addresses": "ip",
    "address": "ip",
    "ipv4": "ipv4",
    "ipv6": "ipv6",
    "os": "os",
    "operating_system": "os",
    "distribution": "os",
    "distro": "os",
    "platform": "os",
    "kernel": "kernel",
    "kernel_release": "kernel",
    "kernel_version": "kernel",
    "arch": "arch",
    "architecture": "arch",
    "machine": "arch",
}


def _detect_local_ips():
    seen = []

    def add(candidate):
        if not candidate:
            return
        ip = str(candidate).strip()
        if not ip:
            return
        if ip in {"0.0.0.0", "::", "::0"}:
            return
        if ip not in seen:
            seen.append(ip)

    hostnames = set()
    for provider in (platform.node, socket.gethostname, socket.getfqdn):
        try:
            value = provider()
        except OSError:
            value = None
        if value:
            hostnames.add(value)

    for hostname in hostnames:
        try:
            infos = socket.getaddrinfo(hostname, None)
        except OSError:
            continue
        for info in infos:
            sockaddr = info[4] if len(info) > 4 else None
            if not sockaddr:
                continue
            ip = sockaddr[0]
            if not ip:
                continue
            add(ip)

    # UDP socket trick to determine outbound addresses without sending traffic.
    udp_targets = (
        (socket.AF_INET, ("8.8.8.8", 80)),
        (socket.AF_INET6, ("2001:4860:4860::8888", 80)),
    )

    for family, target in udp_targets:
        try:
            sock = socket.socket(family, socket.SOCK_DGRAM)
        except OSError:
            continue
        try:
            sock.connect(target)
            sockaddr = sock.getsockname()
            if sockaddr:
                add(sockaddr[0])
        except OSError:
            pass
        finally:
            try:
                sock.close()
            except OSError:
                pass

    if not seen:
        try:
            localhost_ip = socket.gethostbyname("localhost")
        except OSError:
            localhost_ip = None
        if localhost_ip:
            add(localhost_ip)

    return seen


def collect_host_metadata(profile, results, summary: Mapping | None = None):
    info = {}

    def merge_mapping(data):
        if not isinstance(data, Mapping):
            return
        for key, value in data.items():
            if value in (None, ""):
                continue
            mapped = _HOST_FIELD_MAP.get(str(key).lower())
            if not mapped:
                continue
            if mapped not in info:
                info[mapped] = value

    if isinstance(profile, Mapping):
        for key in ("host", "target", "system", "metadata", "meta"):
            merge_mapping(profile.get(key))

    for item in results or []:
        if not isinstance(item, Mapping):
            continue
        for key in ("host", "host_info", "system", "metadata", "meta"):
            merge_mapping(item.get(key))

    if isinstance(summary, Mapping):
        merge_mapping(summary.get("host"))
        os_info = summary.get("os")
        if isinstance(os_info, Mapping):
            merge_mapping(os_info)
        level = summary.get("level")
        if level:
            info.setdefault("audit_level", level)
        score = summary.get("score")
        if score is not None:
            info.setdefault("audit_score", score)

    hostname = info.get("hostname")
    if not hostname:
        hostname = platform.node() or None
        if not hostname:
            try:
                hostname = socket.gethostname()
            except OSError:
                hostname = None
        if hostname:
            info.setdefault("hostname", hostname)

    os_name = info.get("os")
    if not os_name:
        system = platform.system()
        release = platform.release()
        os_candidate = " ".join(part for part in (system, release) if part)
        if os_candidate.strip():
            info.setdefault("os", os_candidate.strip())

    kernel = info.get("kernel")
    if not kernel:
        kernel_candidate = platform.version() or platform.release()
        if kernel_candidate:
            info.setdefault("kernel", kernel_candidate)

    arch = info.get("arch")
    if not arch:
        arch_candidate = platform.machine()
        if arch_candidate:
            info.setdefault("arch", arch_candidate)

    raw_ip_values = []
    for key in ("ip", "ips", "ip_address", "ipaddress", "ip_addresses", "addresses", "address"):
        value = info.get(key)
        if not value:
            continue
        if isinstance(value, (str, bytes)):
            raw_ip_values.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            raw_ip_values.extend(value)

    detected_ips = _detect_local_ips()
    merged_ips = []
    for candidate in list(raw_ip_values) + detected_ips:
        if not candidate:
            continue
        ip = str(candidate).strip()
        if not ip:
            continue
        if ip in {"0.0.0.0", "::", "::0"}:
            continue
        if ip not in merged_ips:
            merged_ips.append(ip)

    if merged_ips:
        info["ip"] = merged_ips if len(merged_ips) > 1 else merged_ips[0]

    return info


def _collect_host_metadata(profile, results):
    return collect_host_metadata(profile, results)

def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _tojson_filter(value, ensure_ascii=False):
    return json.dumps(value, ensure_ascii=ensure_ascii, default=_json_default)


def generate_report(
    profile: dict,
    results: list,
    template_name: str,
    output_path: str,
    host_info: dict | None = None,
    summary: dict | None = None,
):
    env = Environment(loader=FileSystemLoader("reports/"))
    env.filters["fstek_codes"] = _extract_fstek_codes
    env.filters["fstek_details"] = _fstek_details
    env.filters["tojson"] = _tojson_filter
    template = env.get_template(template_name)

    total_count = len(results)
    pass_count = sum(1 for r in results if _canonical_status(r) == "PASS")
    fail_count = sum(1 for r in results if _canonical_status(r) == "FAIL")
    warn_count = sum(1 for r in results if _canonical_status(r) == "WARN")
    error_count = sum(1 for r in results if _canonical_status(r) == "ERROR")
    other_count = total_count - pass_count - fail_count - warn_count - error_count

    host_info = host_info or collect_host_metadata(profile, results, summary=summary)
    fstek_summary = _aggregate_fstek_summary(results)
    high_findings = _collect_high_findings(results)

    rendered = template.render(
        profile=profile,
        results=results,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        host=host_info,
        host_info=host_info,
        summary=summary or {},
        FSTEK21=FSTEK21_DESCRIPTIONS,
        fstek_summary=fstek_summary,
        high_findings=high_findings,
        total_count=total_count,
        pass_count=pass_count,
        fail_count=fail_count,
        warn_count=warn_count,
        error_count=error_count,
        other_count=other_count,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

def generate_json_report(results: list, output_path: str, summary: dict | None = None):
    grouped = defaultdict(list)
    for r in results:
        module = r.get("module", "core")
        grouped[module].append(r)

    # Преобразуем defaultdict в обычный dict для JSON-сериализации
    payload = {
        "modules": dict(grouped),
        "summary": summary or {},
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
