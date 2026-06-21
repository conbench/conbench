package api_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
)

func seedCIReportAPI(t *testing.T, publicBaseURL string) (humatest.TestAPI, *pgxpool.Pool, context.Context) {
	t.Helper()
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	ingester := service.NewIngester(store, commit.LocalProvider{})
	_, tapi := humatest.New(t)
	api.NewHandler(ingester, service.NewReader(store), auth.New(testToken, false, store, nil)).Register(tapi)
	api.NewCIReportHandler(service.NewCIReporter(store, publicBaseURL)).Register(tapi)
	return tapi, pool, ctx
}

func TestCIReportEndpointReturnsReport(t *testing.T) {
	tapi, pool, ctx := seedCIReportAPI(t, "https://conbench.example/")
	seedResult(t, tapi, seedOpts{runID: "main-run", sha: "c1", ts: day(1), data: []float64{10}})
	seedResult(t, tapi, seedOpts{runID: "main-run", sha: "c2", ts: day(2), data: []float64{20}})
	seedResult(t, tapi, seedOpts{runID: "main-run", sha: "c3", ts: day(3), data: []float64{30}})
	seedResult(t, tapi, seedOpts{runID: "ci-run", sha: "c4", ts: day(4), data: []float64{100}})

	// The LocalProvider seeds every commit as default-branch. Patch the contender
	// metadata into the PR shape the CI report baseline resolver expects.
	_, err := pool.Exec(ctx, `UPDATE commit SET parent = $1, fork_point_sha = $2 WHERE repository = $3 AND sha = $4`,
		"c3", "c3", defaultRepo, "c4")
	require.NoError(t, err)

	resp := tapi.Get("/api/ci/report?repository=" + url.QueryEscape(defaultRepo) + "&commit_sha=c4")
	report := decodeCIReport(t, resp)
	assert.Equal(t, service.CIReportStatusFailure, report.Status)
	assert.Equal(t, []string{"ci-run"}, report.SelectedRunIDs)
	assertCIReportURL(t, report)
	require.Len(t, report.Runs, 1)
	assert.Equal(t, "main-run", *report.Runs[0].BaselineRunID)
	require.Len(t, report.Runs[0].Comparisons, 1)
	assert.Equal(t, service.CIReportRowStatusRegressed, report.Runs[0].Comparisons[0].Status)
	assert.Equal(t, 1, report.Summary.Compared)
	assert.Equal(t, 1, report.Summary.Analyzed)
}

func TestCIReportEndpointAcceptsExplicitBaselineRunIDs(t *testing.T) {
	tapi, _, _ := seedCIReportAPI(t, "https://conbench.example/")
	seedResult(t, tapi, seedOpts{runID: "history-run", sha: "c1", ts: day(1), data: []float64{10}})
	seedResult(t, tapi, seedOpts{runID: "history-run", sha: "c2", ts: day(2), data: []float64{20}})
	seedResult(t, tapi, seedOpts{runID: "explicit-baseline", sha: "c3", ts: day(3), data: []float64{30}})
	seedResult(t, tapi, seedOpts{runID: "ci-run", sha: "c4", ts: day(4), data: []float64{100}})

	resp := tapi.Get("/api/ci/report?run_ids=ci-run&baseline_run_ids=explicit-baseline")
	report := decodeCIReport(t, resp)

	assert.Equal(t, service.CIReportBaselineExplicitRun, report.Baseline)
	assertCIReportURL(t, report)
	require.Len(t, report.Runs, 1)
	assert.Equal(t, "explicit-baseline", *report.Runs[0].BaselineRunID)
	require.Len(t, report.Runs[0].Comparisons, 1)
	assert.Equal(t, service.CIReportRowStatusRegressed, report.Runs[0].Comparisons[0].Status)
}

func TestCIReportEndpointValidation(t *testing.T) {
	tapi, _, _ := seedCIReportAPI(t, "")

	resp := tapi.Get("/api/ci/report?repository=https://github.com/org/repo")
	assert.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())

	resp = tapi.Get("/api/ci/report?run_ids=missing")
	assert.Equal(t, http.StatusNotFound, resp.Code, "body %s", resp.Body.String())

	resp = tapi.Get("/api/ci/report?run_ids=a&threshold=0")
	assert.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())

	resp = tapi.Get("/api/ci/report?run_ids=a&baseline=parent&baseline_run_ids=b")
	assert.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())

	resp = tapi.Get("/api/ci/report?run_ids=a,b&baseline_run_ids=base")
	assert.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())
}

func decodeCIReport(t *testing.T, resp *httptest.ResponseRecorder) service.CIReport {
	t.Helper()
	require.Equal(t, http.StatusOK, resp.Code, "body %s", resp.Body.String())
	var report service.CIReport
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &report))
	return report
}

func assertCIReportURL(t *testing.T, report service.CIReport) {
	t.Helper()
	assert.True(t, strings.HasPrefix(report.ReportURL, "https://conbench.example/ci/report?"))
}
