"""Sensitive data redaction module for SecAudit+ reports.

This module provides functionality to detect and redact sensitive information
from audit results, evidence, and reports to prevent accidental data leakage.
"""

import re
from typing import Any, Dict, List, Pattern, Union


# Sensitive data patterns
SENSITIVE_PATTERNS: List[Dict[str, Union[str, Pattern]]] = [
    # Passwords
    {
        "name": "password",
        "pattern": re.compile(
            r'(?i)(password|passwd|pwd)["\s:=]+[\w\S]{3,}',
            re.IGNORECASE | re.MULTILINE
        ),
        "replacement": r'\1=***REDACTED***'
    },
    # API Keys and Tokens
    {
        "name": "api_key",
        "pattern": re.compile(
            r'(?i)(api[_-]?key|apikey|token|bearer)["\s:=]+[\w\S]{10,}',
            re.IGNORECASE | re.MULTILINE
        ),
        "replacement": r'\1=***REDACTED***'
    },
    # Secrets
    {
        "name": "secret",
        "pattern": re.compile(
            r'(?i)(secret|secret[_-]?key)["\s:=]+[\w\S]{8,}',
            re.IGNORECASE | re.MULTILINE
        ),
        "replacement": r'\1=***REDACTED***'
    },
    # Private Keys (PEM format)
    {
        "name": "private_key",
        "pattern": re.compile(
            r'-----BEGIN[\s\w]+PRIVATE KEY-----[\s\S]+?-----END[\s\w]+PRIVATE KEY-----',
            re.MULTILINE
        ),
        "replacement": '-----BEGIN PRIVATE KEY-----\n***REDACTED***\n-----END PRIVATE KEY-----'
    },
    # SSH Keys
    {
        "name": "ssh_key",
        "pattern": re.compile(
            r'(ssh-rsa|ssh-dss|ssh-ed25519|ecdsa-sha2-nistp\d+)\s+[A-Za-z0-9+/=]{50,}',
            re.MULTILINE
        ),
        "replacement": r'\1 ***REDACTED***'
    },
    # AWS Access Keys
    {
        "name": "aws_access_key",
        "pattern": re.compile(
            r'(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}',
            re.MULTILINE
        ),
        "replacement": '***REDACTED_AWS_KEY***'
    },
    # AWS Secret Keys
    {
        "name": "aws_secret_key",
        "pattern": re.compile(
            r'(?i)aws[_-]?secret[_-]?access[_-]?key["\s:=]+[A-Za-z0-9/+=]{40}',
            re.IGNORECASE | re.MULTILINE
        ),
        "replacement": 'aws_secret_access_key=***REDACTED***'
    },
    # GitHub Tokens
    {
        "name": "github_token",
        "pattern": re.compile(
            r'gh[pousr]_[A-Za-z0-9_]{36,}',
            re.MULTILINE
        ),
        "replacement": '***REDACTED_GITHUB_TOKEN***'
    },
    # Generic tokens (long alphanumeric strings)
    {
        "name": "generic_token",
        "pattern": re.compile(
            r'(?i)(token|auth|authorization)["\s:=]+[A-Za-z0-9_\-\.]{32,}',
            re.IGNORECASE | re.MULTILINE
        ),
        "replacement": r'\1=***REDACTED***'
    },
    # Database connection strings
    {
        "name": "db_connection",
        "pattern": re.compile(
            r'(?i)(mysql|postgresql|mongodb|redis)://[^:]+:[^@]+@',
            re.IGNORECASE | re.MULTILINE
        ),
        "replacement": r'\1://***REDACTED***:***REDACTED***@'
    },
    # Email addresses (optional, may be needed for compliance)
    {
        "name": "email",
        "pattern": re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.MULTILINE
        ),
        "replacement": '***REDACTED_EMAIL***'
    },
    # IP addresses (private ranges only)
    {
        "name": "private_ip",
        "pattern": re.compile(
            r'\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b',
            re.MULTILINE
        ),
        "replacement": '***REDACTED_IP***'
    },
]


