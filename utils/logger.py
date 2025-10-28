# utils/logger.py
"""Модуль логирования с поддержкой цветного вывода и уровней детализации."""

import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from colorama import init, Fore, Style

init(autoreset=True)

# Глобальные настройки логирования
_log_file: Optional[Path] = None
_log_level: int = logging.INFO
_verbose: bool = False


def configure_logging(log_file: Optional[str] = None, verbose: bool = False, level: int = logging.INFO):
    """
    Настройка параметров логирования.
    
    Args:
        log_file: Путь к файлу для записи логов
        verbose: Включить детальное логирование
        level: Уровень логирования (logging.DEBUG, INFO, WARNING, ERROR)
    """
    global _log_file, _log_level, _verbose
    _log_file = Path(log_file) if log_file else None
    _log_level = level
    _verbose = verbose
    
    if _log_file:
        _log_file.parent.mkdir(parents=True, exist_ok=True)


def _write_to_file(level: str, msg: str):
    """Запись сообщения в файл лога."""
    if _log_file:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{level}] {msg}\n")
        except OSError:
            pass


def log_debug(msg: str):
    """Отладочное сообщение (только при verbose=True)."""
    if _verbose or _log_level <= logging.DEBUG:
        print(Fore.BLUE + "[DEBUG] " + Style.RESET_ALL + msg)
        _write_to_file("DEBUG", msg)


def log_info(msg: str):
    """Информационное сообщение."""
    print(Fore.CYAN + "[INFO] " + Style.RESET_ALL + msg)
    _write_to_file("INFO", msg)


def log_pass(msg: str):
    """Сообщение об успешной проверке."""
    print(Fore.GREEN + "[PASS] " + Style.RESET_ALL + msg)
    _write_to_file("PASS", msg)


def log_fail(msg: str):
    """Сообщение о провале проверки."""
    print(Fore.RED + "[FAIL] " + Style.RESET_ALL + msg, file=sys.stderr)
    _write_to_file("FAIL", msg)


def log_warn(msg: str):
    """Предупреждение."""
    print(Fore.YELLOW + "[WARN] " + Style.RESET_ALL + msg)
    _write_to_file("WARN", msg)


def log_error(msg: str):
    """Сообщение об ошибке."""
    print(Fore.MAGENTA + "[ERROR] " + Style.RESET_ALL + msg, file=sys.stderr)
    _write_to_file("ERROR", msg)


def log_critical(msg: str):
    """Критическая ошибка."""
    print(Fore.RED + Style.BRIGHT + "[CRITICAL] " + Style.RESET_ALL + msg, file=sys.stderr)
    _write_to_file("CRITICAL", msg)


def log_section(title: str):
    """Заголовок секции для структурирования вывода."""
    separator = "=" * 60
    print(Fore.CYAN + Style.BRIGHT + f"\n{separator}")
    print(f"  {title}")
    print(f"{separator}" + Style.RESET_ALL)
    _write_to_file("SECTION", title)
