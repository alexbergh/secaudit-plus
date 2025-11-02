# tests/test_assert_logic.py

from modules.assert_logic import assert_output


def test_exact_pass():
    assert assert_output("yes", "yes", "exact") == "PASS"


def test_exact_fail():
    assert assert_output("no", "yes", "exact") == "FAIL"


def test_contains_pass():
    assert assert_output("permit root login no", "root", "contains") == "PASS"


def test_contains_fail():
    assert assert_output("deny all", "root", "contains") == "FAIL"


def test_not_contains_pass():
    assert assert_output("secure mode", "admin", "not_contains") == "PASS"


def test_not_contains_fail():
    assert assert_output("admin access granted", "admin", "not_contains") == "FAIL"


def test_regexp_pass():
    assert assert_output("PermitRootLogin no", r"^PermitRootLogin\s+no$", "regexp") == "PASS"


def test_regexp_fail():
    assert assert_output("PermitRootLogin yes", r"^PermitRootLogin\s+no$", "regexp") == "FAIL"


def test_invalid_regexp():
    assert assert_output("text", r"[a-z", "regexp") == "FAIL"


def test_unknown_type():
    assert assert_output("text", "text", "xyz") == "WARN"
