import pytest

from modules import cli as cli_module
from modules import audit_runner as audit_module
from secaudit.exceptions import MissingDependencyError


def test_cli_load_profile_requires_yaml(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.yml"
    profile_path.write_text("schema_version: 1\nchecks: []\n", encoding="utf-8")

    monkeypatch.setattr(cli_module, "yaml", None)
    monkeypatch.setattr(cli_module, "_YAML_IMPORT_ERROR", ModuleNotFoundError("yaml"))

    with pytest.raises(MissingDependencyError) as exc:
        cli_module.load_profile_file(str(profile_path))

    assert "PyYAML" in str(exc.value)


def test_audit_runner_requires_yaml(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.yml"
    profile_path.write_text("schema_version: 1\nchecks: []\n", encoding="utf-8")

    monkeypatch.setattr(audit_module, "yaml", None)
    monkeypatch.setattr(audit_module, "_YAML_IMPORT_ERROR", ModuleNotFoundError("yaml"))

    with pytest.raises(MissingDependencyError) as exc:
        audit_module.load_profile(profile_path)

    assert "PyYAML" in str(exc.value)
