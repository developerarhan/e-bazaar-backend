# Stage 1: Base Image Setup
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system compilation packages safely
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY requirements-test.txt* .
RUN if [ -f requirements-test.txt ]; then pip install -r requirements-test.txt; fi

# Copy project files
COPY . .

# Generate the logging folder context safely
RUN mkdir -p logs

# Configure a low-privilege system user account context for safety
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser

# Give ownership of files to the non-root execution application user
RUN chown -R appuser:appgroup /app

# Make sure our orchestration launch manager script is safely flagged executable
RUN chmod +x /app/run.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit

# Default command falls back onto your production process layout manager shell script
CMD ["/bin/sh", "run.sh"]