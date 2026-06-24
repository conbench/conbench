package auth

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestShouldTouchLastUsed(t *testing.T) {
	now := time.Date(2026, 6, 12, 12, 0, 0, 0, time.UTC)
	assert.True(t, shouldTouchLastUsed(nil, now), "never used -> touch")
	old := now.Add(-6 * time.Minute)
	assert.True(t, shouldTouchLastUsed(&old, now), "stale by >5min -> touch")
	fresh := now.Add(-4 * time.Minute)
	assert.False(t, shouldTouchLastUsed(&fresh, now), "fresh -> no hot-path write")
	exact := now.Add(-5 * time.Minute)
	assert.False(t, shouldTouchLastUsed(&exact, now), "boundary: stale means STRICTLY more than 5min")
}
