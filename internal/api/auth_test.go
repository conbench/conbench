package api_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/oidcauth/oidctestsupport"
)

const testSessionSecret = "test-session-secret"

func newAuthHandler(t *testing.T, iss *oidctestsupport.Issuer) (*api.AuthHandler, *db.Store, context.Context) {
	return newAuthHandlerWithAuthDisabled(t, iss, false)
}

func newAuthHandlerWithAuthDisabled(t *testing.T, iss *oidctestsupport.Issuer, authDisabled bool) (*api.AuthHandler, *db.Store, context.Context) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	h := api.NewAuthHandler(
		iss.Client(t), store,
		auth.NewSessionSigner(testSessionSecret), auth.NewSigner(testSessionSecret),
		false, "https://conbench.example", api.NewDBCodeStore(store), authDisabled,
	)
	return h, store, ctx
}

func registerAuth(t *testing.T, h *api.AuthHandler) humatest.TestAPI {
	_, tapi := humatest.New(t)
	h.Register(tapi)
	return tapi
}

func TestLoginRedirectsAndSetsPendingCookie(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	resp := tapi.Get("/api/auth/login")
	require.Equal(t, http.StatusFound, resp.Code)
	loc, err := url.Parse(resp.Header().Get("Location"))
	require.NoError(t, err)
	assert.Equal(t, "S256", loc.Query().Get("code_challenge_method"))
	assert.NotEmpty(t, loc.Query().Get("state"))

	setCookie := resp.Header().Get("Set-Cookie")
	assert.Contains(t, setCookie, "conbench_pending=")
	assert.Contains(t, setCookie, "HttpOnly")
}

func TestCallbackCreatesUserAndSetsSession(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, store, ctx := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	// Craft the pending cookie directly (the test owns the secret), so we know
	// the nonce the issuer must echo.
	pending := api.SignPendingForTest(testSessionSecret, "the-state", "the-nonce", "the-verifier")
	iss.SetNextIDToken(map[string]any{"nonce": "the-nonce", "email": "new@example.com", "name": "New User"})

	resp := tapi.Get("/api/auth/callback?state=the-state&code=xyz",
		"Cookie: conbench_pending="+pending)
	require.Equal(t, http.StatusFound, resp.Code, "body=%s", resp.Body.String())

	set := resp.Header().Get("Set-Cookie")
	assert.Contains(t, set, "conbench_session=")

	// The user now exists.
	id, err := store.GetOrCreateUserByEmail(ctx, "new@example.com", "x", "!")
	require.NoError(t, err)
	row, err := store.GetUserByID(ctx, id)
	require.NoError(t, err)
	assert.Equal(t, "New User", row.Name)
}

func TestCallbackRejectsStateMismatch(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	// The issuer echoes the matching nonce, so the state check is the only
	// thing that can produce the 400 (otherwise the test would pass even if the
	// state check regressed, on the empty-nonce mismatch instead).
	pending := api.SignPendingForTest(testSessionSecret, "the-state", "the-nonce", "the-verifier")
	iss.SetNextIDToken(map[string]any{"nonce": "the-nonce"})
	resp := tapi.Get("/api/auth/callback?state=WRONG&code=xyz", "Cookie: conbench_pending="+pending)
	assert.Equal(t, http.StatusBadRequest, resp.Code)
}

func TestCallbackRejectsMissingOrForgedPendingCookie(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	// No pending cookie at all: the callback cannot trust the state/nonce, so
	// it must reject before any code exchange.
	resp := tapi.Get("/api/auth/callback?state=the-state&code=xyz")
	assert.Equal(t, http.StatusBadRequest, resp.Code, "missing pending cookie")

	// A pending cookie signed with the wrong secret must not verify.
	forged := api.SignPendingForTest("wrong-secret", "the-state", "the-nonce", "the-verifier")
	resp = tapi.Get("/api/auth/callback?state=the-state&code=xyz", "Cookie: conbench_pending="+forged)
	assert.Equal(t, http.StatusBadRequest, resp.Code, "forged pending cookie")

	// Neither rejection may have reached the token endpoint: an untrusted
	// cookie must be refused before any code exchange, not after.
	assert.Equal(t, 0, iss.TokenCalls(), "no code exchange for missing/forged cookies")
}

func TestCallbackRejectsNonceMismatch(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	pending := api.SignPendingForTest(testSessionSecret, "the-state", "the-nonce", "the-verifier")
	iss.SetNextIDToken(map[string]any{"nonce": "DIFFERENT"})
	resp := tapi.Get("/api/auth/callback?state=the-state&code=xyz", "Cookie: conbench_pending="+pending)
	assert.Equal(t, http.StatusBadRequest, resp.Code)
}

