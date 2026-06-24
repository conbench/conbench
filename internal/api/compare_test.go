package api_test

import (
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/service"
)

func TestCompareHappyPath(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	// Contender fingerprint series: [10,20,30] at days 1..3 (baseline window),
	// contender 100 at day 4. Baseline = the day-3 result (svs 30).
	seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{20}})
	baseline := seedResult(t, tapi, seedOpts{sha: "c3", ts: day(3), data: []float64{30}})
	contender := seedResult(t, tapi, seedOpts{sha: "c4", ts: day(4), data: []float64{100}})

	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusOK, resp.Code, "body %s", resp.Body.String())
	var out service.CompareResult
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))

	assert.Equal(t, "s", out.Unit)
	assert.True(t, out.LessIsBetter)
	assert.InDelta(t, 30.0, out.Baseline.SVS, 1e-9)
	assert.InDelta(t, 100.0, out.Contender.SVS, 1e-9)
	// Pairwise: (100-30)/30 = +2.333, flipped (less is better) => -233.3% => regression.
	require.NotNil(t, out.Analysis.Pairwise)
	assert.True(t, out.Analysis.Pairwise.RegressionIndicated)
	assert.False(t, out.Analysis.Pairwise.ImprovementIndicated)
	assert.InDelta(t, -233.3, out.Analysis.Pairwise.PercentChange, 0.1)
	// Lookback: window [10,20,30] => mean 20, sd sqrt(175/3)=7.6376; z=(100-20)/sd
	// =10.47, flipped => -10.47; -z=10.47 > 5 => regression.
	require.NotNil(t, out.Analysis.LookbackZScore)
	assert.InDelta(t, -10.47, out.Analysis.LookbackZScore.ZScore, 0.05)
	assert.True(t, out.Analysis.LookbackZScore.RegressionIndicated)
	assert.False(t, out.Analysis.LookbackZScore.ImprovementIndicated)
}

func TestCompareRejectsInvalidThresholds(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	baseline := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	contender := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{20}})

	base := "/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender
	tests := []string{
		base + "&threshold=0",
		base + "&threshold=-1",
		base + "&threshold=NaN",
		base + "&threshold_z=0",
		base + "&threshold_z=-1",
		base + "&threshold_z=NaN",
	}
	for _, query := range tests {
		resp := tapi.Get(query)
		assert.Equal(t, http.StatusUnprocessableEntity, resp.Code, "query %s body %s", query, resp.Body.String())
		assert.Contains(t, resp.Body.String(), "finite number greater than zero")
	}
}

func TestCompareFailedResultIs422(t *testing.T) {
	tapi, pool, ctx := seedAPI(t)
	baseline := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	contender := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{20}})
	// Mark the contender failed directly (the ingester accepts only valid bodies).
	_, err := pool.Exec(ctx, `UPDATE benchmark_result SET error = $1 WHERE id = $2`,
		[]byte(`{"stack":"boom"}`), contender)
	require.NoError(t, err)

	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())
}

func TestCompareUnitMismatchIs422(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	baseline := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), unit: "s", data: []float64{10}})
	contender := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), unit: "B/s", data: []float64{20}})

	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())
}

func TestCompareFingerprintMismatchIs422(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	baseline := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	// Different case name => different history fingerprint.
	body := validBody()
	body["tags"] = map[string]any{"name": "other-bench", "source": "test"}
	body["github"] = map[string]any{"commit": "c2", "repository": "https://github.com/org/repo"}
	body["timestamp"] = day(2).Format(time.RFC3339)
	body["stats"] = map[string]any{"data": []float64{20}, "unit": "s"}
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, resp.Code, "%s", resp.Body.String())
	var created struct {
		ID string `json:"id"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &created))

	cmp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + created.ID)
	require.Equal(t, http.StatusUnprocessableEntity, cmp.Code, "body %s", cmp.Body.String())
}

func TestCompareBaselineZeroSVSNullsPairwise(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	// Baseline svs 0 (data [0]); contender svs 5. Pairwise divide-by-zero => null.
	baseline := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{0}})
	contender := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{5}})

	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusOK, resp.Code, "body %s", resp.Body.String())
	var out service.CompareResult
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	assert.Nil(t, out.Analysis.Pairwise, "pairwise must be null when baseline svs is 0")
}

func TestCompareBaselineWithoutCommitNullsLookback(t *testing.T) {
	tapi, pool, ctx := seedAPI(t)
	baseline := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	contender := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{20}})
	// Strip the baseline's commit so there is no ancestry cutoff.
	_, err := pool.Exec(ctx, `UPDATE benchmark_result SET commit_id = NULL WHERE id = $1`, baseline)
	require.NoError(t, err)

	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusOK, resp.Code, "body %s", resp.Body.String())
	var out service.CompareResult
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	require.NotNil(t, out.Analysis.Pairwise, "pairwise still returned")
	assert.Nil(t, out.Analysis.LookbackZScore, "no baseline commit => lookback null")
}

func TestCompareMixedUnitWindowNullsLookback(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	// Window members share the fingerprint but one is B/s; baseline+contender are s.
	seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), unit: "s", data: []float64{10}})
	seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), unit: "B/s", data: []float64{20}})
	baseline := seedResult(t, tapi, seedOpts{sha: "c3", ts: day(3), unit: "s", data: []float64{30}})
	contender := seedResult(t, tapi, seedOpts{sha: "c4", ts: day(4), unit: "s", data: []float64{40}})

	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusOK, resp.Code, "body %s", resp.Body.String())
	var out service.CompareResult
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	require.NotNil(t, out.Analysis.Pairwise, "pairwise still returned")
	assert.Nil(t, out.Analysis.LookbackZScore, "mixed-unit window => lookback null")
}

func TestCompareLookbackPropagatesDataError(t *testing.T) {
	tapi, pool, ctx := seedAPI(t)
	// Window members (same fingerprint+unit) at days 1-3; baseline=day3, contender=day4.
	corrupt := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{20}})
	baseline := seedResult(t, tapi, seedOpts{sha: "c3", ts: day(3), data: []float64{30}})
	contender := seedResult(t, tapi, seedOpts{sha: "c4", ts: day(4), data: []float64{100}})
	// Empty the day-1 member's data while leaving error NULL: it stays a membership
	// member (error IS NULL) but historySVS now errors on it inside the lookback window.
	_, err := pool.Exec(ctx, `UPDATE benchmark_result SET data = '{}' WHERE id = $1`, corrupt)
	require.NoError(t, err)

	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + baseline + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusInternalServerError, resp.Code,
		"a data-integrity fault in the lookback window must surface as 500, not a masked null lookback; body %s", resp.Body.String())
}

func TestCompareNotFoundIs404(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	contender := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	missing := "0000000000000000000000000000dead"
	resp := tapi.Get("/api/compare/benchmark-results?baseline_result_id=" + missing + "&contender_result_id=" + contender)
	require.Equal(t, http.StatusNotFound, resp.Code, "body %s", resp.Body.String())
}
