# modules/report_generator.py
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
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


_HOST_FIELD_MAP = {
    "hostname": "hostname",
    "host": "hostname",
    "name": "hostname",
    "node": "hostname",
    "fqdn": "hostname",
    "computername": "hostname",
    "ip": "ip",
    "ip_address": "ip",
    "ipaddress": "ip",
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


def _detect_local_ip():
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = None

    candidates = []
    if hostname:
        try:
            _, _, host_ips = socket.gethostbyname_ex(hostname)
            candidates.extend(host_ips)
        except OSError:
            pass

    try:
        candidates.append(socket.gethostbyname("localhost"))
    except OSError:
        pass

    for ip in candidates:
        if not ip:
            continue
        if ip.startswith("127.") or ip == "::1":
            continue
        return ip

    return candidates[0] if candidates else None


def _collect_host_metadata(profile, results):
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

    if "ip" not in info and "ipv4" not in info:
        detected_ip = _detect_local_ip()
        if detected_ip:
            info.setdefault("ip", detected_ip)

    return info

def generate_report(profile: dict, results: list, template_name: str, output_path: str):
    env = Environment(loader=FileSystemLoader("reports/"))
    env.filters["fstek_codes"] = _extract_fstek_codes
    env.filters["fstek_details"] = _fstek_details
    template = env.get_template(template_name)

    pass_count = sum(1 for r in results if r["result"] == "PASS")
    fail_count = sum(1 for r in results if r["result"] == "FAIL")
    warn_count = sum(1 for r in results if r["result"] == "WARN")

    host_info = _collect_host_metadata(profile, results)

    rendered = template.render(
        profile=profile,
        results=results,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        host=host_info,
        host_info=host_info,
        FSTEK21=FSTEK21_DESCRIPTIONS,
        pass_count=pass_count,
        fail_count=fail_count,
        warn_count=warn_count
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

def generate_json_report(results: list, output_path: str):
    grouped = defaultdict(list)
    for r in results:
        module = r.get("module", "core")
        grouped[module].append(r)

    # Преобразуем defaultdict в обычный dict для JSON-сериализации
    grouped_dict = dict(grouped)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(grouped_dict, f, indent=2, ensure_ascii=False)
