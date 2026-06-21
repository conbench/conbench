// Package dbtest provides a real-Postgres test harness shared by the packages
// that exercise the data layer end to end (the store, the ingestion service, the
// API). It starts an ephemeral Postgres via testcontainers, applies the frozen
// schema, and skips gracefully when Docker is unavailable so `go test ./...`
// stays green off-CI. Tests run against real Postgres, never mocks.
package dbtest

import (
	"context"
	"fmt"
	"sync/atomic"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"

	"github.com/conbench/conbench/internal/db"
)

// NewPool starts an ephemeral Postgres (the pinned image), applies the embedded
// schema, and returns a connected pool plus a context. It registers cleanups for
// the pool and container, and skips when Docker is not reachable or under
// `go test -short`.
func NewPool(t *testing.T) (*pgxpool.Pool, context.Context) {
	t.Helper()
	if testing.Short() {
		t.Skip("skipping Postgres-backed test in -short mode")
	}
	ctx := context.Background()

	container, err := postgres.Run(ctx, "postgres:15.2-alpine",
		postgres.WithDatabase("conbench"),
		postgres.WithUsername("postgres"),
		postgres.WithPassword("postgres"),
		postgres.BasicWaitStrategies(),
	)
	if err != nil {
		t.Skipf("skipping: cannot start Postgres container (Docker required): %v", err)
	}
	t.Cleanup(func() { _ = testcontainers.TerminateContainer(container) })

	connStr, err := container.ConnectionString(ctx, "sslmode=disable")
	require.NoError(t, err, "connection string")
	pool, err := pgxpool.New(ctx, connStr)
	require.NoError(t, err, "open pool")
	t.Cleanup(pool.Close)

	_, err = pool.Exec(ctx, db.SchemaSQL)
	require.NoError(t, err, "apply schema")
	return pool, ctx
}

// userSeq disambiguates seeded users within a test binary run; the unique
// email index on "user" would otherwise collide across subtests sharing a
// container.
var userSeq atomic.Int64

// SeedUser inserts a minimal user row (the FK target for api_token and,
// later, sessions) and returns its id. The password column is NOT NULL in the
// frozen schema; the marker value is unusable for login by construction.
func SeedUser(t *testing.T, ctx context.Context, pool *pgxpool.Pool) string {
	t.Helper()
	n := userSeq.Add(1)
	id := fmt.Sprintf("testuser%024d", n)
	_, err := pool.Exec(ctx,
		`INSERT INTO "user" (id, email, name, password) VALUES ($1, $2, $3, '!')`,
		id, fmt.Sprintf("user%d@example.com", n), fmt.Sprintf("Test User %d", n))
	require.NoError(t, err, "seed user")
	return id
}