func TestCallbackRejectsUnverifiedEmail(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	pending := api.SignPendingForTest(testSessionSecret, "the-state", "the-nonce", "the-verifier")
	iss.SetNextIDToken(map[string]any{"nonce": "the-nonce", "email_verified": false})
	resp := tapi.Get("/api/auth/callback?state=the-state&code=xyz", "Cookie: conbench_pending="+pending)
	assert.Equal(t, http.StatusBadRequest, resp.Code)
}

func TestUsersMeReturnsSessionIdentity(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, store, ctx := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	uid, err := store.GetOrCreateUserByEmail(ctx, "me@example.com", "Me", "!")
	require.NoError(t, err)
	session := auth.NewSessionSigner(testSessionSecret).Sign(uid, time.Now().UTC().Add(time.Hour))

	resp := tapi.Get("/api/users/me", "Cookie: conbench_session="+session)
	require.Equal(t, http.StatusOK, resp.Code)
	assert.Contains(t, resp.Body.String(), "me@example.com")

	resp = tapi.Get("/api/users/me")
	assert.Equal(t, http.StatusUnauthorized, resp.Code, "no session => 401")
}

func TestAuthCapabilitiesReportResultWriteAvailability(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, store, ctx := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	resp := tapi.Get("/api/auth/capabilities")
	require.Equal(t, http.StatusOK, resp.Code)
	assert.JSONEq(t, `{"signed_in":false,"auth_disabled":false,"can_write_results":false}`, resp.Body.String())

	uid, err := store.GetOrCreateUserByEmail(ctx, "cap@example.com", "Cap", "!")
	require.NoError(t, err)
	session := auth.NewSessionSigner(testSessionSecret).Sign(uid, time.Now().UTC().Add(time.Hour))
	resp = tapi.Get("/api/auth/capabilities", "Cookie: conbench_session="+session)
	require.Equal(t, http.StatusOK, resp.Code)
	assert.JSONEq(t, `{"signed_in":true,"auth_disabled":false,"can_write_results":true}`, resp.Body.String())
}

func TestAuthCapabilitiesReportAuthDisabledResultWrites(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandlerWithAuthDisabled(t, iss, true)
	tapi := registerAuth(t, h)

	resp := tapi.Get("/api/auth/capabilities")
	require.Equal(t, http.StatusOK, resp.Code)
	assert.JSONEq(t, `{"signed_in":false,"auth_disabled":true,"can_write_results":true}`, resp.Body.String())
}

func TestCLIStartWithSessionIssuesCode(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, store, ctx := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	uid, err := store.GetOrCreateUserByEmail(ctx, "dev@example.com", "Dev", "!")
	require.NoError(t, err)
	session := auth.NewSessionSigner(testSessionSecret).Sign(uid, time.Now().UTC().Add(time.Hour))

	resp := tapi.Get("/api/auth/cli-start?redirect_uri=http://127.0.0.1:5000/callback&state=cli-state",
		"Cookie: conbench_session="+session)
	require.Equal(t, http.StatusFound, resp.Code)
	loc, err := url.Parse(resp.Header().Get("Location"))
	require.NoError(t, err)
	assert.Equal(t, "127.0.0.1:5000", loc.Host)
	assert.Equal(t, "cli-state", loc.Query().Get("state"))
	assert.NotEmpty(t, loc.Query().Get("code"))
}

func TestCLIStartRejectsNonLoopbackRedirect(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	for _, bad := range []string{
		"https://evil.example/callback",
		"http://localhost:5000/callback", // hostname, not a literal loopback IP
		"http://10.0.0.5:5000/callback",
	} {
		resp := tapi.Get("/api/auth/cli-start?redirect_uri=" + url.QueryEscape(bad) + "&state=s")
		assert.Equal(t, http.StatusBadRequest, resp.Code, bad)
	}
}

func TestCLIStartWithoutSessionBeginsOIDC(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	resp := tapi.Get("/api/auth/cli-start?redirect_uri=http://127.0.0.1:5000/callback&state=cli-state")
	require.Equal(t, http.StatusFound, resp.Code)
	assert.Contains(t, resp.Header().Get("Location"), iss.URL(), "redirects to the IdP")
	assert.Contains(t, resp.Header().Get("Set-Cookie"), "conbench_pending=")
}

