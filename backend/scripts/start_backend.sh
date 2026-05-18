#!/usr/bin/env bash
set -euo pipefail

echo "Starting FastAPI backend..."
python -m app.db.init_db
uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}" --reload
