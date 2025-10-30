# modules/report_generator.py
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime, date
from pathlib import Path
from importlib import metadata as importlib_metadata
import json
import platform
import socket
import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Dict, List
from xml.etree import ElementTree as ET

# Import redaction module if available
try:
    from seclib.redaction import SensitiveDataRedactor
    REDACTION_AVAILABLE = True
except ImportError:
    REDACTION_AVAILABLE = False
    SensitiveDataRedactor = None


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


def _detect_tool_metadata():
    """Return name/version metadata for the SARIF/JUnit exports."""

    candidates = ["secaudit-core", "secaudit"]
    for dist_name in candidates:
        try:
            version = importlib_metadata.version(dist_name)
            return {
                "name": "SecAudit",
                "full_name": dist_name,
                "version": version,
            }
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:
            continue

    return {"name": "SecAudit", "full_name": "secaudit-core", "version": "dev"}


def _result_message(record: Mapping) -> str:
    for key in ("reason", "output", "message"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"Result: {_canonical_status(record)}"


def _sarif_level(status: str, severity: str | None) -> str:
    severity = (severity or "").strip().lower()
    severity_map = {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "moderate": "warning",
        "low": "note",
        "info": "note",
    }

    if status in {"FAIL", "ERROR"}:
        return severity_map.get(severity, "error")
    if status == "WARN":
        return severity_map.get(severity, "warning")
    if status == "SKIP":
        return "note"
    if status == "PASS":
        return "none"
    return severity_map.get(severity, "warning")


def _sarif_kind(status: str) -> str:
    return {
        "PASS": "pass",
        "FAIL": "fail",
        "ERROR": "fail",
        "WARN": "review",
        "SKIP": "notApplicable",
    }.get(status, "review")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, bytes)):
        return value.decode() if isinstance(value, bytes) else value
    return json.dumps(value, ensure_ascii=False, default=str)


def _iter_properties(prefix: str, value):
    if isinstance(value, Mapping):
        for key, val in value.items():
            if not isinstance(key, str):
                key = str(key)
            next_prefix = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            yield from _iter_properties(next_prefix, val)
    elif isinstance(value, (list, tuple, set)):
        return
    else:
        yield prefix, value


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


def collect_host_metadata(profile: dict | None = None, results: list | None = None, summary: dict | None = None) -> dict:
    """
    Collect host metadata for reports.
    
    Args:
        profile: Audit profile
        results: Audit results
        summary: Audit summary
        
    Returns:
        Dictionary with host metadata
    """
    metadata = {
        "hostname": platform.node() or "unknown",
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "timestamp": datetime.now().isoformat(),
        "ips": _detect_local_ips(),
    }
    
    # Add profile info if available
    if profile:
        metadata["profile_name"] = profile.get("name", "unknown")
        metadata["profile_level"] = profile.get("level", "baseline")
    
    # Add summary if available
    if summary:
        metadata["score"] = summary.get("score", 0)
        metadata["total_checks"] = summary.get("total", 0)
        metadata["passed"] = summary.get("passed", 0)
        metadata["failed"] = summary.get("failed", 0)
    
    return metadata


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
    env = Environment(loader=FileSystemLoader("reports/"), autoescape=select_autoescape(['html', 'xml']))
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


