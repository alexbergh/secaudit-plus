# Changelog

All notable changes to SecAudit+ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-28

### Added
- **Agentless audit functionality** - Execute security audits over SSH without installing on target hosts
- **Network scanning module** - Discover hosts in network segments with OS detection
- **Inventory management** - Centralized host inventory for remote audits
- **Sensitive data redaction** - Automatic redaction of passwords, API keys, secrets, private keys in reports
- **Multi-format reporting** - JSON, HTML, Markdown, SARIF, JUnit, Prometheus, Elastic NDJSON outputs
- **ФСТЭК compliance profiles** - Russian security standards (Приказ №21 от 18.02.2013)
- **CIS Benchmarks integration** - Industry-standard security baselines
- **Russian OS support** - Profiles for Astra Linux, ALT Linux, РЕД ОС
- **Secret Net LSP profile** - Security checks for Secret Net LSP SZI
- **Docker multi-platform builds** - Support for amd64 and arm64 architectures
- **Cosign image signing** - Keyless signing of Docker images with Sigstore
- **SBOM generation** - Software Bill of Materials in SPDX format
- **Helm charts** - Kubernetes deployment with security best practices
- **Pre-commit hooks** - 7 tools including gitleaks, bandit, black, flake8, mypy
- **Comprehensive test suite** - 15 test files including security and integration tests

### Changed
- **Migrated from privileged to capabilities-based security** - Docker and Kubernetes use specific capabilities instead of privileged mode
- **Improved profile inheritance** - Cascading allowlist/denylist with priorities
- **Enhanced variable system** - Severity levels (baseline/strict/paranoid) with templating support

### Security
- **Implemented sensitive data redaction module** - Prevents accidental leakage of credentials
- **Added 8 security scanners to CI/CD** - CodeQL, Semgrep, Gitleaks, TruffleHog, Bandit, Safety, Trivy, yamllint
- **Enabled seccomp profiles** - RuntimeDefault seccomp for container security
- **Configured security contexts** - Non-privileged containers with dropped capabilities
- **Added security testing** - Comprehensive security validation tests

### Fixed
- Command injection protection with input validation
- Path traversal prevention in file operations
- Secure variable substitution in Jinja2 templates

## [Unreleased]

### Planned
- SLSA provenance attestation for supply chain security
- Requirements lock file with cryptographic hashes
- API documentation with Sphinx
- Benchmark performance tests
- Falco/AppArmor/SELinux runtime security profiles
- NIST 800-53 and PCI-DSS compliance mappings

---

## Version History

- **1.0.0** (2025-01-28) - Initial stable release with agentless audit, redaction, and comprehensive security features

[1.0.0]: https://github.com/alexbergh/secaudit-plus/releases/tag/v1.0.0
[Unreleased]: https://github.com/alexbergh/secaudit-plus/compare/v1.0.0...HEAD
