package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/oidcauth/oidctestsupport"
	"github.com/conbench/conbench/internal/server"
)

// TestAuthLoginLoopback drives the full CLI loopback login against a real server
// wired to a live (fake) OIDC issuer. The injected programmatic browser follows
// the whole redirect chain (cli-start -> IdP /authorize -> server /callback ->
// loopback) with a cookie jar, so the pending cookie reaches the callback. The
// callback completes the loopback redirect with a one-time code, the CLI
// exchanges it for an API token, and persists it. The test then proves the
// token authenticates a `auth token list` call.
func TestAuthLoginLoopback(t *testing.T) {
	iss := oidctestsupport.New(t)
	iss.SetNextIDToken(map[string]any{"email": "dev@example.com", "name": "Dev"})

	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	const secret = "test-session-secret-which-is-long-enough"
	sessions := auth.NewSessionSigner(secret)

	// The server and the OIDC client are mutually dependent: the IdP must
	// redirect the browser to the live server's callback URL, which is only
	// known once the test server starts. Start a server fronted by a late-bound
	// handler, then wire the real handler with srv.URL as the OIDC redirect.
	var handler http.Handler
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		handler.ServeHTTP(w, r)
	}))
	t.Cleanup(srv.Close)

	authHandler := api.NewAuthHandler(
		iss.ClientWithRedirect(t, srv.URL+"/api/auth/callback"),
		store, sessions, auth.NewSigner(secret),
		false, "https://app.example", api.NewCodeStore(), false,
	)
	authn := auth.New("", false, store, sessions)
	handler = server.New(store, authn, commit.LocalProvider{}, authHandler)

	// Inject a programmatic browser: follow the cli-start URL through every
	// redirect with a cookie jar (so the pending cookie reaches the callback).
	jar, err := cookiejar.New(nil)
	require.NoError(t, err)
	browser := &http.Client{Jar: jar}
	prevOpener := browserOpener
	browserOpener = func(target string) error {
		go func() {
			resp, err := browser.Get(target)
			if err == nil {
				resp.Body.Close()
			}
		}()
		return nil
	}
	t.Cleanup(func() { browserOpener = prevOpener })

	// Keep the test hermetic: write credentials to a temp file, not the host
	// config dir (which os.UserConfigDir resolves and XDG cannot relocate on
	// macOS).
	credsPath := filepath.Join(t.TempDir(), "credentials.json")
	prevPathFn := credentialsPathFn
	credentialsPathFn = func() (string, error) { return credsPath, nil }
	t.Cleanup(func() { credentialsPathFn = prevPathFn })

	var stdout, stderr strings.Builder
	code := runAuthLogin(srv.URL, &stdout, &stderr)
	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Positive(t, iss.TokenCalls(),
		"login took the real OIDC round-trip (a code exchange happened)")
	assert.Contains(t, stdout.String(), "cb_", "prints the token prefix")
	require.Equal(t, 1, strings.Count(strings.TrimRight(stdout.String(), "\n"), "\n")+1,
		"login prints exactly one stdout line")

	// The credentials file now holds a token for this server.
	creds, err := loadCredentials(credsPath)
	require.NoError(t, err)
	token := creds[srv.URL]
	require.NotEmpty(t, token, "login persisted a token for the server")
	assert.NotContains(t, stdout.String(), token, "never print the plaintext token")

	// The persisted token authenticates a token-list call: the CLI resolves it
	// from the same credentials file via the precedence path.
	var listOut, listErr bytes.Buffer
	code = run([]string{"auth", "token", "list", "--server", srv.URL}, &listOut, &listErr)
	require.Equal(t, 0, code, "stderr=%s", listErr.String())
	var listed struct {
		Tokens []struct {
			ID     string `json:"id"`
			Name   string `json:"name"`
			Prefix string `json:"prefix"`
		} `json:"tokens"`
	}
	require.NoError(t, json.Unmarshal(listOut.Bytes(), &listed))
	require.Len(t, listed.Tokens, 1)
	assert.Equal(t, token[:8], listed.Tokens[0].Prefix)
	assert.Contains(t, listed.Tokens[0].Name, "cli ")

	// Revoking an unknown id (while still authenticated with the live token)
	// reports 404 -> "token not found". This must run before revoking the real
	// token, since revoking the token used for auth would leave later calls
	// unauthenticated (401), not 404.
	var unknownOut, unknownErr bytes.Buffer
	code = run([]string{"auth", "token", "revoke", "does-not-exist", "--server", srv.URL}, &unknownOut, &unknownErr)
	assert.Equal(t, 1, code)
	assert.Empty(t, unknownOut.String())
	assert.Contains(t, unknownErr.String(), "token not found")

	// Revoking the caller's own token succeeds.
	id := listed.Tokens[0].ID
	var revokeOut, revokeErr bytes.Buffer
	code = run([]string{"auth", "token", "revoke", id, "--server", srv.URL}, &revokeOut, &revokeErr)
	require.Equal(t, 0, code, "stderr=%s", revokeErr.String())
	var revoked struct {
		Revoked bool   `json:"revoked"`
		ID      string `json:"id"`
	}
	require.NoError(t, json.Unmarshal(revokeOut.Bytes(), &revoked))
	assert.True(t, revoked.Revoked)
	assert.Equal(t, id, revoked.ID)
	assert.NotContains(t, revokeOut.String(), token, "never print the plaintext token")
}

