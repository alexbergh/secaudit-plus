"""Tests for bash executor module."""
import pytest
from modules.bash_executor import run_bash


def test_run_bash_simple_command():
    """Test running a simple bash command."""
    result = run_bash("echo hello", timeout=5, rc_ok=(0,))
    assert result.returncode == 0
    assert "hello" in result.stdout
    assert result.stderr == ""


def test_run_bash_with_stderr():
    """Test command that produces stderr."""
    result = run_bash("echo error >&2", timeout=5, rc_ok=(0,))
    assert result.returncode == 0
    assert "error" in result.stderr


def test_run_bash_non_zero_exit():
    """Test command with non-zero exit code."""
    result = run_bash("exit 42", timeout=5, rc_ok=(0,))
    assert result.returncode == 42


def test_run_bash_timeout():
    """Test command timeout."""
    # This should timeout on most systems
    result = run_bash("sleep 10", timeout=1, rc_ok=(0,))
    # Should have timed out
    assert result.returncode != 0 or result.stderr != ""


def test_run_bash_multiline_output():
    """Test command with multiline output."""
    result = run_bash("printf 'line1\\nline2\\nline3'", timeout=5, rc_ok=(0,))
    assert result.returncode == 0
    lines = result.stdout.strip().split('\n')
    assert len(lines) == 3
    assert lines[0] == "line1"
    assert lines[2] == "line3"


def test_run_bash_with_variables():
    """Test command with environment variables."""
    result = run_bash("echo $HOME", timeout=5, rc_ok=(0,))
    assert result.returncode == 0
    # Should have some output (HOME is usually set)
    assert len(result.stdout) > 0
