#!/usr/bin/env bash
# Keystone end-to-end check: boot the built conbench serve against an ephemeral
# seeded Postgres, submit a fixture via the conbench CLI, then run the Playwright
# browser assertions and the Python SDK smoke against the live server. Opt-in and
# Docker-required (no graceful skip).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v jq >/dev/null 2>&1 || { echo "jq is required to parse the submit response; please install jq" >&2; exit 1; }

PORT="${CONBENCH_E2E_PORT:-8099}"
BASE_URL="http://localhost:${PORT}"
TOKEN="e2e-token"
DEV_TOKEN="cb_e2e_dev_token_value"
PG_CONTAINER="conbench-e2e-pg-$$"
SERVER_PID=""
SERVER_LOG="$(mktemp)"

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "=== e2e FAILED (status ${status}); diagnostics ===" >&2
    echo "--- conbench serve log (tail) ---" >&2; tail -n 80 "$SERVER_LOG" >&2 2>/dev/null || true
    echo "--- postgres container log (tail) ---" >&2; docker logs --tail 80 "$PG_CONTAINER" >&2 2>&1 || true
    echo "--- playwright report: web/playwright-report/index.html ---" >&2
  fi
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
  rm -f "$SERVER_LOG" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT

echo "==> build binaries + SPA"
make build

echo "==> start ephemeral Postgres"
docker run -d --name "$PG_CONTAINER" \
  -e POSTGRES_USER=conbench -e POSTGRES_PASSWORD=conbench -e POSTGRES_DB=conbench \
  -P postgres:15.2-alpine >/dev/null
PG_PORT="$(docker inspect --format '{{ (index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort }}' "$PG_CONTAINER")"
export CONBENCH_DB_URL="postgres://conbench:conbench@localhost:${PG_PORT}/conbench?sslmode=disable"

postgres_ready() {
  docker exec -e PGPASSWORD=conbench "$PG_CONTAINER" \
    psql -h 127.0.0.1 -U conbench -d conbench -v ON_ERROR_STOP=1 -c "SELECT 1" >/dev/null 2>&1
}

echo "==> wait for Postgres"
for _ in $(seq 1 30); do
  postgres_ready && break
  sleep 1
done
if ! postgres_ready; then
  echo "postgres database did not become ready within 30s" >&2
  exit 1
fi

echo "==> verify :${PORT} is free"
if curl -fsS "${BASE_URL}/api/ping" >/dev/null 2>&1; then
  echo "port ${PORT} already serves a Conbench API; set CONBENCH_E2E_PORT to a free port" >&2
  exit 1
fi

echo "==> start conbench serve on :${PORT}"
CONBENCH_ADDR=":${PORT}" CONBENCH_INIT_SCHEMA=true CONBENCH_SEED=true CONBENCH_API_TOKEN="$TOKEN" \
  CONBENCH_SEED_DEV_TOKEN="$DEV_TOKEN" \
  ./bin/conbench serve >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

echo "==> wait for /api/ping"
for _ in $(seq 1 30); do
  curl -fsS "${BASE_URL}/api/ping" >/dev/null 2>&1 && break
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "conbench serve exited before becoming ready (see server log above)" >&2
    exit 1
  fi
  sleep 1
done
curl -fsS "${BASE_URL}/api/ping" >/dev/null

echo "==> submit fixture via conbench CLI"
SUBMIT_OUT="$(./bin/conbench results submit web/e2e/fixtures/result.json --server "$BASE_URL" --token "$TOKEN")"
echo "submit -> ${SUBMIT_OUT}"
RESULT_ID="$(printf '%s' "$SUBMIT_OUT" | jq -r '.id // empty')"
FINGERPRINT="$(printf '%s' "$SUBMIT_OUT" | jq -r '.history_fingerprint // empty')"
if [ -z "$RESULT_ID" ] || [ -z "$FINGERPRINT" ]; then
  echo "submit response missing id/history_fingerprint: ${SUBMIT_OUT}" >&2
  exit 1
fi

echo "==> CLI read checks"
RESULT_OUT="$(./bin/conbench results get "$RESULT_ID" --server "$BASE_URL")"
printf '%s' "$RESULT_OUT" | jq -e --arg id "$RESULT_ID" '.id == $id' >/dev/null || {
  echo "results get returned unexpected payload: ${RESULT_OUT}" >&2
  exit 1
}
SERIES_OUT="$(./bin/conbench series list --server "$BASE_URL" --fingerprint "$FINGERPRINT")"
printf '%s' "$SERIES_OUT" | jq -e --arg fp "$FINGERPRINT" \
  '.series | length >= 1 and all(.[]; .history_fingerprint == $fp)' >/dev/null || {
  echo "series list returned rows outside fingerprint ${FINGERPRINT}: ${SERIES_OUT}" >&2
  exit 1
}

echo "==> Playwright keystone (result ${RESULT_ID})"
(
  cd web || exit 1
  if [ -z "${CONBENCH_E2E_SKIP_BROWSER_INSTALL:-}" ]; then
    bunx playwright install chromium >/dev/null
  fi
  CONBENCH_E2E_BASE_URL="$BASE_URL" CONBENCH_E2E_RESULT_ID="$RESULT_ID" bun run test:e2e
)

