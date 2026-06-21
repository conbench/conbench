package server

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
)

func TestMetricsEndpointReportsRequests(t *testing.T) {
	authHandler := api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
	handler := newHandler(nil, auth.New("", true, nil, nil), commit.LocalProvider{}, authHandler, testAssets())

	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/ping", nil))
	require.Equal(t, http.StatusOK, rec.Code)

	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "text/plain; version=0.0.4; charset=utf-8", rec.Header().Get("Content-Type"))
	body := rec.Body.String()
	assert.Contains(t, body, "conbench_up 1\n")
	assert.Contains(t, body, `conbench_http_requests_total{method="GET",route="/api/ping",status="200"} 1`)
	assert.Contains(t, body, `conbench_http_request_duration_seconds_count{method="GET",route="/api/ping",status="200"} 1`)
	assert.Contains(t, body, `conbench_http_request_duration_seconds_sum{method="GET",route="/api/ping",status="200"} `)
}

func TestMetricsEndpointReportsUnknownCommitCountForLocalProvider(t *testing.T) {
	authHandler := api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
	handler := newHandler(nil, auth.New("", true, nil, nil), commit.LocalProvider{}, authHandler, testAssets())

	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	require.Equal(t, http.StatusOK, rec.Code)
	body := rec.Body.String()
	assert.Contains(t, body, "# HELP conbench_github_unknown_commits_total")
	assert.Contains(t, body, "# TYPE conbench_github_unknown_commits_total counter")
	assert.Contains(t, body, "conbench_github_unknown_commits_total 0\n")
}

func TestMetricsEndpointReportsUnknownCommitCountFromProvider(t *testing.T) {
	authHandler := api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
	handler := newHandler(nil, auth.New("", true, nil, nil), fakeUnknownCommitProvider{count: 42}, authHandler, testAssets())

	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	require.Equal(t, http.StatusOK, rec.Code)
	assert.Contains(t, rec.Body.String(), "conbench_github_unknown_commits_total 42\n")
}

func TestMetricsRouteLabelsAvoidRawIDs(t *testing.T) {
	authHandler := api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
	handler := newHandler(nil, auth.New("", true, nil, nil), commit.LocalProvider{}, authHandler, testAssets())

	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/unknown/abc123", nil))
	require.Equal(t, http.StatusNotFound, rec.Code)

	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	require.Equal(t, http.StatusOK, rec.Code)
	body := rec.Body.String()
	assert.Contains(t, body, `route="/api/*"`)
	assert.NotContains(t, body, "abc123")
}

func TestMetricsRouteLabelsAlertRulePaths(t *testing.T) {
	assert.Equal(t, "/api/alert-rules", routeLabel("/api/alert-rules"))
	assert.Equal(t, "/api/alert-rules/{id}", routeLabel("/api/alert-rules/rule-1"))
	assert.Equal(t, "/api/alert-rules/{id}/events", routeLabel("/api/alert-rules/rule-1/events"))
	assert.Equal(t, "/api/alert-rules/{id}/events", routeLabel("/api/alert-rules/rule-2/events"))
}

func TestMetricsMethodLabelsAvoidRawInput(t *testing.T) {
	authHandler := api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
	handler := newHandler(nil, auth.New("", true, nil, nil), commit.LocalProvider{}, authHandler, testAssets())

	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest("BREW", "/api/ping", nil))
	require.Equal(t, http.StatusNotFound, rec.Code)

	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	require.Equal(t, http.StatusOK, rec.Code)
	body := rec.Body.String()
	assert.Contains(t, body, `conbench_http_requests_total{method="OTHER",route="/api/ping",status="404"} 1`)
	assert.NotContains(t, body, `method="BREW"`)
}

func TestMetricsNotInOpenAPI(t *testing.T) {
	spec, err := OpenAPISpec()
	require.NoError(t, err)
	assert.NotContains(t, string(spec), "/metrics")
}

type fakeUnknownCommitProvider struct {
	count int64
}

func (p fakeUnknownCommitProvider) Resolve(context.Context, commit.Request) (*commit.Info, error) {
	return &commit.Info{}, nil
}

func (p fakeUnknownCommitProvider) UnknownCommitCount() int64 {
	return p.count
}
