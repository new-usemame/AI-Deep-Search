#!/bin/bash
set -e

# Get port from environment variable, default to 8000
PORT=${PORT:-8000}

# Start uvicorn with the port
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
