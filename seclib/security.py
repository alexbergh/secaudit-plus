"""Security utilities для SecAudit+."""

import re
from typing import Dict, Any
from pathlib import Path


class SecurityError(Exception):
    """Исключение для security-related ошибок."""
    pass


# Паттерны для валидации
ALLOWED_VAR_NAME_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')
ALLOWED_VAR_VALUE_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_./,:@]+$')

# Паттерны для обнаружения sensitive данных
SENSITIVE_PATTERNS = [
    (r'password["\s:=]+([^\s"]+)', 'PASSWORD'),
    (r'passwd["\s:=]+([^\s"]+)', 'PASSWORD'),
    (r'token["\s:=]+([^\s"]+)', 'TOKEN'),
    (r'api[_-]?key["\s:=]+([^\s"]+)', 'API_KEY'),
    (r'secret["\s:=]+([^\s"]+)', 'SECRET'),
    (r'private[_-]?key["\s:=]+([^\s"]+)', 'PRIVATE_KEY'),
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', 'PRIVATE_KEY'),
    (r'[A-Za-z0-9+/]{40,}={0,2}', 'BASE64_TOKEN'),  # Длинные base64 строки
]

# Опасные символы для command injection
DANGEROUS_CHARS = [';', '|', '&', '$', '`', '(', ')', '<', '>', '\n', '\r']


def validate_variable_name(name: str) -> bool:
    """
    Валидация имени переменной.
    
    Разрешены только:
    - Заглавные буквы A-Z
    - Цифры 0-9
    - Подчеркивание _
    - Должно начинаться с буквы
    
    Args:
        name: Имя переменной
        
    Returns:
        bool: True если валидно
        
    Raises:
        SecurityError: Если имя невалидно
        
    Example:
        >>> validate_variable_name("FAILLOCK_DENY")
        True
        >>> validate_variable_name("invalid-name")
        SecurityError: Invalid variable name
    """
    if not name:
        raise SecurityError("Variable name cannot be empty")
    
    if not ALLOWED_VAR_NAME_PATTERN.match(name):
        raise SecurityError(
            f"Invalid variable name: '{name}'. "
            f"Only uppercase letters, digits and underscore allowed. "
            f"Must start with a letter."
        )
    
    return True


def validate_variable_value(value: str, allow_empty: bool = False) -> bool:
    """
    Валидация значения переменной.
    
    Проверяет на:
    - Опасные символы для command injection
    - Подозрительные паттерны
    - Длину значения
    
    Args:
        value: Значение переменной
        allow_empty: Разрешить пустое значение
        
    Returns:
        bool: True если валидно
        
    Raises:
        SecurityError: Если значение невалидно
    """
    if not value and not allow_empty:
        raise SecurityError("Variable value cannot be empty")
    
    if not value and allow_empty:
        return True
    
    # Проверка на опасные символы
    for char in DANGEROUS_CHARS:
        if char in value:
            raise SecurityError(
                f"Dangerous character '{char}' found in value: '{value}'"
            )
    
    # Проверка на допустимые символы
    if not ALLOWED_VAR_VALUE_PATTERN.match(value):
        raise SecurityError(
            f"Invalid characters in value: '{value}'. "
            f"Only alphanumeric, spaces, and -_./,:@ allowed."
        )
    
    # Проверка длины
    if len(value) > 1024:
        raise SecurityError(f"Value too long: {len(value)} characters (max 1024)")
    
    return True


def validate_variables(variables: Dict[str, Any]) -> Dict[str, str]:
    """
    Валидация словаря переменных.
    
    Args:
        variables: Словарь переменных для валидации
        
    Returns:
        Dict[str, str]: Валидированный словарь (все значения str)
        
    Raises:
        SecurityError: Если найдены невалидные переменные
    """
    validated = {}
    
    for key, value in variables.items():
        # Валидация имени
        validate_variable_name(key)
        
        # Конвертация в строку
        str_value = str(value) if value is not None else ""
        
        # Валидация значения
        validate_variable_value(str_value, allow_empty=True)
        
        validated[key] = str_value
    
    return validated


def redact_sensitive_data(text: str) -> str:
    """
    Удаление sensitive данных из текста.
    
    Заменяет пароли, токены, ключи на ***REDACTED***.
    
    Args:
        text: Текст для обработки
        
    Returns:
        str: Текст с замененными sensitive данными
        
    Example:
        >>> redact_sensitive_data("password=secret123")
        'password=***REDACTED***'
    """
    if not text:
        return text
    
    result = text
    
    for pattern, label in SENSITIVE_PATTERNS:
        result = re.sub(
            pattern,
            f'{label}=***REDACTED***',
            result,
            flags=re.IGNORECASE
        )
    
    return result


def validate_file_path(path: str, allowed_dirs: list[str] = None) -> Path:
    """
    Валидация пути к файлу для предотвращения path traversal.
    
    Args:
        path: Путь к файлу
        allowed_dirs: Список разрешенных директорий
        
    Returns:
        Path: Валидированный путь
        
    Raises:
        SecurityError: Если путь невалиден или опасен
    """
    if not path:
        raise SecurityError("File path cannot be empty")
    
    # Проверка на path traversal
    if '..' in path:
        raise SecurityError(f"Path traversal detected in: '{path}'")
    
    # Проверка на абсолютные пути вне allowed_dirs
    file_path = Path(path).resolve()
    
    if allowed_dirs:
        allowed = False
        for allowed_dir in allowed_dirs:
            allowed_path = Path(allowed_dir).resolve()
            try:
                file_path.relative_to(allowed_path)
                allowed = True
                break
            except ValueError:
                continue
        
        if not allowed:
            raise SecurityError(
                f"Path '{path}' is outside allowed directories: {allowed_dirs}"
            )
    
    return file_path


def sanitize_filename(filename: str) -> str:
    """
    Санитизация имени файла.
    
    Удаляет опасные символы и ограничивает длину.
    
    Args:
        filename: Исходное имя файла
        
    Returns:
        str: Безопасное имя файла
    """
    if not filename:
        return "unnamed"
    
    # Удаление path separators
    safe_name = filename.replace('/', '_').replace('\\', '_')
    
    # Удаление опасных символов
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', safe_name)
    
    # Удаление множественных подчеркиваний
    safe_name = re.sub(r'_+', '_', safe_name)
    
    # Удаление ведущих/завершающих символов
    safe_name = safe_name.strip('._-')
    
    # Ограничение длины
    if len(safe_name) > 255:
        safe_name = safe_name[:255]
    
    return safe_name or "unnamed"


def check_command_safety(command: str) -> bool:
    """
    Проверка команды на потенциально опасные паттерны.
    
    Args:
        command: Команда для проверки
        
    Returns:
        bool: True если команда выглядит безопасно
        
    Raises:
        SecurityError: Если обнаружены опасные паттерны
    """
    if not command:
        raise SecurityError("Command cannot be empty")
    
    # Проверка на command chaining
    dangerous_patterns = [
        r';\s*rm\s+-rf',
        r'\|\s*sh',
        r'\|\s*bash',
        r'>\s*/dev/',
        r'curl.*\|\s*sh',
        r'wget.*\|\s*sh',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            raise SecurityError(
                f"Potentially dangerous command pattern detected: {pattern}"
            )
    
    return True
