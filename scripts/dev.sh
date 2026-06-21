#!/usr/bin/env bash
set -euo pipefail

# Backend dev loop: start a persistent dev Postgres, then run conbench serve,
# which applies the schema if missing, seeds deterministic demo data (idempotent),
# and serves the API. Re-runnable; Ctrl-C stops the server (the db keeps running;
# `make dev-down` stops it).
#
# After it starts, try:
#   curl localhost:8080/api/ping
#   curl localhost:8080/api/history?fingerprint=<printed at seed time>
#   open  localhost:8080/docs        # huma's OpenAPI docs

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PROJECT="conbench_backend_dev"
COMPOSE=(docker compose -p "$PROJECT" -f docker-compose.backend-dev.yml)

ADDR="${CONBENCH_ADDR:-:8080}"
# Target the dev compose Postgres explicitly. Do NOT inherit an ambient
# CONBENCH_DB_URL: this script forces schema-init and seeding, which must never
# hit a real database. Use CONBENCH_DEV_DB_URL to point at a different dev DB.
DEV_DB_URL="postgres://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable"
DB_URL="${CONBENCH_DEV_DB_URL:-$DEV_DB_URL}"

echo "[dev] starting Postgres…"
"${COMPOSE[@]}" up -d db

echo "[dev] waiting for Postgres to accept connections…"
for _ in $(seq 1 60); do
	if "${COMPOSE[@]}" exec -T db pg_isready -U postgres >/dev/null 2>&1; then
		break
	fi
	sleep 1
done

echo "[dev] starting conbench serve on ${ADDR} (db: ${DB_URL})…"
CONBENCH_ADDR="$ADDR" \
	CONBENCH_DB_URL="$DB_URL" \
	CONBENCH_INIT_SCHEMA=true \
	CONBENCH_SEED=true \
	CONBENCH_AUTH_DISABLED=true \
	exec go run ./cmd/conbench serve
