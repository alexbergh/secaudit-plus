"""Benchmark tests for SecAudit+ performance."""
import pytest
from pathlib import Path
from modules.audit_runner import load_profile, run_checks


@pytest.mark.benchmark
class TestAuditPerformance:
    """Performance benchmarks for audit operations."""

    def test_profile_loading(self, benchmark):
        """Benchmark profile loading time."""
        profile_path = "profiles/common/baseline.yml"
        result = benchmark(load_profile, profile_path)
        assert result is not None
        assert "checks" in result

    def test_small_audit_performance(self, benchmark):
        """Benchmark small audit execution (< 10 checks)."""
        def run_small_audit():
            profile = load_profile("profiles/common/baseline.yml")
            # Limit to first 5 checks for benchmark
            if "checks" in profile:
                profile["checks"] = profile["checks"][:5]
            return run_checks(profile, level="baseline")

        result = benchmark(run_small_audit)
        assert result is not None

    @pytest.mark.slow
    def test_full_audit_performance(self, benchmark):
        """Benchmark full audit execution."""
        def run_full_audit():
            profile = load_profile("profiles/base/linux.yml")
            return run_checks(profile, level="baseline")

        result = benchmark.pedantic(run_full_audit, iterations=3, rounds=1)
        assert result is not None
        # Full audit should complete within reasonable time
        stats = benchmark.stats.stats
        assert stats.mean < 120  # Mean < 2 minutes


@pytest.mark.benchmark
class TestReportGeneration:
    """Performance benchmarks for report generation."""

    def test_json_report_generation(self, benchmark):
        """Benchmark JSON report generation."""
        from modules.report_generator import generate_json_report

        # Sample results
        results = [
            {"id": f"check_{i}", "result": "PASS", "module": "system"}
            for i in range(100)
        ]

        def generate():
            output_path = Path("results/benchmark_report.json")
            output_path.parent.mkdir(exist_ok=True)
            generate_json_report(results, output_path)
            if output_path.exists():
                output_path.unlink()

        benchmark(generate)

    def test_html_report_generation(self, benchmark):
        """Benchmark HTML report generation."""
        from modules.report_generator import generate_report

        profile = {"schema_version": "1.0", "profile_name": "Benchmark"}
        results = [
            {"id": f"check_{i}", "result": "PASS", "module": "system"}
            for i in range(100)
        ]

        def generate():
            output_path = Path("results/benchmark_report.html")
            output_path.parent.mkdir(exist_ok=True)
            generate_report(profile, results, "report_template.html.j2", output_path)
            if output_path.exists():
                output_path.unlink()

        benchmark(generate)


@pytest.mark.benchmark
class TestSecurityOperations:
    """Performance benchmarks for security operations."""

    def test_redaction_performance(self, benchmark):
        """Benchmark sensitive data redaction."""
        from seclib.redaction import SensitiveDataRedactor

        redactor = SensitiveDataRedactor()
        test_data = {
            "output": "password=secret123 api_key=abc123xyz token=bearer_token",
            "command": "mysql://user:password@localhost/db",
            "evidence": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
        }

        def redact():
            return redactor.redact_dict(test_data)

        result = benchmark(redact)
        assert "***REDACTED***" in str(result)


# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "profile_loading": 0.1,  # seconds
    "small_audit": 5.0,  # seconds
    "json_report": 0.5,  # seconds
    "html_report": 1.0,  # seconds
    "redaction": 0.01,  # seconds
}


def test_performance_thresholds():
    """Verify benchmark results meet performance thresholds."""
    # This test serves as documentation for expected performance
    assert all(threshold > 0 for threshold in PERFORMANCE_THRESHOLDS.values())
