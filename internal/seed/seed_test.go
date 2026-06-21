package seed_test

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/seed"
	"github.com/conbench/conbench/internal/service"
)

func TestSeedIdempotent(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	s1, err := seed.Run(ctx, store)
	require.NoError(t, err, "seed 1")
	require.False(t, s1.Skipped, "first seed skipped, want inserted")
	count1, err := store.CountBenchmarkResults(ctx)
	require.NoError(t, err, "count")
	if int(count1) != s1.Inserted || count1 == 0 {
		require.FailNowf(t, "unexpected count", "count1=%d, inserted=%d", count1, s1.Inserted)
	}

	s2, err := seed.Run(ctx, store)
	require.NoError(t, err, "seed 2")
	assert.True(t, s2.Skipped, "second seed not skipped (not idempotent)")
	count2, err := store.CountBenchmarkResults(ctx)
	require.NoError(t, err, "count")
	assert.Equal(t, count1, count2, "result count changed across runs")
}

func TestDevTokenCreatesUserOwnedToken(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	prefix, err := seed.DevToken(ctx, store, "cb_e2e_dev_token_value")
	require.NoError(t, err)
	assert.Equal(t, "cb_e2e_d", prefix)

	row, err := store.GetAPITokenByHash(ctx, auth.HashToken("cb_e2e_dev_token_value"))
	require.NoError(t, err)
	assert.NotEmpty(t, row.UserID)
	assert.Equal(t, "dev seed token", row.Name)
}

func TestDevTokenIsIdempotent(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	_, err := seed.DevToken(ctx, store, "cb_e2e_dev_token_value")
	require.NoError(t, err)
	_, err = seed.DevToken(ctx, store, "cb_e2e_dev_token_value")
	require.NoError(t, err, "second call is a no-op, not a duplicate-key error")

	userID, err := store.GetOrCreateUserByEmail(ctx, "dev@conbench.local", "Dev (seeded)", "!")
	require.NoError(t, err)
	rows, err := store.ListAPITokensByUser(ctx, userID)
	require.NoError(t, err)
	assert.Len(t, rows, 1, "second call inserted a duplicate token")
}

func TestDevTokenRejectsShortValue(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	_, err := seed.DevToken(ctx, store, "short")
	require.Error(t, err)
}

func TestSeedHistoryOrderedPoints(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	s, err := seed.Run(ctx, store)
	require.NoError(t, err, "seed")
	require.NotEmpty(t, s.Fingerprint, "seed returned no fingerprint")

	series, err := service.NewReader(store).History(ctx, s.Fingerprint)
	require.NoError(t, err, "History")
	require.Len(t, series.Samples, seed.IncludedHistoryPoints)

	// The excluded rows (off-branch, errored) are persisted but not in history.
	count, err := store.CountBenchmarkResults(ctx)
	require.NoError(t, err, "count")
	assert.Greater(t, int(count), seed.IncludedHistoryPoints, "excluded rows present")

	// Ordered oldest-commit-first, with a visible upward trend in the value.
	for i := 1; i < len(series.Samples); i++ {
		prev, cur := series.Samples[i-1], series.Samples[i]
		require.NotNil(t, prev.CommitTimestamp, "sample missing commit timestamp")
		require.NotNil(t, cur.CommitTimestamp, "sample missing commit timestamp")
		assert.False(t, cur.CommitTimestamp.Before(*prev.CommitTimestamp),
			"sample %d commit time %v is before %v", i, cur.CommitTimestamp, prev.CommitTimestamp)
		assert.Greater(t, cur.SVS, prev.SVS,
			"sample %d svs %v not greater than previous %v (expected upward trend)", i, cur.SVS, prev.SVS)
	}
}