class SensitiveDataRedactor:
    """Redacts sensitive data from text and structured data."""

    def __init__(self, patterns: List[Dict[str, Any]] = None, enabled: bool = True):
        """
        Initialize the redactor.

        Args:
            patterns: Custom patterns to use. If None, uses default patterns.
            enabled: Whether redaction is enabled. If False, data passes through unchanged.
        """
        self.patterns = patterns if patterns is not None else SENSITIVE_PATTERNS
        self.enabled = enabled
        self.redaction_count = 0

    def redact_text(self, text: str, skip_patterns: List[str] = None) -> str:
        """
        Redact sensitive data from text.

        Args:
            text: Text to redact
            skip_patterns: List of pattern names to skip

        Returns:
            Redacted text
        """
        if not self.enabled or not text:
            return text

        skip_patterns = skip_patterns or []
        redacted = text

        for pattern_def in self.patterns:
            pattern_name = pattern_def.get("name", "")
            if pattern_name in skip_patterns:
                continue

            pattern = pattern_def.get("pattern")
            replacement = pattern_def.get("replacement", "***REDACTED***")

            if pattern:
                matches = pattern.findall(redacted)
                if matches:
                    self.redaction_count += len(matches)
                redacted = pattern.sub(replacement, redacted)

        return redacted

    def redact_dict(self, data: Dict[str, Any], skip_keys: List[str] = None) -> Dict[str, Any]:
        """
        Redact sensitive data from dictionary recursively.

        Args:
            data: Dictionary to redact
            skip_keys: List of keys to skip redaction

        Returns:
            Redacted dictionary
        """
        if not self.enabled or not isinstance(data, dict):
            return data

        skip_keys = skip_keys or []
        redacted = {}

        for key, value in data.items():
            if key in skip_keys:
                redacted[key] = value
            elif isinstance(value, str):
                redacted[key] = self.redact_text(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value, skip_keys)
            elif isinstance(value, list):
                redacted[key] = self.redact_list(value, skip_keys)
            else:
                redacted[key] = value

        return redacted

    def redact_list(self, data: List[Any], skip_keys: List[str] = None) -> List[Any]:
        """
        Redact sensitive data from list recursively.

        Args:
            data: List to redact
            skip_keys: List of keys to skip redaction in nested dicts

        Returns:
            Redacted list
        """
        if not self.enabled or not isinstance(data, list):
            return data

        skip_keys = skip_keys or []
        redacted = []

        for item in data:
            if isinstance(item, str):
                redacted.append(self.redact_text(item))
            elif isinstance(item, dict):
                redacted.append(self.redact_dict(item, skip_keys))
            elif isinstance(item, list):
                redacted.append(self.redact_list(item, skip_keys))
            else:
                redacted.append(item)

        return redacted

    def get_redaction_stats(self) -> Dict[str, int]:
        """
        Get statistics about redactions performed.

        Returns:
            Dictionary with redaction statistics
        """
        return {
            "total_redactions": self.redaction_count,
            "enabled": self.enabled,
        }

    def reset_stats(self) -> None:
        """Reset redaction statistics."""
        self.redaction_count = 0


def redact_evidence(evidence: str, enabled: bool = True) -> str:
    """
    Convenience function to redact evidence text.

    Args:
        evidence: Evidence text to redact
        enabled: Whether redaction is enabled

    Returns:
        Redacted evidence
    """
    redactor = SensitiveDataRedactor(enabled=enabled)
    return redactor.redact_text(evidence)


def redact_results(results: List[Dict[str, Any]], enabled: bool = True) -> List[Dict[str, Any]]:
    """
    Convenience function to redact audit results.

    Args:
        results: List of audit results
        enabled: Whether redaction is enabled

    Returns:
        Redacted results
    """
    redactor = SensitiveDataRedactor(enabled=enabled)
    # Skip redacting certain fields that need to remain intact
    skip_keys = ["id", "module", "severity", "status", "duration"]
    return redactor.redact_list(results, skip_keys=skip_keys)