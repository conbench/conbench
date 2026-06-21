package oidcauth_test

import (
	"context"
	"net/url"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/oidcauth/oidctestsupport"
)

func TestAuthCodeURLCarriesStateNonceAndPKCE(t *testing.T) {
	iss := oidctestsupport.New(t)
	c := iss.Client(t)

	raw := c.AuthCodeURL("the-state", "the-nonce", "the-verifier")
	u, err := url.Parse(raw)
	require.NoError(t, err)
	q := u.Query()
	assert.Equal(t, "the-state", q.Get("state"))
	assert.Equal(t, "the-nonce", q.Get("nonce"))
	assert.Equal(t, "S256", q.Get("code_challenge_method"))
	assert.NotEmpty(t, q.Get("code_challenge"))
	assert.Equal(t, oidctestsupport.ClientID, q.Get("client_id"))
	assert.Contains(t, q.Get("scope"), "openid")
}

func TestExchangeVerifiesIDTokenAndReturnsIdentity(t *testing.T) {
	iss := oidctestsupport.New(t)
	c := iss.Client(t)

	iss.SetNextIDToken(map[string]any{"nonce": "n1", "email": "x@example.com", "name": "Ex"})
	id, err := c.Exchange(context.Background(), "any-code", "the-verifier")
	require.NoError(t, err)
	assert.Equal(t, "x@example.com", id.Email)
	assert.True(t, id.EmailVerified)
	assert.Equal(t, "Ex", id.Name)
	assert.Equal(t, "n1", id.Nonce)
	// The PKCE verifier must reach the token endpoint; this fails if Exchange
	// stops sending it or sends the wrong value.
	assert.Equal(t, "the-verifier", iss.LastCodeVerifier())
}

func TestExchangeRejectsWrongAudience(t *testing.T) {
	iss := oidctestsupport.New(t)
	c := iss.Client(t)

	iss.SetNextIDToken(map[string]any{"aud": "someone-else"})
	_, err := c.Exchange(context.Background(), "any-code", "the-verifier")
	assert.Error(t, err, "audience mismatch must fail ID-token verification")
}

func TestExchangeRejectsExpiredToken(t *testing.T) {
	iss := oidctestsupport.New(t)
	c := iss.Client(t)

	iss.SetNextIDToken(map[string]any{"exp": int64(1000000000)}) // 2001
	_, err := c.Exchange(context.Background(), "any-code", "the-verifier")
	assert.Error(t, err, "expired token must fail verification")
}
