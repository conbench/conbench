#!/usr/bin/env bash
set -euo pipefail

umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT_DIR="${CONBENCH_PROD_CLONE_OUT_DIR:-var/prod-clone-compat}"
PORT="${CONBENCH_PROD_CLONE_PORT:-18080}"
ADDR="127.0.0.1:${PORT}"
BASE_URL="http://${ADDR}"
SERVER_LOG="${OUT_DIR}/server.log"
REPORT_PATH="${OUT_DIR}/compat-report.md"
SERVER_PID=""
REPORT_RENDERED=0
HELPER_READY=0
PROD_CLONE_HELPER=(./bin/conbench admin prod-clone)
FAILURES=0
PROFILE=0

usage() {
	cat <<'EOF'
usage: scripts/prod_clone_compat.sh [--profile] [--help]

Runs the opt-in read-only compatibility harness against a production clone.

Required environment:
  CONBENCH_PROD_CLONE_DB_URL=postgresql://<read-only-role>@<clone-host>:<port>/<clone-database>
  CONBENCH_PROD_CLONE_CONFIRM=read-only
  CONBENCH_PROD_CLONE_READONLY_ROLE=<read-only-role>

Development dry run:
  CONBENCH_PROD_CLONE_ALLOW_DEV_ROLE=true permits the documented development
  role while the dedicated read-only role is being prepared.

Optional environment:
  CONBENCH_PROD_CLONE_EXPECTED_HOSTS=<clone-host>,<server-reported-address>
  CONBENCH_PROD_CLONE_PORT=18080
  CONBENCH_PROD_CLONE_OUT_DIR=var/prod-clone-compat

Options:
  --profile   collect serial HTTP timings, SQL timings, EXPLAIN plans, and relation sizes
EOF
}

die() {
	echo "prod_clone_compat: $*" >&2
	exit 1
}

require_tool() {
	local name="$1"
	command -v "$name" >/dev/null 2>&1 || die "$name is required"
}

prepare_private_file() {
	local path="$1"
	local dir
	dir="$(dirname "$path")"
	mkdir -p "$dir"
	if [ -e "$path" ]; then
		chmod 0600 "$path"
	fi
	: >"$path"
	chmod 0600 "$path"
}

cleanup() {
	local status="$?"
	set +e
	stop_server
	if [ "$status" -ne 0 ]; then
		finalize_failure_artifacts
		echo "==> prod clone compatibility FAILED (status ${status})" >&2
		if [ -f "$SERVER_LOG" ]; then
			echo "--- conbench serve log (tail) ---" >&2
			tail -n 80 "$SERVER_LOG" >&2 2>/dev/null || true
		fi
		if [ "$REPORT_RENDERED" -eq 1 ]; then
			echo "--- compatibility report: ${REPORT_PATH} ---" >&2
		else
			echo "--- compatibility report was not generated for this run ---" >&2
		fi
	fi
	exit "$status"
}

finalize_failure_artifacts() {
	if [ "$HELPER_READY" -ne 1 ]; then
		return
	fi
	if [ -f "$SERVER_LOG" ]; then
		"${PROD_CLONE_HELPER[@]}" log-scan --log "$SERVER_LOG" --out "$OUT_DIR" >/dev/null 2>&1 || true
	fi
	"${PROD_CLONE_HELPER[@]}" report --out "$OUT_DIR" >/dev/null 2>&1 || true
	if [ -f "$REPORT_PATH" ]; then
		REPORT_RENDERED=1
	fi
}

stop_server() {
	if [ -n "$SERVER_PID" ]; then
		kill "$SERVER_PID" >/dev/null 2>&1 || true
		wait "$SERVER_PID" >/dev/null 2>&1 || true
		SERVER_PID=""
	fi
}

