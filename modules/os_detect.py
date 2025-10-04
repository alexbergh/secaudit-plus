# modules/os_detect.py

from pathlib import Path
from typing import Dict


def read_os_release() -> Dict[str, str]:
    """Читает /etc/os-release и возвращает словарь ключей."""

    osr_path = Path("/etc/os-release")
    if not osr_path.exists():
        return {}

    data = {}
    for line in osr_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip().strip('"')
        data[key] = value
    return data


def detect_os() -> str:
    info = read_os_release()
    os_id = info.get("ID", "").lower()
    os_like = info.get("ID_LIKE", "").lower()

    if "astra" in os_id or "astra" in os_like:
        return "astra"
    if "alt" in os_id:
        return "alt"
    if "centos" in os_id or "rhel" in os_like:
        return "centos"
    if "debian" in os_like or "ubuntu" in os_id:
        return "debian"
    return "unknown"
