from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def _load_profile(profile_path: Path) -> dict:
    with profile_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.mark.parametrize("profile_path", sorted(PROFILES_DIR.glob("*.yml")))
def test_profile_yaml_is_well_formed(profile_path):
    _load_profile(profile_path)


def _get_check(profile: dict, check_id: str) -> dict:
    for check in profile.get("checks", []):
        if check.get("id") == check_id:
            return check
    raise KeyError(f"check {check_id} not found")


def test_base_ntp_sources_expectation_enforces_primary_and_total():
    profile = _load_profile(PROFILES_DIR / "base-linux.yml")
    check = _get_check(profile, "base_ntp_sources_reliable")
    pattern = re.compile(check["expect"])

    assert pattern.match("primary=1 total=3")
    assert pattern.match("skipped")
    assert not pattern.match("primary=0 total=0")
    assert not pattern.match("primary=1 total=1")


def test_base_ntp_makestep_expectation_requires_thresholds():
    profile = _load_profile(PROFILES_DIR / "base-linux.yml")
    check = _get_check(profile, "base_ntp_makestep")
    pattern = re.compile(check["expect"])

    assert pattern.match("makestep 1.0 3")
    assert pattern.match("skipped")
    assert not pattern.match("makestep")
    assert not pattern.match("makestep 0.5")


def test_base_repo_apt_signed_by_expectation_flags_missing_entries():
    profile = _load_profile(PROFILES_DIR / "base-linux.yml")
    check = _get_check(profile, "base_repo_apt_signed_by")
    pattern = re.compile(check["expect"])

    assert pattern.match("ok")
    assert pattern.match("skipped")
    assert not pattern.match("deb http://example.com stable main")
