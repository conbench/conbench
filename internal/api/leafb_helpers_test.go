package api_test

import (
	"context"
	"encoding/json"
	"maps"
	"net/http"
	"testing"
	"time"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
)

// seedAPI builds the read+write API over a real Postgres and returns the pool so
// tests can seed columns the ingester does not write (e.g. change_annotations).
func seedAPI(t *testing.T) (humatest.TestAPI, *pgxpool.Pool, context.Context) {
	t.Helper()
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	ingester := service.NewIngester(store, commit.LocalProvider{})
	_, tapi := humatest.New(t)
	api.NewHandler(ingester, service.NewReader(store), auth.New(testToken, false, store, nil)).Register(tapi)
	api.NewReadHandler(service.NewReader(store)).Register(tapi)
	return tapi, pool, ctx
}

// seedOpts overrides the parts of validBody that a series fixture varies. The
// tags/context/info/machine_info are held constant so every seeded result shares
// one history_fingerprint; unit is excluded from the fingerprint, so a mixed-unit
// series still shares it. To seed DISTINCT series, vary name/machine/repo: the case
// name, hardware name, and repository all feed the history_fingerprint.
type seedOpts struct {
	sha       string         // github commit sha (distinct sha => distinct default-branch commit)
	ts        time.Time      // result timestamp == commit timestamp (LocalProvider)
	unit      string         // measurement unit; defaults to "s"
	data      []float64      // per-iteration measurements; SVS = best-of-mode over these
	runID     string         // defaults to "run-1"
	runReason string         // optional; omitted when empty
	batchID   string         // optional; omitted when empty
	name      string         // case name (the "name" tag); defaults to "bench"
	tags      map[string]any // extra case tags merged with name; defaults to {"source":"test"}
	machine   string         // hardware name; defaults to "m1"
	repo      string         // repository url; defaults to the org/repo remote
}

// defaultRepo is the repository every seeded result uses unless seedOpts.repo
// overrides it. A distinct repo yields a distinct history_fingerprint.
const defaultRepo = "https://github.com/org/repo"

// seedResult posts one result and returns its id. By default it keeps the
// fingerprint stable across calls (constant case/hardware/repo); set
// name/machine/repo to seed a distinct series.
func seedResult(t *testing.T, tapi humatest.TestAPI, o seedOpts) string {
	t.Helper()
	unit := o.unit
	if unit == "" {
		unit = "s"
	}
	runID := o.runID
	if runID == "" {
		runID = "run-1"
	}
	repo := o.repo
	if repo == "" {
		repo = defaultRepo
	}
	body := validBody()
	body["tags"] = caseTags(o)
	if o.machine != "" {
		machine, ok := body["machine_info"].(map[string]any)
		require.True(t, ok, "machine_info must be a map")
		machine["name"] = o.machine
	}
	body["github"] = map[string]any{"commit": o.sha, "repository": repo}
	body["timestamp"] = o.ts.UTC().Format(time.RFC3339)
	body["stats"] = map[string]any{"data": o.data, "unit": unit}
	body["run_id"] = runID
	if o.runReason != "" {
		body["run_reason"] = o.runReason
	}
	if o.batchID != "" {
		body["batch_id"] = o.batchID
	}
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, resp.Code, "seed: body %s", resp.Body.String())
	var out struct {
		ID string `json:"id"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	require.NotEmpty(t, out.ID)
	return out.ID
}

// day returns a fixed UTC base date offset by d days, for deterministic ordering.
func day(d int) time.Time {
	return time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC).AddDate(0, 0, d)
}

// fpForResult fetches a seeded result's history_fingerprint via the detail endpoint.
func fpForResult(t *testing.T, tapi humatest.TestAPI, id string) string {
	t.Helper()
	resp := tapi.Get("/api/benchmark-results/" + id)
	require.Equal(t, http.StatusOK, resp.Code, "detail: %s", resp.Body.String())
	var d struct {
		HistoryFingerprint string `json:"history_fingerprint"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &d))
	return d.HistoryFingerprint
}

// caseTags builds the result's tags map (the case name plus permutation tags).
// The "name" tag becomes the case name; defaults keep validBody's fingerprint.
func caseTags(o seedOpts) map[string]any {
	name := o.name
	if name == "" {
		name = "bench"
	}
	tags := map[string]any{"name": name}
	if o.tags == nil {
		tags["source"] = "test"
		return tags
	}
	maps.Copy(tags, o.tags)
	tags["name"] = name
	return tags
}
