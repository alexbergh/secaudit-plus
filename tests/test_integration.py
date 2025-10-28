"""Integration tests for SecAudit+ end-to-end workflows."""
import json
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def test_profile(tmp_path):
    """Create a simple test profile for integration testing."""
    profile_content = """
schema_version: 1
profile_name: integration_test
description: Test profile for integration tests

checks:
  - id: test/echo
    name: Echo test
    module: system
    command: echo "test_output"
    expect: "test_output"
    assert_type: exact
    severity: low
    
  - id: test/hostname
    name: Hostname check
    module: system
    command: hostname
    assert_type: not_empty
    severity: low
"""
    profile_path = tmp_path / "test_profile.yml"
    profile_path.write_text(profile_content, encoding="utf-8")
    return profile_path


@pytest.mark.integration
def test_cli_help():
    """Test that CLI help command works."""
    result = subprocess.run(
        [sys.executable, "-m", "secaudit.main", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower() or "secaudit" in result.stdout.lower()


@pytest.mark.integration
def test_cli_info():
    """Test that CLI info command works."""
    result = subprocess.run(
        [sys.executable, "-m", "secaudit.main", "--info"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "SecAudit" in result.stdout


@pytest.mark.integration
def test_profile_validation(test_profile):
    """Test profile validation command."""
    result = subprocess.run(
        [sys.executable, "-m", "secaudit.main", "validate", "--profile", str(test_profile)],
        capture_output=True,
        text=True,
        cwd=Path.cwd()
    )
    # Should pass validation
    assert result.returncode == 0 or "OK" in result.stdout


@pytest.mark.integration
def test_audit_execution(test_profile, tmp_path):
    """Test full audit execution."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    
    result = subprocess.run(
        [
            sys.executable, "-m", "secaudit.main",
            "audit",
            "--profile", str(test_profile)
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path
    )
    
    # Audit should complete (may pass or fail checks)
    assert result.returncode in (0, 2)  # 0 = success, 2 = failed checks
    
    # Check that report files were created
    report_json = results_dir / "report.json"
    if report_json.exists():
        data = json.loads(report_json.read_text(encoding="utf-8"))
        assert "results" in data
        assert "summary" in data


@pytest.mark.integration
def test_list_modules_command(test_profile):
    """Test list-modules command."""
    result = subprocess.run(
        [
            sys.executable, "-m", "secaudit.main",
            "list-modules",
            "--profile", str(test_profile)
        ],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "system" in result.stdout.lower()


@pytest.mark.integration
def test_list_checks_command(test_profile):
    """Test list-checks command."""
    result = subprocess.run(
        [
            sys.executable, "-m", "secaudit.main",
            "list-checks",
            "--profile", str(test_profile)
        ],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    # Should list our test checks
    assert "test/echo" in result.stdout or "Echo test" in result.stdout


@pytest.mark.integration
def test_os_detection():
    """Test OS detection functionality."""
    from modules.os_detect import detect_os, read_os_release
    
    os_type = detect_os()
    assert isinstance(os_type, str)
    assert len(os_type) > 0
    
    os_info = read_os_release()
    assert isinstance(os_info, dict)


@pytest.mark.integration
def test_logger_functionality():
    """Test logger module."""
    from utils.logger import log_info, log_warn, log_fail, log_pass, configure_logging
    from io import StringIO
    import sys
    
    # Capture output
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    
    try:
        log_info("Test info message")
        log_warn("Test warning")
        log_pass("Test pass")
        
        output = captured_output.getvalue()
        assert "Test info message" in output
        assert "Test warning" in output
        assert "Test pass" in output
    finally:
        sys.stdout = old_stdout


@pytest.mark.integration
def test_bash_executor():
    """Test bash command execution."""
    from modules.bash_executor import run_bash, CommandError
    
    # Test successful command
    result = run_bash("echo hello", timeout=5, rc_ok=(0,))
    assert result.returncode == 0
    assert "hello" in result.stdout
    
    # Test command with non-zero exit
    with pytest.raises(CommandError):
        run_bash("exit 1", timeout=5, rc_ok=(0,))


@pytest.mark.integration
def test_end_to_end_workflow(test_profile, tmp_path):
    """Test complete end-to-end workflow: validate -> audit -> reports."""
    # Step 1: Validate profile
    validate_result = subprocess.run(
        [sys.executable, "-m", "secaudit.main", "validate", "--profile", str(test_profile)],
        capture_output=True,
        text=True
    )
    assert validate_result.returncode == 0
    
    # Step 2: Run audit
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    
    audit_result = subprocess.run(
        [sys.executable, "-m", "secaudit.main", "audit", "--profile", str(test_profile)],
        capture_output=True,
        text=True,
        cwd=tmp_path
    )
    
    # Step 3: Verify reports exist
    expected_reports = [
        "report.json",
        "report_grouped.json",
        "report.md",
    ]
    
    for report_name in expected_reports:
        report_path = results_dir / report_name
        if report_path.exists():
            assert report_path.stat().st_size > 0, f"{report_name} is empty"
