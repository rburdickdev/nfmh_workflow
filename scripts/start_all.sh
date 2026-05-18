#!/usr/bin/env bash
set -euo pipefail

if [ ! -f ".env" ]; then
  echo "No .env file found. Copy .env.example to .env first."
  exit 1
fi

docker compose up --build
