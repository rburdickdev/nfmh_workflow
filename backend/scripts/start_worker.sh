#!/usr/bin/env bash
set -euo pipefail

echo "Starting Celery worker..."
python -m app.db.init_db
# IMPORTANT:
# Tasks are routed to the "uploads" queue in celery_app.py.
# The worker must subscribe to that queue or uploads will appear "stuck".
celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=1 --queues=uploads,celery
