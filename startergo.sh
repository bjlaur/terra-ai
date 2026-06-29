#!/bin/bash
# Start ergochat IRC server for testing
set -e

ERGO_CONF="${ERGO_CONF:-$HOME/.ircd/ircd.yaml}"

if pgrep -x ergochat >/dev/null 2>&1; then
    echo "ergochat is already running (PID $(pgrep -x ergochat))"
    exit 0
fi

ERGO_DIR="$(dirname "$ERGO_CONF")"
echo "Starting ergochat with config: $ERGO_CONF (cwd: $ERGO_DIR)"
(cd "$ERGO_DIR" && ergochat run --conf "$ERGO_CONF") &

# Wait for port 6667 to be available
for i in $(seq 1 20); do
    if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', 6667)); s.close()" 2>/dev/null; then
        echo "ergochat is ready on :6667 (PID $(pgrep -x ergochat))"
        exit 0
    fi
    sleep 0.5
done

echo "ERROR: ergochat did not start within 10 seconds"
exit 1
