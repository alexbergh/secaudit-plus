# Changelog

All notable changes to SecAudit+ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Replaced `privileged: true` with specific Linux capabilities in Docker and Kubernetes
- Added Network Policy templates for Kubernetes deployments
- Implemented sensitive data redaction module for reports
- Updated security contact email to security@alexbergh.com

### Changed
- Corrected license information to Apache-2.0 in CONTRIBUTING.md
- Enhanced Dockerfile security comments with capability recommendations
- Improved securityContext in Helm values with CIS Kubernetes Benchmark compliance

### Added
- CHANGELOG.md for version tracking
- Network Policy templates for Kubernetes
- Sensitive data redaction functionality
- GitHub Security Advisories as vulnerability reporting channel
- Seccomp profile (RuntimeDefault) in Kubernetes deployments

## [1.0.0] - 2025-01-28

### Added
- Initial stable release of SecAudit+
- CLI tool for security auditing of GNU/Linux systems
- YAML-based audit profiles with inheritance support
- Support for ФСТЭК, CIS Benchmarks, and custom policies
- Multiple report formats: JSON, Markdown, HTML, SARIF, JUnit, Prometheus, Elastic NDJSON
- Docker and Kubernetes deployment support with Helm chart
- Prometheus metrics and Grafana dashboards
- Integration examples for CI/CD (GitHub Actions, GitLab CI)
- Ansible and SaltStack integration guides
- 24+ YAML profile files with 500+ security checks

### Security Features
- CodeQL static analysis integration
- Semgrep SAST scanning with security-extended queries
- Gitleaks and TruffleHog secret scanning
- Bandit Python security linting
- Safety dependency vulnerability scanning
- Trivy container image scanning
- Cosign container image signing
- SBOM generation (SPDX format)
- Dependabot automated dependency updates

### Profiles
- Base profiles: linux, server, workstation
- OS-specific profiles: ALT, Astra, CentOS, Debian, RED OS, Ubuntu
- Role-based profiles: database, kiosk, workstation
- Compliance profiles: Secret Net LSP, ФСТЭК, CIS Benchmarks
- 500+ individual security checks across all profiles

### Documentation
- Comprehensive README with quick start guide (340 lines)
- SECURITY.md with vulnerability reporting process (211 lines)
- CONTRIBUTING.md with development guidelines
- Deployment guide for Docker and Kubernetes
- User guide with CLI reference
- RBAC configuration guide
- Encryption setup guide
- Code signing documentation

### CI/CD
- GitHub Actions workflows for CI, release, and Docker publishing
- Automated testing with pytest and coverage reporting
- Multi-platform Docker builds (amd64, arm64)
- Automated release creation with checksums
- Pre-commit hooks for code quality (7 tools)

### Monitoring
- Prometheus ServiceMonitor for metrics collection
- Grafana dashboard with 6 visualization panels
- Prometheus alerting rules for critical events
- Elasticsearch/Logstash export support

## [0.9.0] - 2024-12-15

### Added
- Beta release for testing
- Core audit engine implementation
- Profile validation and inheritance system
- Report generation with Jinja2 templates
- Basic Docker support

### Changed
- Refactored CLI argument parsing
- Improved error handling and logging

### Fixed
- Profile inheritance bugs
- Template rendering issues

## [0.5.0] - 2024-11-01

### Added
- Alpha release
- Proof of concept implementation
- Basic YAML profile support
- Simple report generation
- Command-line interface

---

## Release Notes

### Version 1.0.0 Highlights

SecAudit+ 1.0.0 is the first stable release, providing a production-ready security auditing tool for GNU/Linux systems. Key features include:

- **Comprehensive Coverage**: 500+ security checks across system, network, services, and containers
- **Flexible Profiles**: YAML-based profiles with inheritance and Jinja2 templating
- **Enterprise Ready**: Kubernetes support with Helm charts, RBAC, and monitoring
- **CI/CD Integration**: SARIF and JUnit exports for automated pipelines
- **Security First**: Multiple scanning tools, container signing, and SBOM generation

### Upgrade Notes

#### From 0.9.x to 1.0.0

1. **Python Version**: Ensure Python 3.10+ is installed
2. **Dependencies**: Run `pip install -e .` to update dependencies
3. **Profiles**: No breaking changes in profile format
4. **CLI**: All commands remain backward compatible
5. **Docker**: Rebuild images with `docker build -t secaudit-plus:latest .`
6. **Security**: Update to use capabilities instead of privileged mode

#### Breaking Changes

None in this release.

### Known Issues

- Some checks require root privileges or specific capabilities
- Evidence collection may include sensitive data (use `--evidence` carefully)
- Large audit runs (1000+ checks) may take several minutes
- Privileged mode deprecated in favor of capabilities (see docker-compose.yml)

### Deprecation Notices

- **Privileged mode**: Deprecated in favor of specific capabilities. Will be removed in 2.0.0
- Support for Python 3.9 will be evaluated based on community feedback

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## Security

See [SECURITY.md](SECURITY.md) for information on reporting security vulnerabilities.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.