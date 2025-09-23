# modules/bash_executor.py
"""Utility functions for running shell commands with error handling."""

from __future__ import annotations

import subprocess


class CommandError(Exception):
    """Исключение, возникающее при ошибке выполнения внешней команды."""

    def __init__(
        self,
        message: str,
        stderr: str = "",
        returncode: int | None = None,
        stdout: str = "",
    ):
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode
        self.stdout = stdout

    def __str__(self) -> str:  # pragma: no cover - simple formatting
        if self.returncode is not None:
            return f"Command failed with exit code {self.returncode}: {self.stderr}"
        return super().__str__()


def run_bash(
    command: str,
    timeout: int = 10,
    rc_ok: tuple[int, ...] = (0, 1),
) -> subprocess.CompletedProcess:
    """Run *command* in a shell and return the completed process.

    Args:
        command: Строка с командой для выполнения.
        timeout: Максимальное время выполнения команды в секундах.
        rc_ok: Коды возврата, которые считаются успешными.

    Returns:
        Объект :class:`subprocess.CompletedProcess`.

    Raises:
        CommandError: Если код возврата не входит в ``rc_ok`` или возникла
            другая ошибка выполнения.
    """

    # ВАЖНО: Использование shell=True представляет риск безопасности, если команда
    # может быть подконтрольна злоумышленнику. В данном случае команды поступают
    # из доверенных YAML-профилей, но этот риск необходимо осознавать.
    try:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode not in rc_ok:
            raise CommandError(
                message=f"Command '{command}' failed.",
                stderr=(result.stderr or "").strip(),
                returncode=result.returncode,
                stdout=result.stdout or "",
            )

        return result

    except subprocess.TimeoutExpired as e:  # pragma: no cover - rare
        raise CommandError(
            f"Command '{command}' timed out after {timeout} seconds.",
            stderr=e.stderr or "",
        ) from e
    except FileNotFoundError as e:  # pragma: no cover - environment issue
        raise CommandError(f"Shell not found: {e}") from e
    except Exception as e:  # pragma: no cover - defensive
        raise CommandError(
            f"An unexpected error occurred while running command: {e}"
        ) from e

