#!/usr/bin/env bash
set -euo pipefail

# Schema-drift gate: fail if internal/db/schema.sql is out of sync with the
# Alembic migrations. Run by CI and locally via `make schema-check`.
#
# Regenerates the schema into a temp file and diffs it against the committed
# copy. A non-empty diff means the migrations changed but schema.sql was not
# regenerated (run `make schema` and commit), or vice versa.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CANONICAL="internal/db/schema.sql"
TMP="$(mktemp -t conbench-schema.XXXXXX.sql)"
trap 'rm -f "$TMP"' EXIT

scripts/gen_schema.sh "$TMP"

if ! diff -u "$CANONICAL" "$TMP"; then
	{
		echo
		echo "ERROR: ${CANONICAL} is out of date with the Alembic migrations."
		echo "Run 'make schema' and commit the result."
	} >&2
	exit 1
fi

echo "[schema-check] ${CANONICAL} is up to date."
