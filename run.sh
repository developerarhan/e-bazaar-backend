#!/bin/sh

# Stop script execution immediately if any internal command fails
set -e

echo "==> Gathering Static Assets..."
python manage.py collectstatic --noinput

echo "==> Running Pending Database Migrations..."
python manage.py migrate --noinput

echo "==> Backgrounding Asynchronous Task Worker Engine..."
celery -A ebazaar worker --loglevel=info --pool=solo &

echo "==> Backgrounding Periodic Task Scheduler Engine..."
celery -A ebazaar beat --loglevel=info &

echo "==> Initializing Main Application HTTP Gunicorn Interface..."
gunicorn ebazaar.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -