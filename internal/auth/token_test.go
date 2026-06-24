package auth_test

import (
	"crypto/sha256"
	"encoding/hex"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/auth"
)

func TestGenerateTokenShape(t *testing.T) {
	tok, err := auth.GenerateToken()
	require.NoError(t, err)

	assert.Regexp(t, `^cb_[0-9a-zA-Z]+$`, tok.Plaintext)
	// The base62 payload is left-padded to a fixed 43 digits, so every
	// plaintext is exactly "cb_" + 43 chars.
	assert.Len(t, tok.Plaintext, 46)
	assert.Equal(t, tok.Plaintext[:8], tok.Prefix)
	assert.Equal(t, auth.HashToken(tok.Plaintext), tok.Hash)

	sum := sha256.Sum256([]byte(tok.Plaintext))
	assert.Equal(t, hex.EncodeToString(sum[:]), tok.Hash, "hash is hex SHA-256 of the full plaintext")
}

func TestGenerateTokenUnique(t *testing.T) {
	a, err := auth.GenerateToken()
	require.NoError(t, err)
	b, err := auth.GenerateToken()
	require.NoError(t, err)
	assert.NotEqual(t, a.Plaintext, b.Plaintext)
	assert.NotEqual(t, a.Hash, b.Hash)
}
