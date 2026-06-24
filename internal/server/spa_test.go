package server

import (
	"io/fs"
	"net/http"
	"net/http/httptest"
	"testing"
	"testing/fstest"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func testAssets() fs.FS {
	return fstest.MapFS{
		"index.html":    {Data: []byte("<!doctype html><title>conbench</title>")},
		"assets/app.js": {Data: []byte("console.log('app')")},
	}
}

func doReq(t *testing.T, h http.Handler, method, target string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, target, nil))
	return rec
}

func TestSPAHandler(t *testing.T) {
	h := spaHandler(testAssets())

	t.Run("serves index.html at root", func(t *testing.T) {
		rec := doReq(t, h, http.MethodGet, "/")
		require.Equal(t, http.StatusOK, rec.Code)
		assert.Contains(t, rec.Body.String(), "<title>conbench</title>")
		assert.Contains(t, rec.Header().Get("Content-Type"), "text/html")
	})

	t.Run("serves an existing asset", func(t *testing.T) {
		rec := doReq(t, h, http.MethodGet, "/assets/app.js")
		require.Equal(t, http.StatusOK, rec.Code)
		assert.Contains(t, rec.Body.String(), "console.log('app')")
		assert.Contains(t, rec.Header().Get("Content-Type"), "javascript")
	})

	t.Run("falls back to index.html for client routes", func(t *testing.T) {
		rec := doReq(t, h, http.MethodGet, "/benchmarks/history/abc123")
		require.Equal(t, http.StatusOK, rec.Code)
		assert.Contains(t, rec.Body.String(), "<title>conbench</title>")
	})

	t.Run("404s API paths instead of serving HTML", func(t *testing.T) {
		for _, p := range []string{"/api", "/api/", "/api/unknown"} {
			rec := doReq(t, h, http.MethodGet, p)
			assert.Equal(t, http.StatusNotFound, rec.Code, p)
			assert.NotContains(t, rec.Body.String(), "<title>conbench</title>", p)
		}
	})

	t.Run("does not serve HTML for non-GET/HEAD", func(t *testing.T) {
		rec := doReq(t, h, http.MethodPost, "/benchmarks/history/abc123")
		assert.Equal(t, http.StatusNotFound, rec.Code)
		assert.NotContains(t, rec.Body.String(), "<title>conbench</title>")
	})

	t.Run("serves HEAD of the app shell", func(t *testing.T) {
		rec := doReq(t, h, http.MethodHead, "/")
		assert.Equal(t, http.StatusOK, rec.Code)
	})

	t.Run("does not leak an asset body on non-GET", func(t *testing.T) {
		rec := doReq(t, h, http.MethodPost, "/assets/app.js")
		assert.Equal(t, http.StatusNotFound, rec.Code)
		assert.NotContains(t, rec.Body.String(), "console.log('app')")
	})

	t.Run("out-of-embed paths resolve to the shell, never an external file", func(t *testing.T) {
		// path.Clean collapses ".." within URL-space and fs.ReadFile on the
		// sandboxed embed refuses anything outside it, so a traversal-shaped or
		// absolute path lands on the app shell rather than an OS file. (In
		// production ServeMux also canonicalizes ".." before this handler; see the
		// newHandler-level test.)
		for _, p := range []string{"/../../etc/passwd", "/etc/passwd"} {
			rec := doReq(t, h, http.MethodGet, p)
			assert.Equal(t, http.StatusOK, rec.Code, p)
			assert.Contains(t, rec.Body.String(), "<title>conbench</title>", p)
		}
	})
}

func TestSPAHandlerMissingIndex(t *testing.T) {
	h := spaHandler(fstest.MapFS{}) // SPA not built: no index.html present
	rec := doReq(t, h, http.MethodGet, "/whatever")
	assert.Equal(t, http.StatusNotFound, rec.Code)
}
