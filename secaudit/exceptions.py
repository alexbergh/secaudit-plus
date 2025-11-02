"""Custom exceptions used across SecAudit."""

from __future__ import annotations

from typing import Optional


class MissingDependencyError(RuntimeError):
    """Raised when an optional runtime dependency is not installed."""

    def __init__(
        self,
        *,
        package: str,
        import_name: Optional[str] = None,
        instructions: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        self.package = package
        self.import_name = import_name or package
        self.instructions = instructions
        self.original = original

        dependency_label = self.package
        if self.import_name and self.import_name != self.package:
            dependency_label += f" (модуль '{self.import_name}')"

        message = f"Отсутствует обязательная зависимость {dependency_label}."
        if self.instructions:
            message += f" Установите её и повторите попытку: {self.instructions}."
        else:
            message += " Установите требуемый пакет и повторите попытку."

        super().__init__(message)
