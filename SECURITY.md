# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **git.upstate674@passinbox.com**

Alternatively, you can use GitHub Security Advisories:
- Go to https://github.com/alexbergh/secaudit-plus/security/advisories
- Click "Report a vulnerability"

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

Please include the following information in your report:

- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit the issue

This information will help us triage your report more quickly.

## Security Considerations

### Privilege Requirements

SecAudit+ requires elevated privileges (root/sudo) to perform many system audits. This is by design, as it needs to:

- Read system configuration files
- Execute privileged commands
- Access kernel parameters
- Inspect running processes and services

**Security Implications:**
- Always run SecAudit+ in a controlled environment
- Review audit profiles before execution
- Be aware that malicious profiles could execute arbitrary commands
- Use Docker containers for isolation when possible

### Profile Security

Audit profiles are YAML files that can execute shell commands. **Never run untrusted profiles.**

**Best Practices:**
1. Review all profiles before execution
2. Use `secaudit validate --strict` to check profile structure
3. Store profiles in version control
4. Implement code review for profile changes
5. Sign trusted profiles with GPG

### Template Injection

SecAudit+ uses Jinja2 templates for report generation. While we use safe defaults:

- Templates are loaded from the `reports/` directory only
- User input is sanitized before rendering
- Autoescape is enabled for HTML templates

**Recommendations:**
- Do not modify template loading paths
- Review custom templates for injection vulnerabilities
- Limit template modification to trusted users

### Command Injection

Profiles execute shell commands defined in YAML. Potential risks:

- **Command injection** through unsanitized variables
- **Path traversal** in file operations
- **Privilege escalation** through sudo misuse

**Mitigations:**
- Input validation on all variables
- Whitelist allowed commands where possible
- Audit logging of all executed commands
- Use `rc_ok` to validate expected return codes

### Data Exposure

Audit results may contain sensitive information:

- System configuration details
- User account information
- Network topology
- Installed software versions
- Security misconfigurations

**Recommendations:**
1. Restrict access to results directory
2. Use `--evidence` carefully (may contain sensitive data)
3. Encrypt results at rest
4. Implement access controls for report viewing
5. Sanitize reports before sharing externally

### Supply Chain Security

To ensure the integrity of SecAudit+:

1. **Verify releases:**
   ```bash
   # Verify GPG signature (when available)
   gpg --verify secaudit-1.0.0.tar.gz.asc
   
   # Check SHA256 sums
   sha256sum -c SHA256SUMS.txt
   ```

2. **Use pinned dependencies:**
   - Review `requirements.txt` for known vulnerabilities
   - Use `pip-audit` or `safety` to scan dependencies
   - Keep dependencies up to date

3. **Build from source:**
   ```bash
   git clone https://github.com/alexbergh/secaudit-plus.git
   cd secaudit-plus
   git verify-commit HEAD  # Verify signed commits
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

## Security Features

### Implemented

- YAML safe loading (no arbitrary code execution)
- JSON Schema validation for profiles
- Severity-based failure policies
- SARIF output for security scanners
- Audit logging in reports
- Timeout protection for commands
- Input sanitization for filenames

### Planned

- Profile signing and verification
- Encrypted evidence storage
- RBAC for multi-user deployments
- Audit trail for all operations
- Sandboxed command execution
- Network isolation options

## Known Security Limitations

1. **Requires Root Access**: Many checks require root privileges, increasing attack surface
2. **Command Execution**: Profiles can execute arbitrary shell commands
3. **No Sandboxing**: Commands run directly on the host system
4. **Limited Input Validation**: Variable substitution may allow injection
5. **No Encryption**: Results stored in plaintext by default

## Security Scanning

We use the following tools in our CI/CD pipeline:

- **Bandit**: Python security linter
- **Safety**: Dependency vulnerability scanner
- **CodeQL**: Semantic code analysis
- **Dependabot**: Automated dependency updates
- **yamllint**: YAML syntax and security checks

## Disclosure Policy

- We follow **responsible disclosure** principles
- Security issues are fixed in private before public disclosure
- We aim to release patches within 30 days of confirmed vulnerabilities
- CVEs will be requested for high-severity issues
- Security advisories published via GitHub Security Advisories

## Security Updates

Subscribe to security updates:

1. Watch this repository for security advisories
2. Enable GitHub security alerts
3. Subscribe to release notifications
4. Follow our security mailing list (TBD)

## Compliance

SecAudit+ helps audit systems for compliance with:

- ФСТЭК (Russian Federal Service for Technical and Export Control)
- CIS Benchmarks
- Custom organizational policies

However, **SecAudit+ itself is not certified or accredited** for any specific compliance framework.

## Contact

For security concerns, contact:
- **Email**: git.upstate674@passinbox.com
- **GitHub Security Advisories**: https://github.com/alexbergh/secaudit-plus/security/advisories
- **PGP Key**: Available on request
- **Response Time**: Within 48 hours (business days)

For general questions, use GitHub Issues or Discussions.

---

**Last Updated**: 2025-01-28  
**Version**: 1.0
