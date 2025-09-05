"""Utility helpers for validating command output against expectations."""

import re
from enum import Enum, auto


class AssertStatus(Enum):
    """Статусы выполнения проверки."""

    PASS = auto()
    FAIL = auto()
    WARN = auto()  # Неподдерживаемый тип проверки


def assert_output(output: str, expected: str, assert_type: str) -> str:
    """Сравнивает фактический вывод с ожидаемым значением.

    Parameters
    ----------
    output:
        Фактический строковый результат, полученный от команды.
    expected:
        Ожидаемая строка или шаблон для сравнения.
    assert_type:
        Тип сравнения (``exact``, ``contains``, ``not_contains`` или
        ``regexp``).

    Returns
    -------
    str
        Строковый статус проверки: ``PASS``, ``FAIL`` или ``WARN``.
    """

    if assert_type == "exact":
        status = (
            AssertStatus.PASS
            if output.strip() == expected.strip()
            else AssertStatus.FAIL
        )

    elif assert_type == "contains":
        status = AssertStatus.PASS if expected in output else AssertStatus.FAIL

    elif assert_type == "not_contains":
        status = (
            AssertStatus.PASS if expected not in output else AssertStatus.FAIL
        )

    elif assert_type == "regexp":
        try:
            # re.search ищет совпадение в любом месте строки.
            status = (
                AssertStatus.PASS
                if re.search(expected, output)
                else AssertStatus.FAIL
            )
        except re.error:
            # Некорректный синтаксис регулярного выражения трактуем
            # как провал проверки.
            status = AssertStatus.FAIL

    else:
        # Передан неподдерживаемый тип утверждения.
        status = AssertStatus.WARN

    return status.name
