package api_test

import (
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
)

// decode unmarshals a JSON response body into v, failing the test on error.
func decode(t *testing.T, body []byte, v any) {
	t.Helper()
	require.NoError(t, json.Unmarshal(body, v))
}

func TestTokenCRUDOwnership(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	sessions := auth.NewSessionSigner("sek")
	_, tapi := humatest.New(t)
	api.NewTokenHandler(store, auth.New("static-op", false, store, sessions)).Register(tapi)

	u1 := dbtest.SeedUser(t, ctx, pool)
	u2 := dbtest.SeedUser(t, ctx, pool)
	s1 := "Cookie: conbench_session=" + sessions.Sign(u1, time.Now().UTC().Add(time.Hour))
	s2 := "Cookie: conbench_session=" + sessions.Sign(u2, time.Now().UTC().Add(time.Hour))

	// Mint as u1.
	resp := tapi.Post("/api/tokens", s1, map[string]any{"name": "ci"})
	require.Equal(t, http.StatusCreated, resp.Code, resp.Body.String())
	var created struct{ ID, Name, Token, Prefix string }
	decode(t, resp.Body.Bytes(), &created)
	require.NotEmpty(t, created.Token, "plaintext returned once")
	require.GreaterOrEqual(t, len(created.Token), 8)
	assert.Equal(t, created.Token[:8], created.Prefix)

	// List as u1 -> one token, no secret.
	resp = tapi.Get("/api/tokens", s1)
	require.Equal(t, http.StatusOK, resp.Code)
	assert.Contains(t, resp.Body.String(), created.ID)
	assert.NotContains(t, resp.Body.String(), created.Token, "list never includes plaintext")
	assert.NotContains(t, resp.Body.String(), auth.HashToken(created.Token),
		"list never includes the token hash")

	// List as u2 -> does not see u1's token.
	resp = tapi.Get("/api/tokens", s2)
	require.Equal(t, http.StatusOK, resp.Code)
	assert.NotContains(t, resp.Body.String(), created.ID)

	// u2 cannot delete u1's token -> 404 (not 403; do not reveal existence).
	resp = tapi.Delete("/api/tokens/"+created.ID, s2)
	assert.Equal(t, http.StatusNotFound, resp.Code)

	// u1 deletes own token -> 204.
	resp = tapi.Delete("/api/tokens/"+created.ID, s1)
	assert.Equal(t, http.StatusNoContent, resp.Code)

	// Idempotent: owner re-deletes the already-revoked token -> 204.
	resp = tapi.Delete("/api/tokens/"+created.ID, s1)
	assert.Equal(t, http.StatusNoContent, resp.Code, "re-delete is idempotent")

	// Unknown id -> 404.
	resp = tapi.Delete("/api/tokens/does-not-exist", s1)
	assert.Equal(t, http.StatusNotFound, resp.Code)
}

func TestTokenCRUDRequiresUserPrincipal(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	_, tapi := humatest.New(t)
	api.NewTokenHandler(store, auth.New("static-op", false, store, auth.NewSessionSigner("sek"))).Register(tapi)

	// No credential -> 401.
	resp := tapi.Post("/api/tokens", map[string]any{"name": "x"})
	assert.Equal(t, http.StatusUnauthorized, resp.Code)

	// Static operator token authenticates but has no user -> 403.
	resp = tapi.Post("/api/tokens", "Authorization: Bearer static-op", map[string]any{"name": "x"})
	assert.Equal(t, http.StatusForbidden, resp.Code)
}

func TestCreateTokenRejectsEmptyName(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	sessions := auth.NewSessionSigner("sek")
	_, tapi := humatest.New(t)
	api.NewTokenHandler(store, auth.New("static-op", false, store, sessions)).Register(tapi)

	u := dbtest.SeedUser(t, ctx, pool)
	s := "Cookie: conbench_session=" + sessions.Sign(u, time.Now().UTC().Add(time.Hour))

	// Authenticated user, empty name -> 422.
	resp := tapi.Post("/api/tokens", s, map[string]any{"name": ""})
	assert.Equal(t, http.StatusUnprocessableEntity, resp.Code)

	// The principal check precedes the name check: an unauthenticated empty-name
	// POST is rejected as 401, not 422.
	resp = tapi.Post("/api/tokens", map[string]any{"name": ""})
	assert.Equal(t, http.StatusUnauthorized, resp.Code)
}
