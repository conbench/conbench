package server

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"testing/fstest"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
)

// TestNewHandlerServesAPIAndSPA proves the SPA catch-all is mounted without
// shadowing the API: /api/ping still routes to huma, while non-API paths fall to
// the embedded app shell. The store is nil because route registration never
// queries it (the same reason specAPI registers with a nil store), so this
// routing/precedence proof runs without Docker and under -short.
func TestNewHandlerServesAPIAndSPA(t *testing.T) {
	assets := fstest.MapFS{
		"index.html": {Data: []byte("<!doctype html><title>conbench</title>")},
	}
	authHandler := api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
	handler := newHandler(nil, auth.New("", true, nil, nil), commit.LocalProvider{}, authHandler, assets)

	t.Run("api ping wins over the SPA catch-all", func(t *testing.T) {
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/ping", nil))
		require.Equal(t, http.StatusOK, rec.Code)
		assert.NotContains(t, rec.Body.String(), "<title>conbench</title>")
	})

	t.Run("client route serves the app shell", func(t *testing.T) {
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/benchmarks/history/abc", nil))
		require.Equal(t, http.StatusOK, rec.Code)
		assert.Contains(t, rec.Body.String(), "<title>conbench</title>")
	})

	t.Run("wrong-method API path returns a plain 404, never the SPA shell", func(t *testing.T) {
		// Only POST /api/results and GET /api/ping are registered. A wrong-method
		// request is caught by the catch-all's /api guard and returns 404, not
		// huma's 405/Allow: an accepted trade-off of the single-mux design (see
		// newHandler). What must hold is that an /api path never yields the shell.
		for _, p := range []struct{ method, path string }{
			{http.MethodGet, "/api/results"},
			{http.MethodDelete, "/api/ping"},
		} {
			rec := httptest.NewRecorder()
			handler.ServeHTTP(rec, httptest.NewRequest(p.method, p.path, nil))
			assert.Equal(t, http.StatusNotFound, rec.Code, p.path)
			assert.NotContains(t, rec.Body.String(), "<title>conbench</title>", p.path)
		}
	})

	t.Run("traversal-shaped paths are canonicalized by the mux, never escaping the embed", func(t *testing.T) {
		// ServeMux cleans the request path before the SPA handler runs, so a raw
		// ".." is redirected to its normalized in-app path -- never to an OS file.
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/../../etc/passwd", nil))
		require.Equal(t, http.StatusTemporaryRedirect, rec.Code)
		require.Equal(t, "/etc/passwd", rec.Header().Get("Location"))

		// Following that redirect lands on the SPA shell (the embed's fs.FS sandbox
		// makes reading outside it impossible), not the host's /etc/passwd.
		rec = httptest.NewRecorder()
		handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/etc/passwd", nil))
		assert.Equal(t, http.StatusOK, rec.Code)
		assert.Contains(t, rec.Body.String(), "<title>conbench</title>")
	})
}
