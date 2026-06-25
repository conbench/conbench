package server_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

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
	"github.com/conbench/conbench/internal/storage"
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

// TestServerServesSeededProductSmokeCorpus pins the deterministic seed data as
// a product-smoke corpus, not just a demo history series. These are the same
// read surfaces the docs screenshot and browser smoke harnesses need after they
// move off production-clone-only sample selection.
func TestServerServesSeededProductSmokeCorpus(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	s, err := seed.Run(ctx, store)
	require.NoError(t, err)
	targets := s.ProductSmoke
	require.NotEmpty(t, targets.Fingerprint)
	require.NotEmpty(t, targets.LatestResultID)
	require.NotEmpty(t, targets.BaselineResultID)
	require.NotEmpty(t, targets.ContenderResultID)
	require.NotEmpty(t, targets.RecentRunID)
	require.NotEmpty(t, targets.RecentBatchID)
	require.NotEmpty(t, targets.CIRegressionRunID)
	require.NotEmpty(t, targets.CIRegressionCommitSHA)
	require.NotEmpty(t, targets.CIRegressionRunReason)
	require.NotEmpty(t, targets.CIActionRequiredRunID)
	require.NotEmpty(t, targets.CIActionRequiredCommitSHA)

	sessions := auth.NewSessionSigner("sek")
	userID := dbtest.SeedUser(t, ctx, pool)
	authn := auth.New("static-op", false, store, sessions)
	authHandler := api.NewAuthHandler(nil, store, sessions, auth.NewSigner("sek"), false, "", api.NewCodeStore(), false)
	handler := server.New(store, authn, commit.LocalProvider{}, authHandler)

	detail := getAPI[service.ResultDetail](t, handler, "/api/benchmark-results/"+url.PathEscape(targets.LatestResultID))
	assert.Equal(t, targets.LatestResultID, detail.ID)
	assert.Equal(t, targets.Fingerprint, detail.HistoryFingerprint)
	assert.Equal(t, "demo-benchmark", detail.Tags["name"])

	recent := getAPI[service.RecentRunsPage](t, handler, "/api/runs/recent?page_size=25")
	assertRunPresent(t, recent.Runs, targets.RecentRunID, targets.RecentBatchID)

	seriesPage := getAPI[api.SeriesPage](t, handler, "/api/series?fingerprint="+url.QueryEscape(targets.Fingerprint)+"&page_size=1")
	require.Len(t, seriesPage.Series, 1)
	assert.Equal(t, targets.Fingerprint, seriesPage.Series[0].HistoryFingerprint)
	assert.Equal(t, targets.LatestResultID, seriesPage.Series[0].LatestResultID)

	history := getAPI[service.HistorySeries](t, handler, "/api/history?fingerprint="+url.QueryEscape(targets.Fingerprint))
	require.Len(t, history.Samples, seed.IncludedHistoryPoints)
	assert.Equal(t, targets.BaselineResultID, history.Samples[0].BenchmarkResultID)
	assert.Equal(t, targets.ContenderResultID, history.Samples[len(history.Samples)-1].BenchmarkResultID)

	compareQuery := url.Values{
		"baseline_result_id":  {targets.BaselineResultID},
		"contender_result_id": {targets.ContenderResultID},
	}
	compare := getAPI[service.CompareResult](t, handler, "/api/compare/benchmark-results?"+compareQuery.Encode())
	assert.Equal(t, targets.BaselineResultID, compare.Baseline.BenchmarkResultID)
	assert.Equal(t, targets.ContenderResultID, compare.Contender.BenchmarkResultID)
	require.NotNil(t, compare.Analysis.Pairwise)
	assert.True(t, compare.Analysis.Pairwise.RegressionIndicated)

	regressionQuery := url.Values{
		"repository": {targets.Repository},
		"commit_sha": {targets.CIRegressionCommitSHA},
		"run_ids":    {targets.CIRegressionRunID},
		"baseline":   {string(service.CIReportBaselineForkPoint)},
	}
	regressionReport := getAPI[service.CIReport](t, handler, "/api/ci/report?"+regressionQuery.Encode())
	assert.Equal(t, service.CIReportStatusFailure, regressionReport.Status)
	require.Len(t, regressionReport.Runs, 1)
	assert.Equal(t, targets.CIRegressionRunID, regressionReport.Runs[0].RunID)
	require.Len(t, regressionReport.Runs[0].Comparisons, 1)
	assert.Equal(t, service.CIReportRowStatusRegressed, regressionReport.Runs[0].Comparisons[0].Status)

	actionQuery := url.Values{
		"repository": {targets.Repository},
		"commit_sha": {targets.CIActionRequiredCommitSHA},
		"run_ids":    {targets.CIActionRequiredRunID},
		"baseline":   {string(service.CIReportBaselineForkPoint)},
	}
	actionReport := getAPI[service.CIReport](t, handler, "/api/ci/report?"+actionQuery.Encode())
	assert.Equal(t, service.CIReportStatusActionRequired, actionReport.Status)
	require.Len(t, actionReport.Runs, 1)
	require.NotNil(t, actionReport.Runs[0].BaselineError)
	assert.Equal(t, service.CIReportBaselineErrorDefaultBranchRun, actionReport.Runs[0].BaselineError.Code)

	rule, err := store.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Seeded PR regression", Repository: targets.Repository,
		Baseline: string(service.CIReportBaselineForkPoint), Threshold: 5, ThresholdZ: 5,
		RunReason: &targets.CIRegressionRunReason, Enabled: true, CreatedAt: dayForSmokeTest(),
	})
	require.NoError(t, err)
	alertSummary, err := service.NewAlertEvaluator(
		store, service.NewCIReporter(store, ""), func() time.Time { return dayForSmokeTest().Add(time.Hour) },
	).Evaluate(ctx, service.AlertEvaluationOptions{})
	require.NoError(t, err)
	assert.Equal(t, 1, alertSummary.Opened)
	require.Len(t, alertSummary.Events, 1)
	assert.Equal(t, targets.CIRegressionRunID, *alertSummary.Events[0].RunID)

	session := sessions.Sign(userID, time.Now().UTC().Add(time.Hour))
	events := getAPIWithCookie[struct {
		Events []struct {
			Status       string `json:"status"`
			StatusReason string `json:"status_reason"`
		} `json:"events"`
	}](t, handler, "/api/alert-rules/"+url.PathEscape(rule.ID)+"/events", session)
	require.Len(t, events.Events, 1)
	assert.Equal(t, string(service.CIReportStatusFailure), events.Events[0].Status)
	assert.Equal(t, "lookback regression detected", events.Events[0].StatusReason)
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

