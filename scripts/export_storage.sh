#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "No .env file found. Copy .env.example to .env first."
  exit 1
fi

DEFAULT_OUTPUT_DIR="./exports/storage_export_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${1:-${DEFAULT_OUTPUT_DIR}}"
mkdir -p "${OUTPUT_DIR}"
ABS_OUTPUT_DIR="$(cd "$(dirname "${OUTPUT_DIR}")" && pwd)/$(basename "${OUTPUT_DIR}")"

echo "Exporting storage artifacts to: ${ABS_OUTPUT_DIR}"
echo "This may take a moment for larger media files..."

docker compose run --rm --no-deps -v "${ABS_OUTPUT_DIR}:/export" backend bash -lc '
set -euo pipefail

STORAGE_ROOT="${STORAGE_PATH:-/storage}"
mkdir -p /export

for subdir in uploads clips transcripts captions; do
  if [ -d "${STORAGE_ROOT}/${subdir}" ]; then
    cp -a "${STORAGE_ROOT}/${subdir}" "/export/${subdir}"
    echo "Copied ${subdir}"
  else
    echo "Skipping ${subdir} (not found)"
  fi
done
'

echo "Export complete."
