#!/usr/bin/env bash
set -euo pipefail

# Run from project root so relative paths (like sqlite:///./mpvrp_scoring.db) resolve correctly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Production-safe defaults (override with env vars).
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

# Export DATABASE_URL (uses existing value if already set).
export DATABASE_URL="${DATABASE_URL:-sqlite:///./mpvrp_scoring.db}"
export FRONTEND_ALLOWED_ORIGINS="${FRONTEND_ALLOWED_ORIGINS:-https://ifri-ai-classes.github.io,https://ifri-ai-classes.github.io/MPVRP-CC,https://ifri-ai-classes.github.io/MPVRP-CC/pages}"

# Require stable secret key in environments with external users.
# Generate and export a fresh SECRET_KEY at launch time.
export SECRET_KEY="$(python -c "import secrets; print(secrets.token_urlsafe(32))")"
if [[ -z "${SECRET_KEY:-}" ]]; then
  echo "ERROR: SECRET_KEY is required. Set it in your environment before starting the server." >&2
  exit 1
fi

exec uvicorn backup.app.main:app --host "$HOST" --port "$PORT" --workers "$WORKERS"

