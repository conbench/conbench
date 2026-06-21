package auth

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestSignerRoundTrip(t *testing.T) {
	s := NewSigner("topsecret")
	tok := s.Sign([]byte(`{"hello":"world"}`))
	got, err := s.Verify(tok)
	require.NoError(t, err)
	assert.JSONEq(t, `{"hello":"world"}`, string(got))
}

func TestSignerRejectsTamper(t *testing.T) {
	s := NewSigner("topsecret")
	tok := s.Sign([]byte("payload"))

	// Flip the last character of the signature.
	bad := tok[:len(tok)-1] + string(rune(tok[len(tok)-1]^1))
	_, err := s.Verify(bad)
	require.Error(t, err)

	// A different secret must not verify.
	_, err = NewSigner("othersecret").Verify(tok)
	require.Error(t, err)

	// Malformed (no separator).
	_, err = s.Verify("nodot")
	assert.Error(t, err)
}