def generate_sarif_report(
    profile: Mapping | None,
    results: list,
    output_path: str,
    summary: Mapping | None = None,
    host_info: Mapping | None = None,
):
    tool_info = _detect_tool_metadata()
    rules: dict[str, dict] = {}
    sarif_results: list[dict] = []

    for record in results or []:
        if not isinstance(record, Mapping):
            continue

        status = _canonical_status(record)
        check_id = str(record.get("id") or record.get("name") or "SEC-CHECK")
        severity = record.get("severity")

        rule_entry = rules.get(check_id)
        if rule_entry is None:
            rule_entry = {
                "id": check_id,
                "name": record.get("name") or check_id,
                "shortDescription": {"text": record.get("name") or check_id},
                "fullDescription": {
                    "text": record.get("description")
                    or record.get("reason")
                    or record.get("output")
                    or record.get("name")
                    or check_id,
                },
                "defaultConfiguration": {"level": _sarif_level("FAIL", severity)},
                "properties": {},
            }
            ref = record.get("ref")
            if ref:
                rule_entry["helpUri"] = ref
            remediation = record.get("remediation")
            if remediation:
                rule_entry["help"] = {"text": remediation}
            module_name = record.get("module")
            if module_name:
                rule_entry["properties"]["module"] = module_name
            if severity:
                rule_entry["properties"]["severity"] = severity
            tags = record.get("tags")
            if tags:
                rule_entry["properties"]["tags"] = tags
            rules[check_id] = rule_entry

        properties = {
            "status": status,
            "module": record.get("module"),
            "severity": severity,
            "weight": record.get("weight"),
        }
        if record.get("tags"):
            properties["tags"] = record.get("tags")
        if record.get("remediation"):
            properties["remediation"] = record.get("remediation")
        if record.get("command"):
            properties["command"] = record.get("command")
        if record.get("evidence"):
            properties["evidence"] = record.get("evidence")
        if record.get("duration") is not None:
            properties["duration"] = _safe_float(record.get("duration"))
        if record.get("cpu_time") is not None:
            properties["cpu_time"] = _safe_float(record.get("cpu_time"))

        message_text = _result_message(record)
        sarif_record = {
            "ruleId": check_id,
            "level": _sarif_level(status, severity),
            "kind": _sarif_kind(status),
            "message": {"text": message_text},
            "properties": properties,
        }

        module_name = record.get("module")
        if module_name:
            sarif_record["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f"module://{module_name}"},
                    }
                }
            ]

        sarif_results.append(sarif_record)

    run: dict[str, object] = {
        "tool": {
            "driver": {
                "name": tool_info["name"],
                "fullName": tool_info["full_name"],
                "version": tool_info["version"],
                "informationUri": "https://github.com/alexbergh/secaudit-core",
                "rules": sorted(rules.values(), key=lambda item: item["id"]),
            }
        },
        "results": sarif_results,
    }

    properties: dict[str, object] = {}
    if isinstance(profile, Mapping):
        profile_meta = {}
        for key in ("id", "profile_name", "description", "schema_version"):
            if key in profile:
                profile_meta[key] = profile[key]
        if profile_meta:
            properties["profile"] = profile_meta
    if summary:
        properties["summary"] = summary
    if host_info:
        properties["host"] = host_info
    if properties:
        run["properties"] = properties

    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [run],
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def generate_junit_report(
    profile: Mapping | None,
    results: list,
    output_path: str,
    summary: Mapping | None = None,
    host_info: Mapping | None = None,
):
    suite_name = None
    if isinstance(profile, Mapping):
        suite_name = profile.get("profile_name") or profile.get("id")
    suite_name = suite_name or "SecAudit"

    total_time = 0.0
    failures = 0
    errors = 0
    skipped = 0

    testsuite = ET.Element(
        "testsuite",
        attrib={
            "name": suite_name,
            "tests": str(len(results or [])),
            "failures": "0",
            "errors": "0",
            "skipped": "0",
            "time": "0.0",
        },
    )

    if summary or host_info:
        properties_elem = ET.SubElement(testsuite, "properties")
        if summary:
            for name, value in _iter_properties("summary", summary):
                if not name:
                    continue
                ET.SubElement(
                    properties_elem,
                    "property",
                    attrib={"name": name, "value": _stringify(value)},
                )
        if host_info:
            for name, value in _iter_properties("host", host_info):
                if not name:
                    continue
                ET.SubElement(
                    properties_elem,
                    "property",
                    attrib={"name": name, "value": _stringify(value)},
                )

    for record in results or []:
        if not isinstance(record, Mapping):
            continue

        status = _canonical_status(record)
        duration = _safe_float(record.get("duration"))
        total_time += duration

        testcase = ET.SubElement(
            testsuite,
            "testcase",
            attrib={
                "name": str(record.get("name") or record.get("id") or "check"),
                "classname": str(record.get("module") or "secaudit"),
                "time": f"{duration:.3f}",
            },
        )

        message = _result_message(record)

        if status == "FAIL":
            failures += 1
            failure = ET.SubElement(
                testcase,
                "failure",
                attrib={"message": message, "type": "failure"},
            )
            failure.text = _stringify(record.get("remediation") or message)
        elif status == "ERROR":
            errors += 1
            error = ET.SubElement(
                testcase,
                "error",
                attrib={"message": message, "type": "error"},
            )
            error.text = _stringify(record.get("stderr") or message)
        elif status in {"WARN", "SKIP"}:
            skipped += 1
            ET.SubElement(testcase, "skipped", attrib={"message": message})

        output = record.get("output")
        if isinstance(output, str) and output:
            out_elem = ET.SubElement(testcase, "system-out")
            out_elem.text = output
        stderr = record.get("stderr")
        if isinstance(stderr, str) and stderr:
            err_elem = ET.SubElement(testcase, "system-err")
            err_elem.text = stderr

    testsuite.set("failures", str(failures))
    testsuite.set("errors", str(errors))
    testsuite.set("skipped", str(skipped))
    testsuite.set("time", f"{total_time:.3f}")

    tree = ET.ElementTree(testsuite)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


_PROM_STATUS_VALUE = {"PASS": 0, "WARN": 1, "FAIL": 2, "UNDEF": 3, "ERROR": 3}


def _prometheus_escape(value: Any) -> str:
    text = str(value if value is not None else "")
    text = text.replace("\\", "\\\\").replace("\n", "\\n").replace("\"", "\\\"")
    return text


def _prometheus_labels(labels: Mapping[str, Any]) -> str:
    parts = [f'{key}="{_prometheus_escape(val)}"' for key, val in sorted(labels.items())]
    return ",".join(parts)


