// Package oidctestsupport stands up a fake OIDC issuer (discovery, JWKS, token
// endpoint) for exercising the OIDC login flow without a real identity
// provider. It is test support, not production code.
package oidctestsupport

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"encoding/json"
	"maps"
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync"
	"testing"
	"time"

	jose "github.com/go-jose/go-jose/v4"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/oidcauth"
)

const (
	// ClientID and ClientSecret are the fake relying-party credentials.
	ClientID     = "conbench-client"
	ClientSecret = "conbench-secret"
	keyID        = "test-key-1"
)

// Issuer is an httptest OIDC provider whose next token response is configured
// per-test via SetNextIDToken. It records token-endpoint calls so tests can
// assert that an exchange happened (and with which PKCE verifier) or, for the
// rejection cases, that no exchange happened at all.
type Issuer struct {
	srv    *httptest.Server
	priv   *rsa.PrivateKey
	claims map[string]any

	mu           sync.Mutex
	tokenCalls   int
	lastVerifier string
	lastNonce    string
}

// New starts a fake issuer and registers cleanup.
func New(t *testing.T) *Issuer {
	t.Helper()
	priv, err := rsa.GenerateKey(rand.Reader, 2048)
	require.NoError(t, err)
	iss := &Issuer{priv: priv}

	mux := http.NewServeMux()
	mux.HandleFunc("/.well-known/openid-configuration", func(w http.ResponseWriter, _ *http.Request) {
		base := iss.srv.URL
		writeJSON(w, map[string]any{
			"issuer":                                base,
			"authorization_endpoint":                base + "/authorize",
			"token_endpoint":                        base + "/token",
			"jwks_uri":                              base + "/jwks",
			"id_token_signing_alg_values_supported": []string{"RS256"},
		})
	})
	mux.HandleFunc("/authorize", func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		u, err := url.Parse(q.Get("redirect_uri"))
		if err != nil {
			http.Error(w, "bad redirect_uri", http.StatusBadRequest)
			return
		}
		iss.mu.Lock()
		iss.lastNonce = q.Get("nonce")
		iss.mu.Unlock()
		rq := u.Query()
		rq.Set("code", "fake-auth-code")
		rq.Set("state", q.Get("state"))
		u.RawQuery = rq.Encode()
		http.Redirect(w, r, u.String(), http.StatusFound)
	})
	mux.HandleFunc("/jwks", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, jose.JSONWebKeySet{Keys: []jose.JSONWebKey{{
			Key: priv.Public(), KeyID: keyID, Algorithm: "RS256", Use: "sig",
		}}})
	})
	mux.HandleFunc("/token", func(w http.ResponseWriter, r *http.Request) {
		verifier := ""
		if err := r.ParseForm(); err == nil {
			verifier = r.PostFormValue("code_verifier")
		}
		iss.mu.Lock()
		iss.tokenCalls++
		iss.lastVerifier = verifier
		iss.mu.Unlock()
		writeJSON(w, map[string]any{
			"access_token": "fake-access-token",
			"token_type":   "Bearer",
			"id_token":     iss.signIDToken(t),
		})
	})
	iss.srv = httptest.NewServer(mux)
	t.Cleanup(iss.srv.Close)
	iss.SetNextIDToken(nil) // sensible defaults until a test overrides
	return iss
}

// URL returns the issuer base URL.
func (iss *Issuer) URL() string { return iss.srv.URL }

// TokenCalls returns how many times the token endpoint has been hit. A
// rejection that happens before code exchange leaves this at zero.
func (iss *Issuer) TokenCalls() int {
	iss.mu.Lock()
	defer iss.mu.Unlock()
	return iss.tokenCalls
}

// LastCodeVerifier returns the PKCE code_verifier posted on the most recent
// token request, so tests can prove the client sent it.
func (iss *Issuer) LastCodeVerifier() string {
	iss.mu.Lock()
	defer iss.mu.Unlock()
	return iss.lastVerifier
}

// SetNextIDToken configures the claims the token endpoint signs next; passed
// keys override the defaults (nonce, email, email_verified, aud, exp, ...).
func (iss *Issuer) SetNextIDToken(claims map[string]any) {
	base := map[string]any{
		"iss":            iss.srv.URL,
		"aud":            ClientID,
		"sub":            "subject-123",
		"exp":            time.Now().Add(time.Hour).Unix(),
		"iat":            time.Now().Unix(),
		"email":          "dev@example.com",
		"email_verified": true,
		"name":           "Dev User",
	}
	maps.Copy(base, claims)
	iss.claims = base
}

// Client builds an oidcauth.Client pointed at this issuer with a default,
// unreachable redirect URL — fine for tests that craft the pending cookie and
// hit /callback directly without a real browser round-trip.
func (iss *Issuer) Client(t *testing.T) *oidcauth.Client {
	return iss.ClientWithRedirect(t, "https://conbench.example/api/auth/callback")
}

// ClientWithRedirect builds an oidcauth.Client whose OIDC redirect_uri is
// redirectURL. The full loopback login test must point this at the live test
// server's callback so the IdP redirects the browser somewhere it can reach.
func (iss *Issuer) ClientWithRedirect(t *testing.T, redirectURL string) *oidcauth.Client {
	t.Helper()
	c, err := oidcauth.New(context.Background(), oidcauth.Config{
		IssuerURL: iss.srv.URL, ClientID: ClientID, ClientSecret: ClientSecret,
		RedirectURL: redirectURL,
	})
	require.NoError(t, err)
	return c
}

func (iss *Issuer) signIDToken(t *testing.T) string {
	t.Helper()
	signer, err := jose.NewSigner(
		jose.SigningKey{Algorithm: jose.RS256, Key: iss.priv},
		(&jose.SignerOptions{}).WithType("JWT").WithHeader("kid", keyID),
	)
	require.NoError(t, err)
	claims := maps.Clone(iss.claims)
	iss.mu.Lock()
	if iss.lastNonce != "" {
		claims["nonce"] = iss.lastNonce
	}
	iss.mu.Unlock()
	payload, err := json.Marshal(claims)
	require.NoError(t, err)
	jws, err := signer.Sign(payload)
	require.NoError(t, err)
	compact, err := jws.CompactSerialize()
	require.NoError(t, err)
	return compact
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
