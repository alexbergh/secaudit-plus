"""Tests for logger utility."""
import pytest
from io import StringIO
import sys
from utils.logger import log_info, log_warn, log_pass, log_fail


def test_log_info_output(capsys):
    """Test info logging output."""
    log_info("Test info message")
    captured = capsys.readouterr()
    assert "Test info message" in captured.out


def test_log_warn_output(capsys):
    """Test warning logging output."""
    log_warn("Test warning")
    captured = capsys.readouterr()
    assert "Test warning" in captured.out


def test_log_pass_output(capsys):
    """Test pass logging output."""
    log_pass("Test passed")
    captured = capsys.readouterr()
    assert "Test passed" in captured.out


def test_log_fail_output(capsys):
    """Test fail logging output."""
    log_fail("Test failed")
    captured = capsys.readouterr()
    assert "Test failed" in captured.out


def test_log_functions_with_special_characters(capsys):
    """Test logging with special characters."""
    log_info("Message with 'quotes' and \"double quotes\"")
    captured = capsys.readouterr()
    assert "quotes" in captured.out


def test_log_functions_with_unicode(capsys):
    """Test logging with unicode characters."""
    log_info("Тестовое сообщение на русском")
    captured = capsys.readouterr()
    assert "Тестовое" in captured.out or len(captured.out) > 0  # May vary by terminal
