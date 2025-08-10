# modules/assert_logic.py
import re
from enum import Enum, auto

class AssertStatus(Enum):
    """Перечисление для статусов выполнения проверки."""
    PASS = auto()
    FAIL = auto()
    ERROR = auto()    # Ошибка в данных проверки (например, неверный regexp)
    UNKNOWN = auto()  # Неизвестный тип проверки

def assert_output(output: str, expected: str, assert_type: str) -> AssertStatus:
    """
    Сравнивает фактический вывод с ожидаемым значением на основе типа утверждения.

    Args:
        output: Фактический строковый результат, полученный от команды.
        expected: Ожидаемая строка или шаблон для сравнения.
        assert_type: Тип сравнения ('exact', 'contains', 'not_contains', 'regexp').

    Returns:
        Член перечисления AssertStatus (PASS, FAIL, ERROR, UNKNOWN).
    """
    if assert_type == "exact":
        # .strip() делает сравнение устойчивым к ведущим/конечным пробелам.
        return AssertStatus.PASS if output.strip() == expected.strip() else AssertStatus.FAIL

    elif assert_type == "contains":
        return AssertStatus.PASS if expected in output else AssertStatus.FAIL

    elif assert_type == "not_contains":
        return AssertStatus.PASS if expected not in output else AssertStatus.FAIL

    elif assert_type == "regexp":
        try:
            # re.search ищет совпадение в любом месте строки.
            return AssertStatus.PASS if re.search(expected, output) else AssertStatus.FAIL
        except re.error:
            # Некорректный синтаксис регулярного выражения — это ошибка в профиле.
            return AssertStatus.ERROR

    else:
        # Передан неподдерживаемый тип утверждения.
        return AssertStatus.UNKNOWN