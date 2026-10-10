# ── Stage 1: Python Dependency Builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Upgrade pip and install prebuilt binary wheels into /install prefix
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production Runtime ───────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install curl for container health monitoring
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source code
COPY . .

# Ensure directory structure and executable permissions
RUN mkdir -p /app/logs /app/app/ml/saved && chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
