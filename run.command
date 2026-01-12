#!/bin/bash
set -e
cd "$(dirname "$0")"

# Default ASGI module (change to your app module: e.g. mypkg.app:app)
APP_MODULE="${APP_MODULE:-ppt_agent.app:app}"
PORT="${PORT:-8000}"
# If you prefer to use the project's `adk` CLI, leave USE_ADK=1 (default). Set to 0 to force uvicorn.
USE_ADK="${USE_ADK:-1}"

# Create/activate virtualenv
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r ppt_agent/requirements.txt
fi

echo "Environment: APP_MODULE=$APP_MODULE PORT=$PORT USE_ADK=$USE_ADK"

# If `adk` is available and enabled, prefer it (it may initialize extra environment or tooling your project needs).
if command -v adk >/dev/null 2>&1 && [ "$USE_ADK" = "1" ]; then
    echo "Found 'adk' in PATH — starting adk web in background"
    adk web &
    SERVER_PID=$!
else
    echo "adk not found or disabled; starting uvicorn $APP_MODULE on http://localhost:$PORT"
    # Run uvicorn as fallback in background. Remove --reload for production use.
    uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$PORT" --reload &
    SERVER_PID=$!
fi

# Wait up to ~5s for the server to respond, then open the default browser. Falls back to opening regardless after the loop.
echo "Waiting for server to become available on http://127.0.0.1:$PORT ..."
for i in {1..50}; do
    if curl -sSf "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
        break
    fi
    sleep 0.1
done

echo "Opening http://127.0.0.1:$PORT in the default browser"
open "http://127.0.0.1:$PORT"

# Wait for the server process so the terminal stays open and shows logs
wait $SERVER_PID