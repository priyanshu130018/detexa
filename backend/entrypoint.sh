#!/bin/sh
set -e

if [ "$1" = "python" ]; then
    echo "==> [Detexa Worker] Starting worker process: $@"
    exec "$@"
fi

echo "==> [Detexa Startup] Running database migrations (alembic upgrade head)..."
alembic upgrade head
echo "==> [Detexa Startup] Migrations completed successfully."

if [ $# -eq 0 ]; then
    echo "==> [Detexa Startup] Launching FastAPI backend server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
else
    echo "==> [Detexa Startup] Launching: $@"
    exec "$@"
fi