echo "==> submit contender fixture via conbench CLI"
CONTENDER_SUBMIT_OUT="$(./bin/conbench results submit web/e2e/fixtures/result.json --server "$BASE_URL" --token "$TOKEN")"
echo "contender submit -> ${CONTENDER_SUBMIT_OUT}"
CONTENDER_ID="$(printf '%s' "$CONTENDER_SUBMIT_OUT" | jq -r '.id // empty')"
CONTENDER_FINGERPRINT="$(printf '%s' "$CONTENDER_SUBMIT_OUT" | jq -r '.history_fingerprint // empty')"
if [ -z "$CONTENDER_ID" ] || [ -z "$CONTENDER_FINGERPRINT" ]; then
  echo "contender submit response missing id/history_fingerprint: ${CONTENDER_SUBMIT_OUT}" >&2
  exit 1
fi

echo "==> shape submitted commit for CI report"
docker exec "$PG_CONTAINER" psql -U conbench -d conbench -v ON_ERROR_STOP=1 \
  -c "UPDATE commit SET parent = 'commit-05', fork_point_sha = 'commit-05' WHERE repository = 'https://github.com/conbench/demo' AND sha = 'commit-06'" >/dev/null

echo "==> CLI compare check"
COMPARE_OUT="$(./bin/conbench compare "$RESULT_ID" "$CONTENDER_ID" --server "$BASE_URL")"
printf '%s' "$COMPARE_OUT" | jq -e --arg baseline "$RESULT_ID" --arg contender "$CONTENDER_ID" \
  '.baseline.benchmark_result_id == $baseline and .contender.benchmark_result_id == $contender' >/dev/null || {
  echo "compare returned unexpected payload: ${COMPARE_OUT}" >&2
  exit 1
}

echo "==> CLI CI report check"
set +e
CI_REPORT_OUT="$(./bin/conbench ci report \
  --server "$BASE_URL" \
  --token "$TOKEN" \
  --repository "https://github.com/conbench/demo" \
  --commit "commit-06" \
  --run-ids "e2e-run-06" \
  --threshold-z 0.1)"
CI_REPORT_CODE=$?
set -e
CI_REPORT_STATUS="$(printf '%s' "$CI_REPORT_OUT" | jq -r '.status // empty')"
[ "$CI_REPORT_STATUS" = "failure" ] || { echo "ci report returned unexpected status: ${CI_REPORT_OUT}" >&2; exit 1; }
[ "$CI_REPORT_CODE" -eq 1 ] || { echo "ci report status ${CI_REPORT_STATUS} exited ${CI_REPORT_CODE}" >&2; exit 1; }
printf '%s' "$CI_REPORT_OUT" | jq -e \
  --arg repo "https://github.com/conbench/demo" \
  '.repository == $repo
    and .commit_sha == "commit-06"
    and .selected_run_ids == ["e2e-run-06"]
    and .runs[0].baseline_run_id == "run-commit-05"
    and .summary.contender_results == 2
    and .summary.compared == 2
    and .summary.analyzed == 2
    and .summary.regressions == 2' >/dev/null || {
  echo "ci report did not exercise expected comparison path: ${CI_REPORT_OUT}" >&2
  exit 1
}

echo "==> Python SDK smoke"
(
  cd sdk/python || exit 1
  CONBENCH_SERVER_URL="$BASE_URL" \
    CONBENCH_HISTORY_FINGERPRINT="$FINGERPRINT" \
    CONBENCH_BASELINE_RESULT_ID="$RESULT_ID" \
    CONBENCH_CONTENDER_RESULT_ID="$CONTENDER_ID" \
    CONBENCH_CI_REPORT_REPOSITORY="https://github.com/conbench/demo" \
    CONBENCH_CI_REPORT_COMMIT_SHA="commit-06" \
    CONBENCH_CI_REPORT_RUN_IDS="e2e-run-06" \
    CONBENCH_CI_REPORT_THRESHOLD_Z="0.1" \
    CONBENCH_CI_REPORT_EXPECT_STATUS="failure" \
    CONBENCH_CI_REPORT_EXPECT_BASELINE_RUN_ID="run-commit-05" \
    CONBENCH_CI_REPORT_EXPECT_CONTENDER_RESULTS="2" \
    CONBENCH_CI_REPORT_EXPECT_REGRESSIONS="2" \
    uv run pytest -q
)

echo "==> authenticated submit + token list with a user-owned db token"
USER_SUBMIT_OUT="$(./bin/conbench results submit web/e2e/fixtures/result.json --server "$BASE_URL" --token "$DEV_TOKEN")"
echo "$USER_SUBMIT_OUT" | jq -e '.id' >/dev/null || { echo "user-token submit failed: $USER_SUBMIT_OUT" >&2; exit 1; }
TOKENS_OUT="$(./bin/conbench auth token list --server "$BASE_URL" --token "$DEV_TOKEN")"
echo "$TOKENS_OUT" | jq -e '.tokens | length >= 1' >/dev/null || { echo "auth token list failed: $TOKENS_OUT" >&2; exit 1; }

echo "==> e2e OK"
