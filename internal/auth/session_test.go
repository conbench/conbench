package auth_test

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/auth"
)

func TestSessionSignerRoundTrip(t *testing.T) {
	s := auth.NewSessionSigner("sek")
	now := time.Date(2026, 6, 12, 12, 0, 0, 0, time.UTC)
	val := s.Sign("user-123", now.Add(time.Hour))

	uid, err := s.Verify(val, now)
	require.NoError(t, err)
	assert.Equal(t, "user-123", uid)
}

func TestSessionSignerRejectsExpired(t *testing.T) {
	s := auth.NewSessionSigner("sek")
	now := time.Date(2026, 6, 12, 12, 0, 0, 0, time.UTC)
	val := s.Sign("user-123", now.Add(-time.Second))

	_, err := s.Verify(val, now)
	assert.Error(t, err)
}

func TestSessionSignerRejectsWrongSecret(t *testing.T) {
	now := time.Date(2026, 6, 12, 12, 0, 0, 0, time.UTC)
	val := auth.NewSessionSigner("sek").Sign("u", now.Add(time.Hour))
	_, err := auth.NewSessionSigner("different").Verify(val, now)
	assert.Error(t, err)
}