func TestCLIExchangeMintsToken(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, store, ctx := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	uid, err := store.GetOrCreateUserByEmail(ctx, "dev@example.com", "Dev", "!")
	require.NoError(t, err)
	code := h.IssueCLICodeForTest(uid)

	resp := tapi.Post("/api/auth/cli-exchange", map[string]any{"code": code, "name": "cli laptop"})
	require.Equal(t, http.StatusOK, resp.Code, resp.Body.String())
	var out struct{ ID, Name, Token, Prefix string }
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	assert.Equal(t, "cli laptop", out.Name)
	require.NotEmpty(t, out.Token)
	assert.Equal(t, out.Token[:8], out.Prefix)

	// Single-use: the same code cannot mint twice.
	resp = tapi.Post("/api/auth/cli-exchange", map[string]any{"code": code, "name": "again"})
	assert.Equal(t, http.StatusBadRequest, resp.Code)
}

func TestCLIExchangeRedeemsCodeIssuedByAnotherHandlerInstance(t *testing.T) {
	iss := oidctestsupport.New(t)
	issuer := iss.Client(t)
	h1, store, ctx := newAuthHandler(t, iss)
	h2 := api.NewAuthHandler(
		issuer, store,
		auth.NewSessionSigner(testSessionSecret), auth.NewSigner(testSessionSecret),
		false, "https://conbench.example", api.NewDBCodeStore(store), false,
	)
	tapi2 := registerAuth(t, h2)

	uid, err := store.GetOrCreateUserByEmail(ctx, "dev@example.com", "Dev", "!")
	require.NoError(t, err)
	code := h1.IssueCLICodeForTest(uid)

	resp := tapi2.Post("/api/auth/cli-exchange", map[string]any{"code": code, "name": "cli laptop"})
	require.Equal(t, http.StatusOK, resp.Code, resp.Body.String())

	resp = tapi2.Post("/api/auth/cli-exchange", map[string]any{"code": code, "name": "again"})
	assert.Equal(t, http.StatusBadRequest, resp.Code, "code remains single-use across handler instances")
}

func TestCLIExchangeDefaultsEmptyName(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, store, ctx := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	uid, err := store.GetOrCreateUserByEmail(ctx, "dev@example.com", "Dev", "!")
	require.NoError(t, err)
	code := h.IssueCLICodeForTest(uid)

	resp := tapi.Post("/api/auth/cli-exchange", map[string]any{"code": code, "name": ""})
	require.Equal(t, http.StatusOK, resp.Code, resp.Body.String())
	var out struct{ Name string }
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	assert.Equal(t, "cli token", out.Name, "empty name defaults")
}

// TestCLIStartUnconfiguredOIDC pins that a no-session cli-start against a
// server with OIDC unconfigured returns 501 (auth endpoints are always
// registered), not a panic or 500.
func TestCLIStartUnconfiguredOIDC(t *testing.T) {
	h := api.NewAuthHandler(
		nil, nil,
		auth.NewSessionSigner(testSessionSecret), auth.NewSigner(testSessionSecret),
		false, "https://conbench.example", api.NewCodeStore(), false,
	)
	tapi := registerAuth(t, h)

	resp := tapi.Get("/api/auth/cli-start?redirect_uri=http://127.0.0.1:5000/callback&state=s")
	assert.Equal(t, http.StatusNotImplemented, resp.Code)
}

func TestCLICallbackCompletesLoopback(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	// A pending login carrying CLI context: the callback must mint the session
	// AND 302 to the loopback with a code (not to the app root).
	pending := api.SignPendingCLIForTest(testSessionSecret, "the-state", "the-nonce", "the-verifier",
		"http://127.0.0.1:5000/callback", "cli-state")
	iss.SetNextIDToken(map[string]any{"nonce": "the-nonce", "email": "dev@example.com", "name": "Dev"})

	resp := tapi.Get("/api/auth/callback?state=the-state&code=xyz", "Cookie: conbench_pending="+pending)
	require.Equal(t, http.StatusFound, resp.Code, resp.Body.String())
	loc, err := url.Parse(resp.Header().Get("Location"))
	require.NoError(t, err)
	assert.Equal(t, "127.0.0.1:5000", loc.Host, "callback returns to the CLI loopback")
	assert.Equal(t, "cli-state", loc.Query().Get("state"))
	assert.NotEmpty(t, loc.Query().Get("code"))
	assert.Contains(t, resp.Header().Get("Set-Cookie"), "conbench_session=", "session still set")
}

func TestLogoutClearsSession(t *testing.T) {
	iss := oidctestsupport.New(t)
	h, _, _ := newAuthHandler(t, iss)
	tapi := registerAuth(t, h)

	resp := tapi.Post("/api/auth/logout", "")
	require.Equal(t, http.StatusNoContent, resp.Code)
	set := resp.Header().Get("Set-Cookie")
	assert.Contains(t, set, "conbench_session=")
	assert.True(t, strings.Contains(set, "Max-Age=0") || strings.Contains(set, "Max-Age=-1"),
		"logout expires the cookie")
}
