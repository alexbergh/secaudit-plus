import sys

import pytest

from modules import cli
from modules.cli import parse_args


def test_parse_args_level_workers_and_vars(monkeypatch):
    monkeypatch.setenv("SECAUDIT_LEVEL", "baseline")
    monkeypatch.setenv("SECAUDIT_WORKERS", "2")
    argv = [
        "secaudit",
        "--profile",
        "profiles/base/linux.yml",
        "audit",
        "--level",
        "paranoid",
        "--workers",
        "4",
        "--var",
        "FOO=bar",
        "--var",
        "Baz=2",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    args = parse_args()

    assert args.command == "audit"
    assert args.profile == "profiles/base/linux.yml"
    assert args.level == "paranoid"
    assert args.workers == 4
    assert args.vars == {"FOO": "bar", "Baz": "2"}


def test_parse_args_env_defaults(monkeypatch):
    monkeypatch.setenv("SECAUDIT_LEVEL", "strict")
    monkeypatch.setenv("SECAUDIT_WORKERS", "6")
    monkeypatch.setattr(sys, "argv", ["secaudit", "audit"])

    args = parse_args()

    assert args.command == "audit"
    assert args.level == "strict"
    assert args.workers == 6
    assert args.profile == "profiles/common/baseline.yml"


def test_parse_args_invalid_var(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["secaudit", "audit", "--var", "broken"])

    with pytest.raises(SystemExit) as exc:
        parse_args()

    assert exc.value.code == 2


@pytest.mark.parametrize(
    "argv, expected_profile",
    [
        (["secaudit", "audit", "--profile", "profiles/os/alt-8sp.yml"], "profiles/os/alt-8sp.yml"),
        (["secaudit", "--profile", "profiles/os/alt-8sp.yml", "audit"], "profiles/os/alt-8sp.yml"),
    ],
)
def test_parse_args_accepts_profile_any_position(monkeypatch, argv, expected_profile):
    monkeypatch.setattr(sys, "argv", argv)

    args = cli.parse_args()

    assert args.command == "audit"
    assert args.profile == expected_profile


def test_parse_args_positional_profile_overrides_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "secaudit",
            "validate",
            "--profile",
            "profiles/common/baseline.yml",
            "profiles/os/alt-8sp.yml",
        ],
    )

    args = cli.parse_args()

    assert args.command == "validate"
    assert args.profile == "profiles/os/alt-8sp.yml"


def test_parse_args_defaults_to_baseline_profile(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["secaudit", "list-modules"])

    args = cli.parse_args()

    assert args.profile == cli.DEFAULT_PROFILE_PATH
