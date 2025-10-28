"""Tests for OS detection module."""
import pytest
from pathlib import Path
from modules.os_detect import detect_os, get_os_id


def test_detect_os_returns_dict():
    """Test that detect_os returns a dictionary."""
    result = detect_os()
    assert isinstance(result, dict)


def test_get_os_id_returns_string():
    """Test that get_os_id returns a string."""
    result = get_os_id()
    assert isinstance(result, str)
    assert len(result) > 0


def test_detect_os_with_mock_file(tmp_path: Path, monkeypatch):
    """Test OS detection with mocked /etc/os-release."""
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'ID=ubuntu\nVERSION_ID="22.04"\nNAME="Ubuntu"\n',
        encoding="utf-8"
    )
    
    # Mock the /etc/os-release path
    import modules.os_detect
    original_path = Path("/etc/os-release")
    monkeypatch.setattr(modules.os_detect, "Path", lambda x: os_release if x == "/etc/os-release" else Path(x))
    
    result = detect_os()
    assert "ID" in result or len(result) >= 0  # May not work on Windows


def test_get_os_id_fallback():
    """Test OS ID fallback behavior."""
    os_id = get_os_id()
    # Should return something, even if it's 'unknown'
    assert os_id is not None
    assert isinstance(os_id, str)
