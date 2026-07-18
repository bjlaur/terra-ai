#!/usr/bin/env bash
# Start a persistent local Ergo server for TerraAI system tests.

set -euo pipefail

ERGO_CONF="${ERGO_CONF:-${HOME}/.ircd/ircd.yaml}"
ERGO_PID_FILE="${ERGO_PID_FILE:-/tmp/terra-ai-ergo.pid}"
ERGO_LOG="${ERGO_LOG:-/tmp/terra-ai-ergo.log}"

if ! command -v ergochat >/dev/null 2>&1; then
    echo "ERROR: ergochat is not installed" >&2
    exit 1
fi
if [[ ! -f "$ERGO_CONF" ]]; then
    echo "ERROR: Ergo config not found: $ERGO_CONF" >&2
    exit 1
fi

if python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 6667), 1); s.close()" 2>/dev/null; then
    echo "Ergo is already listening on 127.0.0.1:6667"
    exit 0
fi

ergo_dir="$(dirname "$ERGO_CONF")"
(
    cd "$ergo_dir"
    nohup ergochat run --conf "$ERGO_CONF" >"$ERGO_LOG" 2>&1 &
    echo "$!" >"$ERGO_PID_FILE"
)

for _ in $(seq 1 40); do
    if python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 6667), 1); s.close()" 2>/dev/null; then
        echo "Ergo is ready on 127.0.0.1:6667 (PID $(<"$ERGO_PID_FILE"))"
        exit 0
    fi
    sleep 0.25
done

echo "ERROR: Ergo did not start; see $ERGO_LOG" >&2
"$(dirname "$0")/stopergo.sh" || true
exit 1
