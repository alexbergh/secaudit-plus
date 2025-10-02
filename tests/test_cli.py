import pytest

from modules import cli


@pytest.mark.parametrize(
    "argv, expected_profile",
    [
        (["secaudit", "audit", "--profile", "profiles/alt.yml"], "profiles/alt.yml"),
        (["secaudit", "--profile", "profiles/alt.yml", "audit"], "profiles/alt.yml"),
    ],
)
def test_parse_args_allows_profile_any_position(monkeypatch, argv, expected_profile):
    monkeypatch.setattr(cli.sys, "argv", argv)

    args = cli.parse_args()

    assert args.command == "audit"
    assert args.profile == expected_profile


def test_parse_args_additional_subcommand_arguments_preserved(monkeypatch):
    argv = [
        "secaudit",
        "audit",
        "--profile",
        "profiles/alt.yml",
        "--fail-on-undef",
        "--fail-level",
        "medium",
    ]
    monkeypatch.setattr(cli.sys, "argv", argv)

    args = cli.parse_args()

    assert args.command == "audit"
    assert args.profile == "profiles/alt.yml"
    assert args.fail_on_undef is True
    assert args.fail_level == "medium"


def test_parse_args_accepts_positional_profile(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["secaudit", "validate", "profiles/alt.yml"])

    args = cli.parse_args()

    assert args.command == "validate"
    assert args.profile == "profiles/alt.yml"


def test_parse_args_describe_check_keeps_check_id_with_positional_profile(monkeypatch):
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["secaudit", "describe-check", "ssh_root_login", "profiles/alt.yml"],
    )

    args = cli.parse_args()

    assert args.command == "describe-check"
    assert args.check_id == "ssh_root_login"
    assert args.profile == "profiles/alt.yml"


def test_parse_args_list_modules_positional_profile(monkeypatch):
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["secaudit", "list-modules", "profiles/alt.yml"],
    )

    args = cli.parse_args()

    assert args.command == "list-modules"
    assert args.profile == "profiles/alt.yml"


def test_parse_args_defaults_to_baseline_profile(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["secaudit", "list-modules"])

    args = cli.parse_args()

    assert args.profile == cli.DEFAULT_PROFILE_PATH
