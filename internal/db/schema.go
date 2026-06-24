package db

import _ "embed"

// SchemaSQL is the canonical Postgres schema (the Alembic-generated DDL dumped to
// schema.sql by scripts/gen_schema.sh). It is embedded so tooling and tests can
// materialize the frozen schema without shelling out to Alembic or locating the
// file on disk.
//
//go:embed schema.sql
var SchemaSQL string
