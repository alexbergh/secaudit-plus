# modules/bash_executor.py
import subprocess
import shlex

# 1. Вводим пользовательское исключение для явной обработки ошибок.
class CommandError(Exception):
    """Исключение, возникающее при ошибке выполнения внешней команды."""
    def __init__(self, message, stderr="", returncode=None):
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode

    def __str__(self):
        if self.returncode is not None:
            return f"Command failed with exit code {self.returncode}: {self.stderr}"
        return super().__str__()


def run_bash(command: str, timeout: int = 10) -> str:
    """
    Выполняет команду в оболочке bash с контролем ошибок и таймаутом.

    Args:
        command: Строка с командой для выполнения.
        timeout: Максимальное время выполнения команды в секундах.

    Returns:
        Стандартный вывод (stdout) команды в виде строки.

    Raises:
        CommandError: Если команда завершается с ненулевым кодом возврата,
                      истекает таймаут или происходит другая ошибка выполнения.
    """
    # ВАЖНО: Использование shell=True представляет риск безопасности, если команда
    # может быть подконтрольна злоумышленнику. В данном случае команды поступают
    # из доверенных YAML-профилей, но этот риск необходимо осознавать.
    try:
        # 2. Используем subprocess.run с таймаутом и проверкой кода возврата.
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True, # Более современный аналог stdout/stderr=PIPE
            timeout=timeout,
            check=False  # Мы будем проверять код возврата вручную
        )

        # 3. Проверяем код возврата. Если не 0, выбрасываем наше исключение с stderr.
        if result.returncode != 0:
            raise CommandError(
                message=f"Command '{command}' failed.",
                stderr=result.stderr.strip(),
                returncode=result.returncode
            )

        # 4. Если все успешно, возвращаем stdout.
        return result.stdout.strip()

    except subprocess.TimeoutExpired as e:
        raise CommandError(
            f"Command '{command}' timed out after {timeout} seconds.",
            stderr=e.stderr or ""
        ) from e
    except FileNotFoundError as e:
        # Эта ошибка возникает, если сама оболочка (/bin/sh) не найдена
        raise CommandError(f"Shell not found: {e}") from e
    except Exception as e:
        # Ловим любые другие непредвиденные ошибки subprocess
        raise CommandError(f"An unexpected error occurred while running command: {e}") from e