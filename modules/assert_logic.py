# modules/assert_logic.py
import re

def assert_output(output: str, expected: str, assert_type: str) -> str:
    if assert_type == "exact":
        return "PASS" if output.strip() == expected.strip() else "FAIL"

    elif assert_type == "contains":
        return "PASS" if expected in output else "FAIL"

    elif assert_type == "not_contains":
        return "PASS" if expected not in output else "FAIL"

    elif assert_type == "regexp":
        try:
            return "PASS" if re.search(expected, output) else "FAIL"
        except re.error:
            return "FAIL"

    else:
        return "WARN"
