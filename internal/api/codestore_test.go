package api

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCodeStoreSweepsExpiredOnIssue(t *testing.T) {
	cs := newCodeStore()
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)

	cs.issueAt("u1", now) // never redeemed; expires at now+codeTTL

	// A later issue (after the first code expired) sweeps the stale entry, so an
	// abandoned login cannot accumulate in the map.
	cs.issueAt("u2", now.Add(codeTTL+time.Second))

	cs.mu.Lock()
	n := len(cs.entries)
	cs.mu.Unlock()
	assert.Equal(t, 1, n, "expired entry swept on the next issue")
}

func TestCodeStoreIssueRedeemSingleUse(t *testing.T) {
	cs := newCodeStore()
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)

	code := cs.issueAt("user-1", now)
	require.NotEmpty(t, code)

	uid, ok := cs.redeemAt(code, now.Add(time.Second))
	require.True(t, ok)
	assert.Equal(t, "user-1", uid)

	// Single use: a second redeem fails.
	_, ok = cs.redeemAt(code, now.Add(time.Second))
	assert.False(t, ok, "code is single-use")
}

func TestCodeStoreExpiry(t *testing.T) {
	cs := newCodeStore()
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)
	code := cs.issueAt("user-1", now)

	_, ok := cs.redeemAt(code, now.Add(codeTTL+time.Second))
	assert.False(t, ok, "expired code is rejected")
}

func TestCodeStoreExpiredCodeIsConsumed(t *testing.T) {
	// An expired code must still be deleted on the redeem attempt (no lingering
	// state), so a later in-window retry of the same value also fails.
	cs := newCodeStore()
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)
	code := cs.issueAt("user-1", now)

	_, ok := cs.redeemAt(code, now.Add(codeTTL+time.Second))
	require.False(t, ok)
	_, ok = cs.redeemAt(code, now.Add(time.Second)) // earlier "now", still gone
	assert.False(t, ok, "expired code was consumed, not left behind")
}

func TestCodeStoreUnknown(t *testing.T) {
	cs := newCodeStore()
	_, ok := cs.redeemAt("nope", time.Now().UTC())
	assert.False(t, ok)
}
