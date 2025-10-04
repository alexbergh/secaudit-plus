"""SecAudit public package interface."""

from __future__ import annotations

from typing import Any

__all__ = ["main"]


def main(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper around :func:`secaudit.main.main`."""

    from .main import main as _main

    return _main(*args, **kwargs)
