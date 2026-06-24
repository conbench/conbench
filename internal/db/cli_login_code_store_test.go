package db_test

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/dbtest"
)

func TestCLILoginCodeStorageRedeemsOnceAndRejectsExpired(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	now := time.Date(2026, 6, 18, 14, 30, 0, 0, time.UTC)

	codeHash := auth.HashToken("loopback-code")
	require.NoError(t, st.InsertCLILoginCode(ctx, codeHash, userID, now, now.Add(time.Minute)))

	gotUserID, ok, err := st.RedeemCLILoginCode(ctx, codeHash, now.Add(time.Second))
	require.NoError(t, err)
	require.True(t, ok)
	assert.Equal(t, userID, gotUserID)

	_, ok, err = st.RedeemCLILoginCode(ctx, codeHash, now.Add(2*time.Second))
	require.NoError(t, err)
	assert.False(t, ok, "redeemed code is single-use")

	expiredHash := auth.HashToken("expired-loopback-code")
	require.NoError(t, st.InsertCLILoginCode(ctx, expiredHash, userID, now.Add(-2*time.Minute), now.Add(-time.Minute)))
	_, ok, err = st.RedeemCLILoginCode(ctx, expiredHash, now)
	require.NoError(t, err)
	assert.False(t, ok, "expired code cannot be redeemed")

	require.NoError(t, st.DeleteExpiredCLILoginCodes(ctx, now))
}
