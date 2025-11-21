# Requirements Lock File Generation

## Overview

The `requirements.lock` file provides supply chain security by pinning exact dependency versions with cryptographic hashes.

## Prerequisites

```bash
pip install pip-tools
```

## Generate requirements.lock

```bash
# From project root
pip-compile --generate-hashes --output-file=requirements.lock requirements.txt
```

This will:
1. Resolve all dependencies and sub-dependencies
2. Download packages from PyPI
3. Generate SHA256 hashes for each package
4. Create `requirements.lock` with pinned versions

## Verify Installation

```bash
# Install with hash verification
pip install --require-hashes -r requirements.lock
```

## Update Dependencies

```bash
# Upgrade all dependencies to latest compatible versions
pip-compile --generate-hashes --upgrade --output-file=requirements.lock requirements.txt
```

## Automated Updates

The GitHub Actions workflow `.github/workflows/update-dependencies.yml` automatically:
- Runs weekly on Monday
- Generates updated requirements.lock
- Creates pull request for review

## Why Hashes?

Cryptographic hashes prevent:
- **Dependency confusion attacks** - substituting malicious packages
- **Supply chain compromises** - tampering with packages in transit
- **Version drift** - unexpected package updates

## Security Note

⚠️ **Never commit requirements.lock without verifying hashes**

Always review dependency changes before merging PRs from automated updates.

## Dockerfile Support

The Dockerfile automatically uses requirements.lock if present:

```dockerfile
RUN if [ -f requirements.lock ]; then \
        pip install --require-hashes -r requirements.lock; \
    else \
        pip install -r requirements.txt; \
    fi
```

Until requirements.lock is generated, Dockerfile will use requirements.txt.

## First-Time Setup

```bash
# 1. Install pip-tools
pip install pip-tools

# 2. Generate lock file
pip-compile --generate-hashes --output-file=requirements.lock requirements.txt

# 3. Test installation
pip install --require-hashes -r requirements.lock

# 4. Commit
git add requirements.lock
git commit -m "chore: add requirements.lock with verified hashes"
```

## Troubleshooting

### Error: "Hash mismatch"
- PyPI package was updated
- Run `pip-compile` again to regenerate hashes

### Error: "No matching distribution"
- Package not available for your platform
- Check Python version compatibility
- Review `requires-python` in pyproject.toml

### Error: "Cannot verify hashes"
- requirements.lock contains invalid hashes
- Delete and regenerate: `rm requirements.lock && pip-compile --generate-hashes ...`
