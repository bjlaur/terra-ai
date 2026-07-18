#!/usr/bin/env bash
# Stop the Ergo process started by startergo.sh.

set -euo pipefail

ERGO_PID_FILE="${ERGO_PID_FILE:-/tmp/terra-ai-ergo.pid}"

if [[ ! -f "$ERGO_PID_FILE" ]]; then
    echo "No TerraAI-owned Ergo process is recorded"
    exit 0
fi

pid="$(<"$ERGO_PID_FILE")"
if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    echo "ERROR: invalid Ergo PID file: $ERGO_PID_FILE" >&2
    exit 1
fi

if ! kill -0 "$pid" 2>/dev/null; then
    rm -f -- "$ERGO_PID_FILE"
    echo "Recorded Ergo process is no longer running"
    exit 0
fi

process_name="$(ps -p "$pid" -o comm= | tr -d '[:space:]')"
if [[ "$process_name" != "ergochat" ]]; then
    echo "ERROR: refusing to stop PID $pid because it is $process_name, not ergochat" >&2
    exit 1
fi

echo "Stopping Ergo (PID $pid)"
kill "$pid"
for _ in $(seq 1 20); do
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f -- "$ERGO_PID_FILE"
        echo "Ergo stopped"
        exit 0
    fi
    sleep 0.25
done

echo "ERROR: Ergo did not stop gracefully" >&2
exit 1
