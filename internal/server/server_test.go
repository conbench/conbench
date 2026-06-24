package server_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/seed"
	"github.com/conbench/conbench/internal/server"
	"github.com/conbench/conbench/internal/service"
)

// noAuthHandler builds an auth handler with no live OIDC client or DB, for
// tests that wire the server but do not exercise the login flow.
func noAuthHandler() *api.AuthHandler {
	return api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
}

// TestServerServesSeededHistory boots the real net/http handler (humago, not
// humatest) over real Postgres and checks the health and history endpoints after
// seeding — exercising the full routing the dev server uses.
func TestServerServesSeededHistory(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	s, err := seed.Run(ctx, store)
	require.NoError(t, err)

	handler := server.New(store, auth.New("", true, store, nil), commit.LocalProvider{}, noAuthHandler())

	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/ping", nil))
	require.Equal(t, http.StatusOK, rec.Code, "GET /api/ping; body %s", rec.Body.String())

	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/history?fingerprint="+s.Fingerprint, nil))
	require.Equal(t, http.StatusOK, rec.Code, "GET /api/history; body %s", rec.Body.String())
	var series service.HistorySeries
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &series))
	assert.Len(t, series.Samples, seed.IncludedHistoryPoints)
}

// TestOpenAPISpec emits the OpenAPI document straight from the huma structs with
// no database, pinning the registered paths and byte-for-byte determinism — the
// property the checked-in api/openapi.yaml drift gate relies on.
func TestOpenAPISpec(t *testing.T) {
	spec, err := server.OpenAPISpec()
	require.NoError(t, err)
	require.NotEmpty(t, spec)

	doc := string(spec)
	assert.Contains(t, doc, "openapi: 3.1")
	for _, path := range []string{
		"/api/results",
		"/api/benchmark-results/{id}",
		"/api/history/{benchmark_result_id}",
		"/api/history",
		"/api/alert-rules",
		"/api/alert-rules/{id}/events",
		"/api/ping",
	} {
		assert.Contains(t, doc, path)
	}

	again, err := server.OpenAPISpec()
	require.NoError(t, err)
	assert.Equal(t, string(spec), string(again), "spec emission must be deterministic")
}

// TestOpenAPISpec30 emits the OpenAPI 3.0 downgrade and pins its version and
// determinism — the property the checked-in api/openapi-3.0.yaml drift gate and
// the Go client generator (oapi-codegen) rely on.
func TestOpenAPISpec30(t *testing.T) {
	spec, err := server.OpenAPISpec30()
	require.NoError(t, err)
	require.NotEmpty(t, spec)

	doc := string(spec)
	assert.Contains(t, doc, "openapi: 3.0")
	// The downgrade must express nullability as `nullable: true`, not leak 3.1
	// type-union null (which oapi-codegen does not understand).
	assert.Contains(t, doc, "nullable: true")
	assert.NotContains(t, doc, `- "null"`)

	again, err := server.OpenAPISpec30()
	require.NoError(t, err)
	assert.Equal(t, string(spec), string(again), "downgrade emission must be deterministic")
}

// TestEnsureSchemaApplies proves the dev schema bootstrap creates the schema on a
// bare database and is a no-op when it already exists.
func TestEnsureSchemaApplies(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)

	// Simulate a bare database (dbtest applies the schema; drop it).
	_, err := pool.Exec(ctx, "DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
	require.NoError(t, err, "reset schema")

	require.NoError(t, server.EnsureSchema(ctx, pool), "EnsureSchema (apply)")
	_, err = db.NewStore(pool).CountBenchmarkResults(ctx)
	require.NoError(t, err, "schema not applied")
	// Idempotent: a second call is a no-op.
	require.NoError(t, server.EnsureSchema(ctx, pool), "EnsureSchema (no-op)")
}
