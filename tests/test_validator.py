import pytest

from seclib.validator import validate_profile


@pytest.fixture
def minimal_check():
    return {
        "id": "dummy_check",
        "name": "Dummy",
        "module": "core",
        "command": "echo ok",
        "expect": "ok",
        "assert_type": "exact",
        "severity": "low",
        "tags": {},
    }


def test_validate_profile_accepts_1_x_schema_version(minimal_check):
    profile = {
        "schema_version": "1.1",
        "profile_name": "Test",
        "description": "Test profile",
        "checks": [minimal_check],
    }

    is_valid, errors = validate_profile(profile)

    assert is_valid, f"Profile unexpectedly invalid: {errors}"
    assert errors == []


def test_validate_profile_rejects_invalid_schema_version(minimal_check):
    profile = {
        "schema_version": "1.a",
        "profile_name": "Test",
        "description": "Test profile",
        "checks": [minimal_check],
    }

    is_valid, errors = validate_profile(profile)

    assert not is_valid
    assert any("schema_version" in err for err in errors)
