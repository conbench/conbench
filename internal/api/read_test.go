package api_test

import (
	"context"
	"encoding/json"
	"net/http"
	"testing"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
)

// newReadAPI registers the write and read handlers on one test API over a real
// Postgres, so tests create rows through the ingestion endpoint and read them
// back through the read endpoints.
func newReadAPI(t *testing.T) (humatest.TestAPI, context.Context) {
	t.Helper()
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	ingester := service.NewIngester(store, commit.LocalProvider{})

	_, tapi := humatest.New(t)
	api.NewHandler(ingester, service.NewReader(store), auth.New(testToken, false, store, nil)).Register(tapi)
	api.NewReadHandler(service.NewReader(store)).Register(tapi)
	return tapi, ctx
}

// submit posts a valid result and returns its id and history fingerprint.
func submit(t *testing.T, tapi humatest.TestAPI) (string, string) {
	t.Helper()
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, validBody())
	require.Equal(t, http.StatusCreated, resp.Code, "submit: body %s", resp.Body.String())
	var out struct {
		ID                 string `json:"id"`
		HistoryFingerprint string `json:"history_fingerprint"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out), "decode submit response")
	return out.ID, out.HistoryFingerprint
}

func TestGetResult(t *testing.T) {
	tapi, _ := newReadAPI(t)
	id, _ := submit(t, tapi)

	resp := tapi.Get("/api/benchmark-results/" + id)
	require.Equal(t, http.StatusOK, resp.Code, "body = %s", resp.Body.String())
	var d service.ResultDetail
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &d))
	assert.Equal(t, id, d.ID)
	assert.Equal(t, "bench", d.Tags["name"])
	if d.Commit == nil || d.Commit.Sha != "abc123" {
		assert.Failf(t, "commit mismatch", "commit = %+v", d.Commit)
	}
	if d.SVS == nil || *d.SVS != 1 || d.SVSType != "min" {
		assert.Failf(t, "svs mismatch", "svs = %v (%s), want 1 (min)", d.SVS, d.SVSType)
	}
}

func TestGetResultNotFound(t *testing.T) {
	tapi, _ := newReadAPI(t)
	resp := tapi.Get("/api/benchmark-results/0000000000000000000000000000dead")
	require.Equal(t, http.StatusNotFound, resp.Code, "body = %s", resp.Body.String())
}

// getResultDetail fetches a result's detail via the API and returns the decoded
// body, asserting a 200.
func getResultDetail(t *testing.T, tapi humatest.TestAPI, id string) service.ResultDetail {
	t.Helper()
	resp := tapi.Get("/api/benchmark-results/" + id)
	require.Equal(t, http.StatusOK, resp.Code, "detail: %s", resp.Body.String())
	var d service.ResultDetail
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &d))
	return d
}

func TestResultDetailLessIsBetter(t *testing.T) {
	tapi, pool, ctx := seedAPI(t)
	id := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(0), unit: "s", data: []float64{10}})
	d := getResultDetail(t, tapi, id)
	require.NotNil(t, d.LessIsBetter)
	assert.True(t, *d.LessIsBetter, "seconds: less is better")

	// An errored result may carry an unvalidated raw unit; deriving must not 500.
	bogus := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(1), unit: "s", data: []float64{1}})
	_, err := pool.Exec(ctx,
		`UPDATE benchmark_result SET unit='zzz', error='{"x":1}'::jsonb, data='{}' WHERE id=$1`, bogus)
	require.NoError(t, err)
	d2 := getResultDetail(t, tapi, bogus)
	assert.Nil(t, d2.LessIsBetter, "unknown unit -> null, not a 500")
}

// TestResultDetailAnnotationFields asserts the detail endpoint exposes the three
// annotation columns and that a partial result's null data element survives to
// the wire. A variant-B partial submission (a null element in data, no error key)
// stores data verbatim with the synthetic partial error, so the nullable-element
// array shape must reach the response.
func TestResultDetailAnnotationFields(t *testing.T) {
	tapi, _ := newReadAPI(t)

	body := validBody()
	body["optional_benchmark_info"] = map[string]any{"trace_id": "abc"}
	body["validation"] = map[string]any{"type": "pandas.testing", "success": true}
	body["change_annotations"] = map[string]any{
		"begins_distribution_change": true,
		"dropme":                     nil, // dropped on create
	}
	body["stats"] = map[string]any{"data": []any{1.5, nil}, "unit": "s"}
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, resp.Code, "submit: %s", resp.Body.String())
	var out struct {
		ID string `json:"id"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))

	d := getResultDetail(t, tapi, out.ID)
	assert.Equal(t, map[string]any{"trace_id": "abc"}, d.OptionalBenchmarkInfo)
	assert.Equal(t, map[string]any{"type": "pandas.testing", "success": true}, d.Validation)
	assert.Equal(t, map[string]any{"begins_distribution_change": true}, d.ChangeAnnotations)
	// The null data element reaches the wire as a JSON null.
	require.Len(t, d.Data, 2)
	require.NotNil(t, d.Data[0])
	assert.InDelta(t, 1.5, *d.Data[0], 1e-12)
	assert.Nil(t, d.Data[1])
}

// TestResultDetailAnnotationFieldsAbsent asserts a result submitted without the
// annotation fields reports null optional_benchmark_info/validation but an empty
// object (not null) for change_annotations, matching the legacy serializer.
func TestResultDetailAnnotationFieldsAbsent(t *testing.T) {
	tapi, _ := newReadAPI(t)
	id, _ := submit(t, tapi)

	resp := tapi.Get("/api/benchmark-results/" + id)
	require.Equal(t, http.StatusOK, resp.Code, "detail: %s", resp.Body.String())
	var raw map[string]json.RawMessage
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &raw))
	assert.JSONEq(t, `null`, string(raw["optional_benchmark_info"]))
	assert.JSONEq(t, `null`, string(raw["validation"]))
	assert.JSONEq(t, `{}`, string(raw["change_annotations"]))
}

func TestGetHistoryForResult(t *testing.T) {
	tapi, _ := newReadAPI(t)
	id, fp := submit(t, tapi)

	resp := tapi.Get("/api/history/" + id)
	require.Equal(t, http.StatusOK, resp.Code, "body = %s", resp.Body.String())
	var series service.HistorySeries
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &series))
	assert.Equal(t, fp, series.HistoryFingerprint)
	if len(series.Samples) != 1 || series.Samples[0].BenchmarkResultID != id {
		assert.Failf(t, "unexpected samples", "samples = %+v, want one for %s", series.Samples, id)
	}
}

func TestGetHistoryByFingerprint(t *testing.T) {
	tapi, _ := newReadAPI(t)
	id, fp := submit(t, tapi)

	resp := tapi.Get("/api/history?fingerprint=" + fp)
	require.Equal(t, http.StatusOK, resp.Code, "body = %s", resp.Body.String())
	var series service.HistorySeries
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &series))
	if len(series.Samples) != 1 || series.Samples[0].BenchmarkResultID != id {
		assert.Failf(t, "unexpected samples", "samples = %+v, want one for %s", series.Samples, id)
	}
}

func TestGetHistoryRequiresFingerprint(t *testing.T) {
	tapi, _ := newReadAPI(t)
	resp := tapi.Get("/api/history")
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "missing fingerprint; body = %s", resp.Body.String())
}
