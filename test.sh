#!/usr/bin/env bash
# TerraAI test entrypoint. Run without arguments for help.

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ergo_started_here=0
cd "$project_dir"

prepare_run_dir() {
    local test_mode="$1"
    local log_root="${TMPDIR:-/tmp}/terraai-tests"
    local run_stamp
    run_stamp="$(date -u +%Y%m%d-%H%M%S-%N)"
    export TERRAI_TEST_RUN_DIR="$log_root/${run_stamp}-${test_mode}-$$"
    mkdir -p "$TERRAI_TEST_RUN_DIR"
    chmod 700 "$TERRAI_TEST_RUN_DIR"
    echo "Test artifacts:  $TERRAI_TEST_RUN_DIR" >&2
}

prepare_test_logs() {
    local test_mode="$1"
    prepare_run_dir "$test_mode"
    test_output_log="$TERRAI_TEST_RUN_DIR/pytest-output.log"
    export TERRAI_PYTEST_PROGRESS_FILE="$TERRAI_TEST_RUN_DIR/progress.log"
    : > "$test_output_log"
    : > "$TERRAI_PYTEST_PROGRESS_FILE"
    chmod 600 "$test_output_log" "$TERRAI_PYTEST_PROGRESS_FILE"
    echo "Pytest output:   $test_output_log" >&2
    echo "Test progress:   $TERRAI_PYTEST_PROGRESS_FILE" >&2
    echo "Follow progress: tail -f $TERRAI_PYTEST_PROGRESS_FILE" >&2
}

run_pytest() {
    local test_mode="$1"
    local pytest_status
    local progress_reporter_pid=""
    shift
    prepare_test_logs "$test_mode"

    if [[ "${TERRAI_TEST_LIVE_PROGRESS:-0}" == "1" ]]; then
        python3 -m tests.progress_reporter \
            "$TERRAI_PYTEST_PROGRESS_FILE" \
            --heartbeat-seconds "${TERRAI_TEST_HEARTBEAT_SECONDS:-15}" &
        progress_reporter_pid=$!
    fi

    set +e
    python3 -m pytest "$@" 2>&1 | tee "$test_output_log"
    pytest_status=${PIPESTATUS[0]}
    set -e

    if [[ -n "$progress_reporter_pid" ]]; then
        kill -TERM "$progress_reporter_pid" 2>/dev/null || true
        wait "$progress_reporter_pid" 2>/dev/null || true
    fi

    return "$pytest_status"
}

usage() {
    cat <<'EOF'
Usage: ./test.sh MODE [pytest arguments]

Modes:
  fast   Complete deterministic offline suite; does not load .env
  real   Shared plugin E2E scenarios using real external services
  ergo   Start Ergo, run always-real IRC/SOPEL system tests, then stop Ergo
  manual Start the Ergo/SOPEL system-test bot for interactive irssi testing
  all    Run fast, real, and Ergo in order

Real and Ergo tests accept --model MODEL.
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
    local had_test_model=0 old_test_model=""
    local had_benchmark_output=0 old_benchmark_output=""
    local had_provider_rpm=0 old_provider_rpm=""
    local had_provider_min_interval=0 old_provider_min_interval=""
    local had_live_progress=0 old_live_progress=""
    if [[ -v OPENROUTER_API_KEY ]]; then had_key=1; old_key="$OPENROUTER_API_KEY"; fi
    if [[ -v TERRAI_TEST_TIMEOUT ]]; then had_timeout=1; old_timeout="$TERRAI_TEST_TIMEOUT"; fi
    if [[ -v ERGO_CONF ]]; then had_ergo_conf=1; old_ergo_conf="$ERGO_CONF"; fi
    if [[ -v TERRAI_TEST_MODEL ]]; then had_test_model=1; old_test_model="$TERRAI_TEST_MODEL"; fi
    if [[ -v TERRAI_BENCHMARK_OUTPUT ]]; then had_benchmark_output=1; old_benchmark_output="$TERRAI_BENCHMARK_OUTPUT"; fi
    if [[ -v TERRAI_TEST_PROVIDER_RPM ]]; then had_provider_rpm=1; old_provider_rpm="$TERRAI_TEST_PROVIDER_RPM"; fi
    if [[ -v TERRAI_TEST_PROVIDER_MIN_INTERVAL ]]; then had_provider_min_interval=1; old_provider_min_interval="$TERRAI_TEST_PROVIDER_MIN_INTERVAL"; fi
    if [[ -v TERRAI_TEST_LIVE_PROGRESS ]]; then had_live_progress=1; old_live_progress="$TERRAI_TEST_LIVE_PROGRESS"; fi

    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a

    if (( had_key )); then export OPENROUTER_API_KEY="$old_key"; fi
    if (( had_timeout )); then export TERRAI_TEST_TIMEOUT="$old_timeout"; fi
    if (( had_ergo_conf )); then export ERGO_CONF="$old_ergo_conf"; fi
    if (( had_test_model )); then export TERRAI_TEST_MODEL="$old_test_model"; fi
    if (( had_benchmark_output )); then export TERRAI_BENCHMARK_OUTPUT="$old_benchmark_output"; fi
    if (( had_provider_rpm )); then export TERRAI_TEST_PROVIDER_RPM="$old_provider_rpm"; fi
    if (( had_provider_min_interval )); then export TERRAI_TEST_PROVIDER_MIN_INTERVAL="$old_provider_min_interval"; fi
    if (( had_live_progress )); then export TERRAI_TEST_LIVE_PROGRESS="$old_live_progress"; fi
    if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
        echo "ERROR: OPENROUTER_API_KEY is not set in the environment or .env" >&2
        exit 1
    fi
}

run_fast() {
    run_pytest fast "$@"
}

run_real() {
    load_test_env
    run_pytest real --real -m "e2e and not mock" "$@"
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
    local has_test_selector=0
    local argument
    for argument in "$@"; do
        if [[ "$argument" == *"::"* || "$argument" == *.py || \
              "$argument" == tests/* || "$argument" == ./tests/* ]]; then
            has_test_selector=1
            break
        fi
    done
    if (( has_test_selector )); then
        run_pytest ergo --ergo "$@"
    else
        run_pytest ergo --ergo tests/test_ergo.py "$@"
    fi
    cleanup_ergo
    trap - EXIT
}

run_manual() {
    load_test_env
    prepare_run_dir manual
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
