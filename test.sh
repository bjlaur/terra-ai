#!/usr/bin/env bash
# TerraAI test entrypoint. Run without arguments for help.

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ergo_started_here=0
cd "$project_dir"

usage() {
    cat <<'EOF'
Usage: ./test.sh MODE [pytest arguments]

Modes:
  fast   Complete deterministic offline suite; does not load .env
  real   Shared plugin E2E scenarios using real external services
  ergo   Start Ergo, run always-real IRC/SOPEL system tests, then stop Ergo
  manual Start the Ergo/SOPEL system-test bot for interactive irssi testing
  all    Run fast, real, and Ergo in order
EOF
}

load_test_env() {
    local env_file="$project_dir/.env"
    if [[ ! -f "$env_file" ]]; then
        echo "ERROR: $env_file is required for real-service tests" >&2
        exit 1
    fi

    local had_key=0 old_key=""
    local had_timeout=0 old_timeout=""
    local had_ergo_conf=0 old_ergo_conf=""
    if [[ -v OPENROUTER_API_KEY ]]; then had_key=1; old_key="$OPENROUTER_API_KEY"; fi
    if [[ -v TERRAI_TEST_TIMEOUT ]]; then had_timeout=1; old_timeout="$TERRAI_TEST_TIMEOUT"; fi
    if [[ -v ERGO_CONF ]]; then had_ergo_conf=1; old_ergo_conf="$ERGO_CONF"; fi

    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a

    if (( had_key )); then export OPENROUTER_API_KEY="$old_key"; fi
    if (( had_timeout )); then export TERRAI_TEST_TIMEOUT="$old_timeout"; fi
    if (( had_ergo_conf )); then export ERGO_CONF="$old_ergo_conf"; fi
    if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
        echo "ERROR: OPENROUTER_API_KEY is not set in the environment or .env" >&2
        exit 1
    fi
}

run_fast() {
    python3 -m pytest "$@"
}

run_real() {
    load_test_env
    python3 -m pytest --real -m "e2e and not mock" "$@"
}

ergo_is_running() {
    python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 6667), 1); s.close()" 2>/dev/null
}

cleanup_ergo() {
    if (( ergo_started_here )); then
        "$project_dir/stopergo.sh"
        ergo_started_here=0
    fi
}

run_ergo() {
    load_test_env
    if ! ergo_is_running; then
        "$project_dir/startergo.sh"
        ergo_started_here=1
    fi

    trap cleanup_ergo EXIT
    python3 -m pytest --ergo tests/test_ergo.py "$@"
    cleanup_ergo
    trap - EXIT
}

run_manual() {
    load_test_env
    if ! ergo_is_running; then
        "$project_dir/startergo.sh"
        ergo_started_here=1
    fi
    trap cleanup_ergo EXIT
    python3 -m tests.manual_sopel "$@"
    cleanup_ergo
    trap - EXIT
}

mode="${1:-}"
if [[ -z "$mode" || "$mode" == "help" || "$mode" == "--help" || "$mode" == "-h" ]]; then
    usage
    exit 0
fi
shift

case "$mode" in
    fast) run_fast "$@" ;;
    real) run_real "$@" ;;
    ergo) run_ergo "$@" ;;
    manual) run_manual "$@" ;;
    all)
        run_fast "$@"
        run_real "$@"
        run_ergo "$@"
        ;;
    *)
        echo "ERROR: unknown test mode: $mode" >&2
        usage >&2
        exit 2
        ;;
esac
