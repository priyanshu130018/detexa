#!/bin/sh
set -e

# If command is provided (e.g. worker process: python -m flink.run_job)
if [ "$1" = "python" ]; then
    echo "==> [Detexa Worker] Starting worker process: $@"
    exec "$@"
fi

# Run database migrations for the API backend server unless explicitly skipped
if [ "$SKIP_MIGRATIONS" != "true" ] && [ "$SKIP_MIGRATIONS" != "1" ]; then
    echo "==> [Detexa Startup] Checking and running database migrations (alembic upgrade head)..."
    alembic upgrade head || {
        echo "==> [Detexa Warning] Alembic migration reported non-zero status; continuing startup..."
    }
    echo "==> [Detexa Startup] Migrations check completed."
fi

if [ $# -eq 0 ]; then
    echo "==> [Detexa Startup] Launching FastAPI backend server on 0.0.0.0:8000..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
else
    echo "==> [Detexa Startup] Launching custom command: $@"
    exec "$@"
fi
