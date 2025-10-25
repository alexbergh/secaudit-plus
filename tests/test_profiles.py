from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from modules.audit_runner import _expand_extends, load_profile as load_profile_data

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
BASE_PROFILE = PROFILES_DIR / "base" / "linux.yml"
DEBIAN_PROFILE = PROFILES_DIR / "os" / "debian.yml"
WORKSTATION_PROFILE = PROFILES_DIR / "base" / "workstation.yml"


def _load_profile(profile_path: Path) -> dict:
    with profile_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_expanded_profile(profile_path: Path) -> dict:
    raw_profile = load_profile_data(str(profile_path))
    return _expand_extends(raw_profile, profile_path.resolve().parent)


def _collect_check_ids(profile: dict) -> list[str]:
    checks = profile.get("checks", []) or []
    return [str(check.get("id", "")) for check in checks if isinstance(check, dict)]


@pytest.mark.parametrize("profile_path", sorted(PROFILES_DIR.glob("**/*.yml")))
def test_profile_yaml_is_well_formed(profile_path):
    _load_profile(profile_path)


def _get_check(profile: dict, check_id: str) -> dict:
    for check in profile.get("checks", []):
        if check.get("id") == check_id:
            return check
    raise KeyError(f"check {check_id} not found")


def test_base_ntp_sources_expectation_enforces_primary_and_total():
    profile = _load_profile(BASE_PROFILE)
    check = _get_check(profile, "base_ntp_sources_reliable")
    pattern = re.compile(check["expect"])

    assert pattern.match("primary=1 total=3")
    assert pattern.match("skipped")
    assert not pattern.match("primary=0 total=0")
    assert not pattern.match("primary=1 total=1")


def test_base_ntp_makestep_expectation_requires_thresholds():
    profile = _load_profile(BASE_PROFILE)
    check = _get_check(profile, "base_ntp_makestep")
    pattern = re.compile(check["expect"])

    assert pattern.match("makestep 1.0 3")
    assert pattern.match("skipped")
    assert not pattern.match("makestep")
    assert not pattern.match("makestep 0.5")


def test_base_ntp_minsources_expectation_requires_minimum_sources():
    profile = _load_profile(BASE_PROFILE)
    check = _get_check(profile, "base_ntp_minsources")
    pattern = re.compile(check["expect"])

    assert pattern.match("minsources 2")
    assert pattern.match("minsources 5")
    assert pattern.match("skipped")
    assert not pattern.match("minsources 1")
    assert not pattern.match("minsources")


def test_base_repo_apt_signed_by_expectation_flags_missing_entries():
    profile = _load_profile(BASE_PROFILE)
    check = _get_check(profile, "base_repo_apt_signed_by")
    pattern = re.compile(check["expect"])

    assert pattern.match("ok")
    assert pattern.match("skipped")
    assert not pattern.match("deb http://example.com stable main")


def test_mount_options_require_expected_flags():
    profile = _load_profile(BASE_PROFILE)

    tmp_check = _get_check(profile, "base_tmp_mount_options")
    tmp_pattern = re.compile(tmp_check["expect"])
    assert tmp_pattern.search("rw,nosuid,nodev,noexec")
    assert not tmp_pattern.search("rw,nodev")

    vartmp_check = _get_check(profile, "base_vartmp_mount_options")
    vartmp_pattern = re.compile(vartmp_check["expect"])
    assert vartmp_pattern.search("nosuid,nodev,noexec")
    assert not vartmp_pattern.search("nosuid,nodev")

    home_check = _get_check(profile, "base_home_mount_options")
    assert home_check["assert_type"] == "contains"
    assert home_check["expect"] == "nodev"


def test_base_profile_has_unique_check_ids_after_expansion():
    profile = _load_expanded_profile(BASE_PROFILE)
    check_ids = _collect_check_ids(profile)
    assert len(check_ids) == len(set(check_ids)), "duplicate check IDs detected in base profile"


def test_base_profile_container_runtime_expectations_are_present():
    profile = _load_expanded_profile(BASE_PROFILE)
    vars_section = profile.get("vars", {}) or {}
    assert vars_section.get("PODMAN_EXPECTED_EVENTS_LOGGER") == "journald"
    assert vars_section.get("CONTAINERD_REQUIRE_SYSTEMD_CGROUP") == "true"

    rootless_check = _get_check(profile, "base_rootless_runtime_sockets")
    assert rootless_check["assert_type"] == "set_allowlist"
    assert rootless_check["expect"] == "profiles/include/allowlist_rootless_sockets.txt"


@pytest.mark.parametrize("profile_path", sorted((PROFILES_DIR / "os").glob("*.yml")))
def test_os_profiles_have_unique_check_ids(profile_path: Path):
    profile = _load_expanded_profile(profile_path)
    check_ids = _collect_check_ids(profile)
    assert len(check_ids) == len(set(check_ids)), f"duplicate check IDs detected in {profile_path.name}"


def test_workstation_profile_has_unique_check_ids():
    profile = _load_expanded_profile(WORKSTATION_PROFILE)
    check_ids = _collect_check_ids(profile)
    assert len(check_ids) == len(set(check_ids)), "duplicate check IDs detected in workstation profile"


def test_workstation_profile_inherits_gui_hardening():
    profile = _load_expanded_profile(WORKSTATION_PROFILE)
    vars_section = profile.get("vars", {}) or {}
    assert vars_section.get("GUI_IDLE_TIMEOUT") == "300"
    check_ids = set(_collect_check_ids(profile))
    assert {"workstation_gnome_idle_lock_policy", "workstation_firefox_policies_enforced"}.issubset(check_ids)


def test_debian_profile_overrides_shadow_permission_patterns():
    profile = _load_expanded_profile(DEBIAN_PROFILE)
    vars_section = profile.get("vars", {}) or {}
    assert vars_section.get("SHADOW_PERM_PATTERN") == "^(600|640)$"
    assert vars_section.get("GSHADOW_PERM_PATTERN") == "^(600|640)$"
    check_ids = _collect_check_ids(profile)
    assert "check_shadow_perms" in check_ids
    assert "check_gshadow_perms" in check_ids