func getAPI[T any](t *testing.T, handler http.Handler, target string) T {
	t.Helper()
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, target, nil))
	require.Equal(t, http.StatusOK, rec.Code, "GET %s; body %s", target, rec.Body.String())
	var out T
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &out), "decode GET %s", target)
	return out
}

func getAPIWithCookie[T any](t *testing.T, handler http.Handler, target, session string) T {
	t.Helper()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, target, nil)
	req.AddCookie(&http.Cookie{Name: auth.SessionCookieName, Value: session})
	handler.ServeHTTP(rec, req)
	require.Equal(t, http.StatusOK, rec.Code, "GET %s; body %s", target, rec.Body.String())
	var out T
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &out), "decode GET %s", target)
	return out
}

func assertRunPresent(t *testing.T, runs []service.RecentRunListItem, runID, latestBatchID string) {
	t.Helper()
	for _, run := range runs {
		if run.RunID != runID {
			continue
		}
		require.NotNil(t, run.LatestBatchID)
		assert.Equal(t, latestBatchID, *run.LatestBatchID)
		assert.Equal(t, int64(1), run.ResultCount)
		return
	}
	require.Failf(t, "run not found", "recent runs did not include %s", runID)
}

func dayForSmokeTest() time.Time {
	return time.Date(2024, 1, 8, 12, 0, 0, 0, time.UTC)
}
