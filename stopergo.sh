#!/bin/bash
# Stop ergochat IRC server
set -e

if ! pgrep -x ergochat >/dev/null 2>&1; then
    echo "ergochat is not running"
    exit 0
fi

PID=$(pgrep -x ergochat)
echo "Stopping ergochat (PID $PID)"
kill "$PID"

# Wait for it to die
for i in $(seq 1 10); do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "ergochat stopped"
        exit 0
    fi
    sleep 0.5
done

echo "ergochat did not stop gracefully, killing..."
kill -9 "$PID" 2>/dev/null
echo "ergochat killed"
