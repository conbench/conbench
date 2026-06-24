// Package githubtest provides a fake GitHub HTTP API server for tests, plus the
// legacy conbench test fixtures (real GitHub API response bodies) as the parity
// oracle. The commit-provider, backfill, and ingestion tests all build on it so
// no test touches the live GitHub API.
package githubtest

import (
	"embed"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/stretchr/testify/require"
)

//go:embed testdata/*.json
var fixtures embed.FS

// Fixture returns the raw bytes of a legacy GitHub API fixture, e.g.
// "github_child.json".
func Fixture(t *testing.T, name string) []byte {
	t.Helper()
	b, err := fixtures.ReadFile("testdata/" + name)
	require.NoError(t, err, "read fixture %s", name)
	return b
}

// Server is a configurable fake GitHub API. Tests register handlers on Mux and
// can assert on the requests received (method, path, and raw query).
type Server struct {
	*httptest.Server
	Mux *http.ServeMux

	mu       sync.Mutex
	requests []string
}

// NewServer starts a fake GitHub API server and closes it on test cleanup.
// The server synchronizes only its own request log; custom handlers registered
// on Mux run on per-request goroutines, so any mutable state they share must
// be guarded by the test when requests can arrive concurrently.
func NewServer(t *testing.T) *Server {
	t.Helper()
	s := &Server{Mux: http.NewServeMux()}
	s.Server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.mu.Lock()
		s.requests = append(s.requests, r.Method+" "+r.URL.String())
		s.mu.Unlock()
		s.Mux.ServeHTTP(w, r)
	}))
	t.Cleanup(s.Close)
	return s
}

// Requests returns a copy of every request seen so far, formatted
// "METHOD /path?query".
func (s *Server) Requests() []string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]string(nil), s.requests...)
}

// HandleJSON registers a handler that responds 200 with the given body.
func (s *Server) HandleJSON(pattern string, body []byte) {
	s.Mux.HandleFunc(pattern, func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(body)
	})
}

// HandleStatus registers a handler that responds with the given status code
// and an empty JSON object body.
func (s *Server) HandleStatus(pattern string, code int) {
	s.Mux.HandleFunc(pattern, func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(code)
		_, _ = w.Write([]byte("{}"))
	})
}
