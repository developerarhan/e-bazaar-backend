# Stage 1: Base Image Setup
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

# Install system compilation packages safely
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Install Python dependencies
COPY requirements.txt .

# Install CPU-only PyTorch first (avoids NVIDIA CUDA dependencies)
RUN pip install torch==2.5.1 \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining application dependencies
RUN pip install -r requirements.txt

COPY requirements-test.txt* .
RUN if [ -f requirements-test.txt ]; then pip install -r requirements-test.txt; fi

# Copy project files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Create a low-privilege application user
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser

# Create writable directories for the application and Hugging Face cache
RUN mkdir -p /home/appuser/.cache/huggingface \
    && chown -R appuser:appgroup /home/appuser \
    && chown -R appuser:appgroup /app

# Make the startup script executable
RUN chmod +x /app/run.sh

# Run the application as a non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

CMD ["/bin/sh", "run.sh"]