func TestParseAuthTokenArgsExplicitSourcesDoNotNeedConfigDir(t *testing.T) {
	prevPathFn := credentialsPathFn
	credentialsPathFn = func() (string, error) { return "", errors.New("config unavailable") }
	t.Cleanup(func() { credentialsPathFn = prevPathFn })

	var got authTokenConfig
	list := newAuthTokenCommand(
		"list",
		"list",
		"List API tokens.",
		io.Discard,
		func(_ context.Context, _ string, parsed authTokenConfig, _ io.Writer) error {
			got = parsed
			return nil
		},
	)
	require.NoError(t, executeParseCommand(list, []string{"--server", "https://s.example", "--token", "from-flag"}))
	assert.Equal(t, "from-flag", got.token)

	t.Setenv("CONBENCH_TOKEN", "from-env")
	revoke := newAuthTokenCommand(
		"revoke",
		"revoke <id>",
		"Revoke an API token.",
		io.Discard,
		func(_ context.Context, _ string, parsed authTokenConfig, _ io.Writer) error {
			got = parsed
			return nil
		},
	)
	require.NoError(t, executeParseCommand(revoke, []string{"token-id", "--server", "https://s.example"}))
	assert.Equal(t, "from-env", got.token)
	assert.Equal(t, "token-id", got.id)
}

// TestLoopbackCallbackRejectsStateMismatch pins the CLI-side CSRF control: the
// loopback callback must reject a code delivered with a state that does not
// match the one this login generated, signalling an error and never publishing
// the code.
func TestLoopbackCallbackRejectsStateMismatch(t *testing.T) {
	loop := &loopback{
		state:  "the-real-state",
		codeCh: make(chan string, 1),
		errCh:  make(chan error, 1),
	}

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/callback?code=stolen&state=attacker-state", nil)
	loop.handleCallback(rec, req)

	assert.Equal(t, http.StatusBadRequest, rec.Code)
	select {
	case err := <-loop.errCh:
		assert.Contains(t, err.Error(), "state mismatch")
	default:
		assert.Fail(t, "expected a state-mismatch error to be signalled")
	}
	select {
	case c := <-loop.codeCh:
		assert.Failf(t, "code must not be published on state mismatch", "got %q", c)
	default:
	}
}

// TestLoopbackCallbackAcceptsMatchingState confirms the happy path publishes the
// code when the state matches.
func TestLoopbackCallbackAcceptsMatchingState(t *testing.T) {
	loop := &loopback{
		state:  "the-real-state",
		codeCh: make(chan string, 1),
		errCh:  make(chan error, 1),
	}

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/callback?code=good-code&state=the-real-state", nil)
	loop.handleCallback(rec, req)

	assert.Equal(t, http.StatusOK, rec.Code)
	select {
	case c := <-loop.codeCh:
		assert.Equal(t, "good-code", c)
	default:
		assert.Fail(t, "expected the code to be published")
	}
}
