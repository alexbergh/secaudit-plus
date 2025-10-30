# Multi-stage build for SecAudit+
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy dependency files
COPY requirements.txt pyproject.toml ./
COPY requirements.lock* ./

# Install Python dependencies
# Use requirements.lock with hashes for security if available, fallback to requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f requirements.lock ]; then \
        echo "Installing from requirements.lock with hash verification..."; \
        pip install --no-cache-dir --require-hashes -r requirements.lock; \
    else \
        echo "Installing from requirements.txt (no hash verification)..."; \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Production stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # System utilities needed for audit checks
    mount \
    procps \
    net-tools \
    iproute2 \
    sudo \
    systemd \
    auditd \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for running the application
RUN groupadd -r secaudit && useradd -r -g secaudit -s /bin/bash secaudit

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=secaudit:secaudit . .

# Install the package
RUN pip install --no-cache-dir -e .

# Create results directory
RUN mkdir -p /app/results && chown -R secaudit:secaudit /app/results

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SECAUDIT_LEVEL=baseline \
    SECAUDIT_WORKERS=4

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD secaudit --info || exit 1

# Security Note: Many audit checks require root privileges or specific capabilities.
# When running in Docker/K8s, use capabilities (SYS_ADMIN, SYS_PTRACE, etc.) 
# instead of privileged mode. See docker-compose.yml and helm/values.yaml for examples.
# For production, consider running specific checks as non-root where possible.
# USER secaudit

# Default command
ENTRYPOINT ["secaudit"]
CMD ["--help"]
