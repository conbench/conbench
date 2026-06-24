package server

import (
	"bytes"
	"io/fs"
	"net/http"
	"path"
	"strings"
	"time"
)

// spaHandler serves the embedded single-page app: it returns a matching static
// asset when one exists, otherwise falls back to index.html so client-side
// routes (e.g. /benchmarks/history/:id) resolve to the app shell. API paths are
// never served as HTML, and only GET/HEAD are answered. path.Clean plus the
// sandboxed fs.FS keep traversal-shaped paths inside the embed (the wrapping
// ServeMux also canonicalizes ".." before this handler runs in production).
func spaHandler(assets fs.FS) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api" || strings.HasPrefix(r.URL.Path, "/api/") {
			http.NotFound(w, r)
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			http.NotFound(w, r)
			return
		}
		name := strings.TrimPrefix(path.Clean(r.URL.Path), "/")
		if name != "" && serveAsset(w, r, assets, name) {
			return
		}
		if !serveAsset(w, r, assets, "index.html") {
			http.NotFound(w, r)
		}
	})
}

// serveAsset writes the named file from assets and reports whether it existed.
// Directories and missing files yield false so the caller can fall back to the
// app shell. fs.ReadFile rejects ".." paths, so traversal is not possible.
func serveAsset(w http.ResponseWriter, r *http.Request, assets fs.FS, name string) bool {
	data, err := fs.ReadFile(assets, name)
	if err != nil {
		return false
	}
	http.ServeContent(w, r, path.Base(name), time.Time{}, bytes.NewReader(data))
	return true
}
