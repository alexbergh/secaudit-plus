# modules/os_detect.py
"""Модуль определения операционной системы на основе /etc/os-release."""

from pathlib import Path
from typing import Dict


def read_os_release() -> Dict[str, str]:
    """
    Читает файл /etc/os-release и возвращает словарь параметров ОС.
    
    Файл /etc/os-release содержит информацию об операционной системе
    в формате KEY=VALUE. Функция парсит этот файл и возвращает словарь.
    
    Returns:
        Dict[str, str]: Словарь с параметрами ОС (ID, VERSION_ID, NAME и т.д.)
                       Пустой словарь, если файл не найден или не читается.
    
    Example:
        >>> info = read_os_release()
        >>> print(info.get('ID'))
        'ubuntu'
    """
    osr_path = Path("/etc/os-release")
    if not osr_path.exists():
        return {}

    data = {}
    try:
        for line in osr_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().upper()
            value = value.strip().strip('"')
            data[key] = value
    except (OSError, UnicodeDecodeError):
        return {}
    
    return data


def detect_os() -> str:
    """
    Определяет тип операционной системы на основе /etc/os-release.
    
    Функция анализирует поля ID и ID_LIKE из /etc/os-release и возвращает
    идентификатор ОС, используемый для выбора профиля аудита.
    
    Returns:
        str: Идентификатор ОС: 'astra', 'alt', 'centos', 'debian' или 'unknown'
    
    Note:
        Приоритет определения:
        1. Astra Linux (по ID или ID_LIKE)
        2. ALT Linux (по ID)
        3. CentOS/RHEL (по ID или ID_LIKE)
        4. Debian/Ubuntu (по ID_LIKE или ID)
        5. unknown (если не удалось определить)
    
    Example:
        >>> os_type = detect_os()
        >>> print(f"Detected OS: {os_type}")
        Detected OS: debian
    """
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


def get_os_id() -> str:
    """
    Возвращает идентификатор ОС (alias для detect_os).
    
    Returns:
        str: Идентификатор операционной системы
    """
    return detect_os()
