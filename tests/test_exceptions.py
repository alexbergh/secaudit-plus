"""Tests for custom exceptions."""
import pytest
from secaudit.exceptions import MissingDependencyError


def test_missing_dependency_error_basic():
    """Test basic MissingDependencyError creation."""
    error = MissingDependencyError(package="test-package")
    assert "test-package" in str(error)
    assert error.package == "test-package"


def test_missing_dependency_error_with_import_name():
    """Test MissingDependencyError with import name."""
    error = MissingDependencyError(
        package="PyYAML",
        import_name="yaml"
    )
    assert "PyYAML" in str(error)
    assert "yaml" in str(error)
    assert error.import_name == "yaml"


def test_missing_dependency_error_with_instructions():
    """Test MissingDependencyError with installation instructions."""
    error = MissingDependencyError(
        package="pytest",
        instructions="pip install pytest"
    )
    assert "pytest" in str(error)
    assert "pip install pytest" in str(error)


def test_missing_dependency_error_with_original():
    """Test MissingDependencyError with original exception."""
    original = ImportError("No module named 'test'")
    error = MissingDependencyError(
        package="test",
        original=original
    )
    assert error.original is original


def test_missing_dependency_error_inheritance():
    """Test that MissingDependencyError inherits from RuntimeError."""
    error = MissingDependencyError(package="test")
    assert isinstance(error, RuntimeError)
    assert isinstance(error, Exception)