def generate_prometheus_metrics(
    profile: Mapping | None,
    results: list,
    output_path: str,
    summary: Mapping | None = None,
    host_info: Mapping | None = None,
) -> None:
    lines: List[str] = []

    base_labels: Dict[str, Any] = {}
    if isinstance(profile, Mapping):
        profile_id = profile.get("id") or profile.get("profile_name")
        if profile_id:
            base_labels["profile"] = profile_id
    if isinstance(host_info, Mapping):
        hostname = host_info.get("hostname")
        if hostname:
            base_labels["host"] = hostname

    lines.append(
        "# HELP secaudit_check_status Status of audit checks (0=PASS,1=WARN,2=FAIL,3=UNDEF)"
    )
    lines.append("# TYPE secaudit_check_status gauge")

    for record in results or []:
        if not isinstance(record, Mapping):
            continue
        status = _canonical_status(record)
        value = _PROM_STATUS_VALUE.get(status, 3)
        labels = dict(base_labels)
        labels["check_id"] = record.get("id") or record.get("name") or "check"
        if record.get("module"):
            labels["module"] = record.get("module")
        if record.get("severity"):
            labels["severity"] = record.get("severity")
        lines.append(
            f"secaudit_check_status{{{_prometheus_labels(labels)}}} {value}"
        )

        duration = _safe_float(record.get("duration"))
        if duration:
            duration_labels = dict(labels)
            lines.append(
                f"secaudit_check_duration_seconds{{{_prometheus_labels(duration_labels)}}} {duration:.6f}"
            )

    if summary:
        score = summary.get("score")
        if isinstance(score, (int, float)):
            lines.append("# HELP secaudit_summary_score Overall audit score (percentage)")
            lines.append("# TYPE secaudit_summary_score gauge")
            lines.append(
                f"secaudit_summary_score{{{_prometheus_labels(base_labels)}}} {float(score):.6f}"
            )

        coverage = summary.get("coverage")
        if isinstance(coverage, (int, float)):
            lines.append("# HELP secaudit_summary_coverage Coverage of executed checks")
            lines.append("# TYPE secaudit_summary_coverage gauge")
            lines.append(
                f"secaudit_summary_coverage{{{_prometheus_labels(base_labels)}}} {float(coverage):.6f}"
            )

        counts = summary.get("status_counts")
        if isinstance(counts, Mapping):
            lines.append("# HELP secaudit_summary_status_total Checks per final status")
            lines.append("# TYPE secaudit_summary_status_total gauge")
            for status, count in counts.items():
                try:
                    numeric = float(count)
                except (TypeError, ValueError):
                    continue
                labels = dict(base_labels)
                labels["status"] = status
                lines.append(
                    f"secaudit_summary_status_total{{{_prometheus_labels(labels)}}} {numeric:.6f}"
                )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_elastic_export(
    profile: Mapping | None,
    results: list,
    output_path: str,
    summary: Mapping | None = None,
    host_info: Mapping | None = None,
) -> None:
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    profile_meta: Dict[str, Any] = {}
    if isinstance(profile, Mapping):
        for key in ("id", "profile_name", "description", "schema_version"):
            if profile.get(key) is not None:
                profile_meta[key] = profile.get(key)

    host_meta: Dict[str, Any] = {}
    if isinstance(host_info, Mapping):
        host_meta = {k: v for k, v in host_info.items() if v is not None}

    lines: List[str] = []
    for record in results or []:
        if not isinstance(record, Mapping):
            continue
        entry: Dict[str, Any] = {
            "@timestamp": timestamp,
            "event": {
                "dataset": "secaudit.check",
                "kind": "state",
                "category": ["configuration"],
                "type": ["info"],
            },
            "secaudit": {
                "check": {
                    "id": record.get("id") or record.get("name"),
                    "name": record.get("name") or record.get("id"),
                    "module": record.get("module"),
                    "severity": record.get("severity"),
                    "status": _canonical_status(record),
                    "reason": record.get("reason"),
                    "remediation": record.get("remediation"),
                    "duration": _safe_float(record.get("duration")),
                    "cpu_time": _safe_float(record.get("cpu_time")),
                },
            },
        }
        if profile_meta:
            entry["secaudit"]["profile"] = profile_meta
        if host_meta:
            entry["host"] = host_meta
        lines.append(json.dumps(entry, ensure_ascii=False))

    if summary:
        summary_entry = {
            "@timestamp": timestamp,
            "event": {
                "dataset": "secaudit.summary",
                "kind": "state",
                "category": ["configuration"],
                "type": ["info"],
            },
            "secaudit": {
                "summary": summary,
            },
        }
        if profile_meta:
            summary_entry["secaudit"]["profile"] = profile_meta
        if host_meta:
            summary_entry["host"] = host_meta
        lines.append(json.dumps(summary_entry, ensure_ascii=False))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
