#!/bin/bash
set -euo pipefail

WORKERS=${WORKERS:-1}
WORKER_CLASS=${WORKER_CLASS:-gevent}
ACCESS_LOG=${ACCESS_LOG:--}
ERROR_LOG=${ERROR_LOG:--}
WORKER_TEMP_DIR=${WORKER_TEMP_DIR:-/dev/shm}
SECRET_KEY=${SECRET_KEY:-}
SKIP_DB_PING=${SKIP_DB_PING:-false}

# Check that a .ctfd_secret_key file or SECRET_KEY envvar is set
if [ ! -f .ctfd_secret_key ] && [ -z "$SECRET_KEY" ]; then
    if [ $WORKERS -gt 1 ]; then
        echo "[ ERROR ] You are configured to use more than 1 worker."
        echo "[ ERROR ] To do this, you must define the SECRET_KEY environment variable or create a .ctfd_secret_key file."
        echo "[ ERROR ] Exiting..."
        exit 1
    fi
fi

# Railway / PaaS: DATABASE_URL must be in the *runtime* environment. If it is empty here,
# CTFd falls back to SQLite (Alembic logs: Context impl SQLiteImpl).
if [ -z "${DATABASE_URL:-}" ]; then
  echo "[CTFd] WARNING: DATABASE_URL is empty in this process. CTFd will use SQLite, not MySQL/Postgres."
else
  echo "[CTFd] DATABASE_URL is set (dialect: ${DATABASE_URL%%://*}, length=${#DATABASE_URL} chars)"
fi
python -c "from CTFd.config import Config; u=Config.DATABASE_URL or ''; s=u.startswith('sqlite') if u else True; print('[CTFd] Resolved after config load:', 'SQLite' if s else 'non-SQLite (OK for production DB)')" || true

# Skip db ping if SKIP_DB_PING is set to a value other than false or empty string
if [[ "$SKIP_DB_PING" == "false" ]]; then
  # Ensures that the database is available
  python ping.py
fi

# Initialize database
flask db upgrade

# Start CTFd
echo "Starting CTFd"
exec gunicorn 'CTFd:create_app()' \
    --bind '0.0.0.0:8000' \
    --workers $WORKERS \
    --worker-tmp-dir "$WORKER_TEMP_DIR" \
    --worker-class "$WORKER_CLASS" \
    --access-logfile "$ACCESS_LOG" \
    --error-logfile "$ERROR_LOG"