wait_for_ping() {
	for _ in $(seq 1 60); do
		if curl -fsS "${BASE_URL}/api/ping" >/dev/null 2>&1; then
			return 0
		fi
		if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
			die "conbench serve exited before /api/ping became ready"
		fi
		sleep 1
	done
	curl -fsS "${BASE_URL}/api/ping" >/dev/null
}

json_probe_line() {
	local surface="$1"
	local name="$2"
	local operation="$3"
	local passed="$4"
	local error="$5"

	jq -cn \
		--arg surface "$surface" \
		--arg name "$name" \
		--arg operation "$operation" \
		--argjson passed "$passed" \
		--arg error "$error" \
		'{
			surface: $surface,
			name: $name,
			operation: $operation,
			passed: $passed
		} + (if $error == "" then {} else {error: $error} end)'
}

finalize_probe_artifact() {
	local server_url="$1"
	local jsonl="$2"
	local out="$3"

	if [ -e "$out" ]; then
		chmod 0600 "$out"
	fi
	jq -s --arg server_url "$server_url" \
		'{server_url: $server_url, passed: all(.[]; .passed == true), probes: .}' \
		"$jsonl" >"$out"
	chmod 0600 "$out"
}

run_cli_result_get() {
	local result_id="$1"
	local jsonl="$2"
	local output rc error

	set +e
	output="$(./bin/conbench results get "$result_id" --server "$BASE_URL" 2>/dev/null)"
	rc="$?"
	set -e

	error=""
	if [ "$rc" -ne 0 ]; then
		error="command exited ${rc}"
	elif ! printf '%s' "$output" | jq -e --arg id "$result_id" '.id == $id' >/dev/null; then
		error="JSON validation failed"
	fi

	if [ -n "$error" ]; then
		json_probe_line "CLI" "conbench results get" "results get" false "$error" >>"$jsonl"
		FAILURES=1
		return
	fi
	json_probe_line "CLI" "conbench results get" "results get" true "" >>"$jsonl"
}

run_cli_series_list() {
	local fingerprint="$1"
	local jsonl="$2"
	local output rc error

	set +e
	output="$(./bin/conbench series list --server "$BASE_URL" --fingerprint "$fingerprint" --page-size 5 2>/dev/null)"
	rc="$?"
	set -e

	error=""
	if [ "$rc" -ne 0 ]; then
		error="command exited ${rc}"
	elif ! printf '%s' "$output" | jq -e --arg fp "$fingerprint" \
		'.series | type == "array" and length >= 1 and all(.[]; .history_fingerprint == $fp)' >/dev/null; then
		error="JSON validation failed"
	fi

	if [ -n "$error" ]; then
		json_probe_line "CLI" "conbench series list" "series list" false "$error" >>"$jsonl"
		FAILURES=1
		return
	fi
	json_probe_line "CLI" "conbench series list" "series list" true "" >>"$jsonl"
}

run_cli_compare() {
	local baseline_id="$1"
	local contender_id="$2"
	local jsonl="$3"
	local output rc error

	set +e
	output="$(./bin/conbench compare "$baseline_id" "$contender_id" --server "$BASE_URL" 2>/dev/null)"
	rc="$?"
	set -e

	error=""
	if [ "$rc" -ne 0 ]; then
		error="command exited ${rc}"
	elif ! printf '%s' "$output" | jq -e --arg baseline "$baseline_id" --arg contender "$contender_id" \
		'.baseline.benchmark_result_id == $baseline and .contender.benchmark_result_id == $contender' >/dev/null; then
		error="JSON validation failed"
	fi

	if [ -n "$error" ]; then
		json_probe_line "CLI" "conbench compare" "compare" false "$error" >>"$jsonl"
		FAILURES=1
		return
	fi
	json_probe_line "CLI" "conbench compare" "compare" true "" >>"$jsonl"
}

