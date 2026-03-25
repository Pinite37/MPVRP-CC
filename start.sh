#!/usr/bin/env bash
set -euo pipefail

# Run from project root so relative paths (like sqlite:///./mpvrp_scoring.db) resolve correctly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Generate and export a fresh SECRET_KEY at launch time.
SECRET_KEY="$(python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))")"
export "$SECRET_KEY"

# Export DATABASE_URL (uses existing value if already set).
export DATABASE_URL="${DATABASE_URL:-sqlite:///./mpvrp_scoring.db}"

exec uvicorn backup.app.main:app --host 0.0.0.0 --port 8000 --reload

