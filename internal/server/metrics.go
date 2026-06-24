package server

import (
	"fmt"
	"maps"
	"net/http"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"
)

const metricsContentType = "text/plain; version=0.0.4; charset=utf-8"

type metricKey struct {
	method string
	route  string
	status int
}

type requestMetric struct {
	count       uint64
	durationSum float64
}

type unknownCommitCounter interface {
	UnknownCommitCount() int64
}

type metricsRecorder struct {
	mu                 sync.Mutex
	requests           map[metricKey]requestMetric
	unknownCommitCount func() int64
}

func newMetricsRecorder(provider any) *metricsRecorder {
	unknownCommitCount := func() int64 { return 0 }
	if counter, ok := provider.(unknownCommitCounter); ok {
		unknownCommitCount = counter.UnknownCommitCount
	}
	return &metricsRecorder{
		requests:           make(map[metricKey]requestMetric),
		unknownCommitCount: unknownCommitCount,
	}
}

func instrumentHTTP(next http.Handler, recorder *metricsRecorder) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rec := &statusResponseWriter{ResponseWriter: w, status: http.StatusOK}
		start := time.Now()
		next.ServeHTTP(rec, r)
		recorder.observe(metricMethodLabel(r.Method), routeLabel(r.URL.Path), rec.status, time.Since(start).Seconds())
	})
}

func (m *metricsRecorder) observe(method, route string, status int, durationSeconds float64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	key := metricKey{method: method, route: route, status: status}
	value := m.requests[key]
	value.count++
	value.durationSum += durationSeconds
	m.requests[key] = value
}

func (m *metricsRecorder) serveMetrics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", http.MethodGet+", "+http.MethodHead)
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	w.Header().Set("Content-Type", metricsContentType)
	if r.Method == http.MethodHead {
		return
	}

	snapshot := m.snapshot()
	_, _ = fmt.Fprint(w, "# HELP conbench_up Constant 1 when the Go server is serving requests.\n")
	_, _ = fmt.Fprint(w, "# TYPE conbench_up gauge\n")
	_, _ = fmt.Fprint(w, "conbench_up 1\n")
	_, _ = fmt.Fprint(w, "# HELP conbench_github_unknown_commits_total Total commit resolves that degraded to unknown GitHub metadata since process start.\n")
	_, _ = fmt.Fprint(w, "# TYPE conbench_github_unknown_commits_total counter\n")
	_, _ = fmt.Fprintf(w, "conbench_github_unknown_commits_total %d\n", m.unknownCommitCount())
	_, _ = fmt.Fprint(w, "# HELP conbench_http_requests_total Total HTTP requests by method, low-cardinality route, and status code.\n")
	_, _ = fmt.Fprint(w, "# TYPE conbench_http_requests_total counter\n")
	for _, key := range sortedMetricKeys(snapshot) {
		labels := metricLabels(key)
		_, _ = fmt.Fprintf(w, "conbench_http_requests_total{%s} %d\n", labels, snapshot[key].count)
	}
	_, _ = fmt.Fprint(w, "# HELP conbench_http_request_duration_seconds HTTP request duration summary by method, low-cardinality route, and status code.\n")
	_, _ = fmt.Fprint(w, "# TYPE conbench_http_request_duration_seconds summary\n")
	for _, key := range sortedMetricKeys(snapshot) {
		labels := metricLabels(key)
		value := snapshot[key]
		_, _ = fmt.Fprintf(w, "conbench_http_request_duration_seconds_count{%s} %d\n", labels, value.count)
		_, _ = fmt.Fprintf(w, "conbench_http_request_duration_seconds_sum{%s} %.9f\n", labels, value.durationSum)
	}
}

func (m *metricsRecorder) snapshot() map[metricKey]requestMetric {
	m.mu.Lock()
	defer m.mu.Unlock()

	return maps.Clone(m.requests)
}

type statusResponseWriter struct {
	http.ResponseWriter
	status int
	wrote  bool
}

func (w *statusResponseWriter) WriteHeader(status int) {
	if w.wrote {
		return
	}
	w.wrote = true
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}

func (w *statusResponseWriter) Write(data []byte) (int, error) {
	if !w.wrote {
		w.wrote = true
	}
	return w.ResponseWriter.Write(data)
}

func (w *statusResponseWriter) Unwrap() http.ResponseWriter {
	return w.ResponseWriter
}

func metricLabels(key metricKey) string {
	return "method=" + prometheusQuote(key.method) +
		",route=" + prometheusQuote(key.route) +
		",status=" + prometheusQuote(strconv.Itoa(key.status))
}

func metricMethodLabel(method string) string {
	switch method {
	case http.MethodGet, http.MethodHead, http.MethodPost, http.MethodPut, http.MethodPatch,
		http.MethodDelete, http.MethodOptions:
		return method
	default:
		return "OTHER"
	}
}

func sortedMetricKeys(values map[metricKey]requestMetric) []metricKey {
	keys := make([]metricKey, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	slices.SortFunc(keys, func(a, b metricKey) int {
		if c := strings.Compare(a.route, b.route); c != 0 {
			return c
		}
		if c := strings.Compare(a.method, b.method); c != 0 {
			return c
		}
		return a.status - b.status
	})
	return keys
}

func prometheusQuote(value string) string {
	quoted := strconv.Quote(value)
	return quoted
}

func routeLabel(path string) string {
	switch {
	case path == "/":
		return "/"
	case path == "/metrics":
		return "/metrics"
	case path == "/api/ping":
		return "/api/ping"
	case path == "/api/results":
		return "/api/results"
	case path == "/api/benchmark-results":
		return "/api/benchmark-results"
	case strings.HasPrefix(path, "/api/benchmark-results/"):
		return "/api/benchmark-results/{id}"
	case path == "/api/history":
		return "/api/history"
	case strings.HasPrefix(path, "/api/history/"):
		return "/api/history/{benchmark_result_id}"
	case path == "/api/series":
		return "/api/series"
	case path == "/api/compare/benchmark-results":
		return "/api/compare/benchmark-results"
	case path == "/api/ci/report":
		return "/api/ci/report"
	case path == "/api/alert-rules":
		return "/api/alert-rules"
	case strings.HasPrefix(path, "/api/alert-rules/") && strings.HasSuffix(path, "/events"):
		return "/api/alert-rules/{id}/events"
	case strings.HasPrefix(path, "/api/alert-rules/"):
		return "/api/alert-rules/{id}"
	case strings.HasPrefix(path, "/api/auth/"):
		return "/api/auth/*"
	case path == "/api/tokens":
		return "/api/tokens"
	case path == "/api/users/me":
		return "/api/users/me"
	case strings.HasPrefix(path, "/api/"):
		return "/api/*"
	case strings.HasPrefix(path, "/docs"):
		return "/docs"
	case strings.HasPrefix(path, "/openapi"):
		return "/openapi"
	default:
		return "spa"
	}
}