run_sdk_smoke() {
	local result_id="$1"
	local fingerprint="$2"
	local baseline_id="$3"
	local contender_id="$4"
	local jsonl="$5"
	local rc

	set +e
	(
		cd sdk/python || exit 1
		CONBENCH_SERVER_URL="$BASE_URL" \
			CONBENCH_RESULT_ID="$result_id" \
			CONBENCH_HISTORY_FINGERPRINT="$fingerprint" \
			CONBENCH_BASELINE_RESULT_ID="$baseline_id" \
			CONBENCH_CONTENDER_RESULT_ID="$contender_id" \
			uv run pytest -q tests/test_smoke.py >/dev/null
	)
	rc="$?"
	set -e

	if [ "$rc" -ne 0 ]; then
		json_probe_line "SDK" "pytest sdk smoke" "uv run pytest -q tests/test_smoke.py" false "command exited ${rc}" >>"$jsonl"
		FAILURES=1
		return
	fi
	json_probe_line "SDK" "pytest sdk smoke" "uv run pytest -q tests/test_smoke.py" true "" >>"$jsonl"
}

selected_result_sample() {
	jq -r '
		def category(name): .categories[name] // {};
		([category("recent_result"), category("long_history"), category("short_history")] + [.categories[]?])
		| map(select((.result_id // "") != "" and (.history_fingerprint // "") != ""))
		| .[0] // {}
		| [.result_id // "", .history_fingerprint // ""]
		| @tsv
	' "$1"
}

trap cleanup EXIT

for arg in "$@"; do
	case "$arg" in
	-h | --help)
		usage
		exit 0
		;;
	--profile)
		PROFILE=1
		;;
	*)
		usage >&2
		exit 2
		;;
	esac
done

[ -n "${CONBENCH_PROD_CLONE_DB_URL:-}" ] || die "CONBENCH_PROD_CLONE_DB_URL must be set"
[ "${CONBENCH_PROD_CLONE_CONFIRM:-}" = "read-only" ] || die "CONBENCH_PROD_CLONE_CONFIRM must equal read-only"
if [ "${CONBENCH_PROD_CLONE_ALLOW_DEV_ROLE:-}" != "true" ] && [ -z "${CONBENCH_PROD_CLONE_READONLY_ROLE:-}" ]; then
	die "CONBENCH_PROD_CLONE_READONLY_ROLE must be set unless CONBENCH_PROD_CLONE_ALLOW_DEV_ROLE=true"
fi

require_tool jq
require_tool curl
require_tool uv

mkdir -p "$OUT_DIR/timings"

preflight_args=(--out "$OUT_DIR")
if [ "${CONBENCH_PROD_CLONE_ALLOW_DEV_ROLE:-}" = "true" ]; then
	preflight_args+=(--allow-dev-role)
fi

echo "==> build binaries"
make build
HELPER_READY=1

echo "==> preflight target"
"${PROD_CLONE_HELPER[@]}" preflight "${preflight_args[@]}"

SAFE_DB_URL="$("${PROD_CLONE_HELPER[@]}" safe-db-url)"

echo "==> verify ${BASE_URL} is free"
if curl -fsS "${BASE_URL}/api/ping" >/dev/null 2>&1; then
	die "port ${PORT} already serves a Conbench API; set CONBENCH_PROD_CLONE_PORT to a free port"
fi

echo "==> start conbench serve on ${ADDR}"
prepare_private_file "$SERVER_LOG"
env -i \
	PATH="${PATH:-/usr/bin:/bin}" \
	CONBENCH_DB_URL="$SAFE_DB_URL" \
	CONBENCH_ADDR="$ADDR" \
	./bin/conbench serve >"$SERVER_LOG" 2>&1 &
SERVER_PID="$!"

echo "==> wait for /api/ping"
wait_for_ping

echo "==> select sample manifest"
"${PROD_CLONE_HELPER[@]}" samples "${preflight_args[@]}"
SAMPLES_PATH="${OUT_DIR}/samples.json"
read -r RESULT_ID HISTORY_FINGERPRINT < <(selected_result_sample "$SAMPLES_PATH")
[ -n "$RESULT_ID" ] || die "sample manifest did not include a result_id"
[ -n "$HISTORY_FINGERPRINT" ] || die "sample manifest did not include a history_fingerprint"

BASELINE_RESULT_ID="$(jq -r '.compare.baseline_result_id // ""' "$SAMPLES_PATH")"
CONTENDER_RESULT_ID="$(jq -r '.compare.contender_result_id // ""' "$SAMPLES_PATH")"

echo "==> API read probes"
if ! "${PROD_CLONE_HELPER[@]}" api-probe --server "$BASE_URL" --samples "$SAMPLES_PATH" --out "$OUT_DIR"; then
	FAILURES=1
fi

CLI_JSONL="${OUT_DIR}/cli-probes.jsonl"
prepare_private_file "$CLI_JSONL"

echo "==> CLI read probes"
run_cli_result_get "$RESULT_ID" "$CLI_JSONL"
run_cli_series_list "$HISTORY_FINGERPRINT" "$CLI_JSONL"
if [ -n "$BASELINE_RESULT_ID" ] && [ -n "$CONTENDER_RESULT_ID" ]; then
	run_cli_compare "$BASELINE_RESULT_ID" "$CONTENDER_RESULT_ID" "$CLI_JSONL"
else
	echo "warning: compare sample absent; skipping CLI compare probe" >&2
fi
finalize_probe_artifact "$BASE_URL" "$CLI_JSONL" "${OUT_DIR}/cli-probes.json"
rm -f "$CLI_JSONL"

SDK_JSONL="${OUT_DIR}/sdk-smoke.jsonl"
prepare_private_file "$SDK_JSONL"

echo "==> Python SDK smoke"
run_sdk_smoke "$RESULT_ID" "$HISTORY_FINGERPRINT" "$BASELINE_RESULT_ID" "$CONTENDER_RESULT_ID" "$SDK_JSONL"
finalize_probe_artifact "$BASE_URL" "$SDK_JSONL" "${OUT_DIR}/sdk-smoke.json"
rm -f "$SDK_JSONL"

if [ "$PROFILE" -eq 1 ]; then
	echo "==> profile read paths"
	if ! "${PROD_CLONE_HELPER[@]}" profile --server "$BASE_URL" --samples "$SAMPLES_PATH" --out "$OUT_DIR"; then
		FAILURES=1
	fi
fi

echo "==> stop server"
stop_server

echo "==> after-count preflight"
"${PROD_CLONE_HELPER[@]}" preflight "${preflight_args[@]}" \
	--json-out "${OUT_DIR}/preflight-after.json" \
	--counts-out "${OUT_DIR}/counts-after.json"

echo "==> compare writable-table counts"
if ! "${PROD_CLONE_HELPER[@]}" compare-counts \
	--before "${OUT_DIR}/counts-before.json" \
	--after "${OUT_DIR}/counts-after.json" \
	--out "${OUT_DIR}/count-delta.json"; then
	FAILURES=1
fi

echo "==> scan server log for blocked writes"
if ! "${PROD_CLONE_HELPER[@]}" log-scan --log "$SERVER_LOG" --out "$OUT_DIR"; then
	FAILURES=1
fi

echo "==> render compatibility report"
report_args=(--out "$OUT_DIR")
if [ "$PROFILE" -eq 1 ]; then
	report_args+=(--require-profile)
fi
if "${PROD_CLONE_HELPER[@]}" report "${report_args[@]}"; then
	REPORT_RENDERED=1
else
	REPORT_RENDERED=1
	exit 1
fi

if [ "$FAILURES" -ne 0 ]; then
	echo "==> compatibility checks failed; report: ${REPORT_PATH}" >&2
	exit 1
fi

echo "==> prod clone compatibility OK"
echo "report: ${REPORT_PATH}"
