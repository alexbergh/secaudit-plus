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
