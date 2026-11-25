#!/bin/sh

# Stop script execution immediately if any internal command fails
set -e

# Restrict PyTorch / OpenMP / HuggingFace thread pools to prevent memory bloat
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false

echo "==> Gathering Static Assets..."
python manage.py collectstatic --noinput

echo "==> Running Pending Database Migrations..."
python manage.py migrate --noinput

# Only start Celery background processes if explicitly enabled (paid plan / dedicated worker)
if [ "$CELERY_ENABLED" = "true" ] || [ "$CELERY_ENABLED" = "True" ] || [ "$CELERY_ENABLED" = "1" ]; then
    echo "==> Backgrounding Combined Celery Worker & Beat Engine..."
    celery -A ebazaar worker -B --loglevel=warning --pool=solo &
else
    echo "==> Free tier mode: Background Celery disabled to stay under 512MB RAM. Tasks will execute inline."
fi

echo "==> Initializing Main Application HTTP Gunicorn Interface..."
gunicorn ebazaar.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 2 \
    --max-requests 250 \
    --max-requests-jitter 25 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
