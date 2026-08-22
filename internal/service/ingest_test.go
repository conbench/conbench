package service_test

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/commit/githubtest"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/hardware"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/stats"
	"github.com/conbench/conbench/internal/storage"
)

func newIngester(t *testing.T) (*service.Ingester, *db.Store, *pgxpool.Pool, context.Context) {
	t.Helper()
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	return service.NewIngester(store, commit.LocalProvider{}), store, pool, ctx
}

func TestSubmitIdempotentReplayAndConflict(t *testing.T) {
	ing, _, _, ctx := newIngester(t)
	req := machineReq(samples(1, 2, 3), "s")
	req.SubmissionKey = "publisher-0000000000000001"

	first, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	second, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	assert.Equal(t, first, second)
	assert.Equal(t, req.RunID, second.RunID)

	changed := req
	changed.Stats = &service.StatsInput{Data: samples(4, 5, 6), Unit: "s"}
	_, err = ing.Submit(ctx, changed)
	require.Error(t, err)
	assert.ErrorIs(t, err, service.ErrSubmissionConflict)
}

func TestSubmitWithoutIdempotencyKeyCreatesIndependentResults(t *testing.T) {
	ing, _, _, ctx := newIngester(t)
	req := machineReq(samples(1, 2, 3), "s")
	first, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	second, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	assert.NotEqual(t, first.ID, second.ID)
}

func TestSubmitAcceptsMaximumLengthUnicodeIdempotencyKey(t *testing.T) {
	ing, _, _, ctx := newIngester(t)
	req := machineReq(samples(1, 2, 3), "s")
	req.SubmissionKey = strings.Repeat("é", 255)

	_, err := ing.Submit(ctx, req)
	require.NoError(t, err)
}

// samples wraps float values as the nullable per-iteration slice the payload carries.
func samples(vs ...float64) []*float64 {
	out := make([]*float64, len(vs))
	for i := range vs {
		v := vs[i]
		out[i] = &v
	}
	return out
}

const testRepo = "https://github.com/org/repo"

// machineReq builds a valid machine-based success request with the given samples.
func machineReq(data []*float64, unit string) service.SubmitRequest {
	return service.SubmitRequest{
		Tags:    map[string]any{"name": "bench", "source": "test"},
		Context: map[string]any{"compiler": "gcc"},
		Info:    map[string]any{"build": "release"},
		MachineInfo: &service.MachineInfo{
			Name:             "m1",
			ArchitectureName: new("x86_64"),
			CpuCoreCount:     new(int32(8)),
			CpuThreadCount:   new(int32(16)),
			MemoryBytes:      new(int64(16) << 30),
			GpuCount:         new(int32(0)),
		},
		GitHub:    service.GitHubInfo{Commit: "abc123", Repository: testRepo},
		RunID:     "run-1",
		BatchID:   "batch-1",
		Timestamp: time.Date(2024, 1, 2, 3, 4, 5, 0, time.UTC),
		Stats:     &service.StatsInput{Data: data, Unit: unit},
	}
}

// machineHash recomputes the hash for machineReq's hardware (gpu, core, thread, mem).
func machineHash() string {
	return hardware.MachineHash("m1", new(int64(0)), new(int64(8)), new(int64(16)), new(int64(16)<<30))
}

func TestSubmitHappyPathInserts(t *testing.T) {
	ing, store, pool, ctx := newIngester(t)

	res, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
	require.NoError(t, err)
	require.NotEmpty(t, res.ID)
	require.NotEmpty(t, res.HistoryFingerprint)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	if assert.NotNil(t, row.Unit) {
		assert.Equal(t, "s", *row.Unit)
	}
	assert.Len(t, row.Data, 3)
	assert.Nil(t, row.Error)
	assert.NotNil(t, row.CommitID)
	assert.Equal(t, "run-1", row.RunID)
	assert.Equal(t, testRepo, row.CommitRepoUrl)

	// FK rows exist.
	for _, q := range []struct {
		table, id string
	}{
		{`"case"`, row.CaseID}, {"context", row.ContextID},
		{"info", row.InfoID}, {"hardware", row.HardwareID},
	} {
		var n int
		err := pool.QueryRow(ctx, "SELECT count(*) FROM "+q.table+" WHERE id=$1", q.id).Scan(&n)
		require.NoError(t, err, "count %s", q.table)
		assert.Equalf(t, 1, n, "%s rows for id %s", q.table, q.id)
	}

	// The successful, commit-joined, default-branch result is in its history.
	hist, err := store.SelectHistoryForFingerprint(ctx, res.HistoryFingerprint)
	require.NoError(t, err)
	assert.Len(t, hist, 1)
}

func TestSubmitComputesAggregates(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	t.Run("three samples set every aggregate", func(t *testing.T) {
		res, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
		require.NoError(t, err)
		row, err := store.GetBenchmarkResultByID(ctx, res.ID)
		require.NoError(t, err)
		want := map[string]*float64{
			"mean": new(2.0), "min": new(1.0), "max": new(3.0), "median": new(2.0),
			"q1": new(1.5), "q3": new(2.5), "stdev": new(1.0), "iqr": new(1.0),
		}
		got := map[string]*float64{
			"mean": row.Mean, "min": row.Min, "max": row.Max, "median": row.Median,
			"q1": row.Q1, "q3": row.Q3, "stdev": row.Stdev, "iqr": row.Iqr,
		}
		for k, w := range want {
			g := got[k]
			if assert.NotNilf(t, g, "%s", k) {
				assert.InDeltaf(t, *w, *g, 1e-9, "%s", k)
			}
		}
	})

	t.Run("one sample sets only the mean", func(t *testing.T) {
		res, err := ing.Submit(ctx, machineReq(samples(5), "s"))
		require.NoError(t, err)
		row, err := store.GetBenchmarkResultByID(ctx, res.ID)
		require.NoError(t, err)
		if assert.NotNil(t, row.Mean) {
			assert.InDelta(t, float64(5), *row.Mean, 1e-9)
		}
		assert.Nil(t, row.Min)
		assert.Nil(t, row.Max)
		assert.Nil(t, row.Stdev)
		assert.Nil(t, row.Q1)
	})
}

func TestSubmitEmptyCommitStoresNullCommitID(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.GitHub.Commit = ""
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.Nil(t, row.CommitID)
	// commit_repo_url and history_fingerprint are still recorded.
	assert.Equal(t, testRepo, row.CommitRepoUrl)
	assert.NotEmpty(t, row.HistoryFingerprint)
	// Without a commit join, the result is excluded from history.
	hist, err := store.SelectHistoryForFingerprint(ctx, res.HistoryFingerprint)
	require.NoError(t, err)
	assert.Empty(t, hist)
}

func TestSubmitNormalizesTrailingSlashRepo(t *testing.T) {
	ing, store, pool, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.GitHub.Repository = testRepo + "/"
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.Equal(t, testRepo, row.CommitRepoUrl)
	// The commit row's repository is normalized too, so the fingerprint is stable.
	var repo string
	err = pool.QueryRow(ctx, "SELECT repository FROM commit WHERE id=$1", *row.CommitID).Scan(&repo)
	require.NoError(t, err)
	assert.Equal(t, testRepo, repo)
}

func TestSubmitSplitsTags(t *testing.T) {
	ing, store, pool, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Tags = map[string]any{
		"name": "mybench", "cols": 2, "flag": true,
		"empty": "", "nullv": nil, "keep": "yes",
	}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)

	var name string
	var tagsJSON []byte
	err = pool.QueryRow(ctx, `SELECT name, tags FROM "case" WHERE id=$1`, row.CaseID).Scan(&name, &tagsJSON)
	require.NoError(t, err)
	assert.Equal(t, "mybench", name)
	var tags map[string]any
	err = json.Unmarshal(tagsJSON, &tags)
	require.NoError(t, err)
	// name removed; empty/null dropped; primitives stringified Python-style.
	want := map[string]any{"cols": "2", "flag": "True", "keep": "yes"}
	require.Len(t, tags, len(want))
	for k, w := range want {
		assert.Equalf(t, w, tags[k], "tag %s", k)
	}
}

func TestSubmitPartialResultStoresError(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq([]*float64{new(1.0), nil, new(3.0)}, "s")
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	require.NotNil(t, row.Error)
	var e map[string]any
	err = json.Unmarshal(row.Error, &e)
	require.NoError(t, err)
	assert.Equal(t, "Partial result: not all iterations completed", e["status"])
	assert.Nil(t, row.Mean) // no user-given aggregate to preserve
	// Raw data (null element included) is stored verbatim on the error path.
	assert.Equal(t, []*float64{new(1.0), nil, new(3.0)}, row.Data)
	hist, err := store.SelectHistoryForFingerprint(ctx, res.HistoryFingerprint)
	require.NoError(t, err)
	assert.Empty(t, hist)
}

func TestSubmitExplicitErrorStored(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Error = service.JSONObject{Present: true, Value: map[string]any{"command": "boom"}}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	require.NotNil(t, row.Error)
	var e map[string]any
	err = json.Unmarshal(row.Error, &e)
	require.NoError(t, err)
	assert.Equal(t, "boom", e["command"])
	assert.Nil(t, row.Mean) // no user-given aggregate to preserve
}

func TestSubmitFingerprintConsistency(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	r1, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
	require.NoError(t, err)
	r2, err := ing.Submit(ctx, machineReq(samples(4, 5, 6), "s"))
	require.NoError(t, err)
	assert.Equal(t, r1.HistoryFingerprint, r2.HistoryFingerprint)

	row, err := store.GetBenchmarkResultByID(ctx, r1.ID)
	require.NoError(t, err)
	want := stats.HistoryFingerprint(row.CaseID, row.ContextID, machineHash(), testRepo)
	assert.Equal(t, want, r1.HistoryFingerprint)
}

// TestSubmitGitAtRepoURLJoinsHTTPSHistory pins the git@ rewrite end to end: the
// same repo submitted via the git@ spelling lands in the same history series
// (same fingerprint, same commit_repo_url) as the https spelling.
func TestSubmitGitAtRepoURLJoinsHTTPSHistory(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req1 := machineReq(samples(1, 2, 3), "s")
	res1, err := ing.Submit(ctx, req1)
	require.NoError(t, err)

	req2 := machineReq(samples(2, 3, 4), "s")
	req2.GitHub.Repository = "git@github.com:org/repo"
	res2, err := ing.Submit(ctx, req2)
	require.NoError(t, err)

	assert.Equal(t, res1.HistoryFingerprint, res2.HistoryFingerprint)
	row, err := store.GetBenchmarkResultByID(ctx, res2.ID)
	require.NoError(t, err)
	assert.Equal(t, "https://github.com/org/repo", row.CommitRepoUrl)
}

// countingProvider wraps LocalProvider and counts Resolve calls, standing in
// for the GitHub provider's network cost.
type countingProvider struct {
	calls int
}

func (p *countingProvider) Resolve(ctx context.Context, req commit.Request) (*commit.Info, error) {
	p.calls++
	return commit.LocalProvider{}.Resolve(ctx, req)
}

// TestSubmitExistingCommitShortCircuitsProvider pins the Leaf 2 contract: a
// (sha, repository) pair already in the commit table is reused without calling
// the provider at all, so resubmission never re-triggers GitHub enrichment and
// previously-unknown commits stay unknown until the Phase 6 repair job.
func TestSubmitExistingCommitShortCircuitsProvider(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	prov := &countingProvider{}
	ing := service.NewIngester(store, prov)

	req := machineReq(samples(1, 2, 3), "s")
	_, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	require.Equal(t, 1, prov.calls)

	req2 := machineReq(samples(4, 5, 6), "s")
	res2, err := ing.Submit(ctx, req2)
	require.NoError(t, err)
	assert.Equal(t, 1, prov.calls, "existing commit row must short-circuit the provider")

	row, err := store.GetBenchmarkResultByID(ctx, res2.ID)
	require.NoError(t, err)
	assert.NotNil(t, row.CommitID, "second result still references the commit")
}

// TestSubmitShortCircuitUsesNormalizedRepo pins that the lookup key is the
// normalized URL: the git@ spelling of an already-known repo also short-circuits.
func TestSubmitShortCircuitUsesNormalizedRepo(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	prov := &countingProvider{}
	ing := service.NewIngester(store, prov)

	_, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
	require.NoError(t, err)

	req := machineReq(samples(2, 3, 4), "s")
	req.GitHub.Repository = "git@github.com:org/repo"
	_, err = ing.Submit(ctx, req)
	require.NoError(t, err)
	assert.Equal(t, 1, prov.calls)
}

func TestSubmitErroredPreservesRawStats(t *testing.T) {
	// variant A: explicit error object; complete stats given.
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Error = service.JSONObject{Present: true, Value: map[string]any{"stack": "trace"}}
	req.Stats = &service.StatsInput{
		Data:  []*float64{new(1.5), nil},
		Times: []*float64{nil, new(0.5)},
		Unit:  "definitely-not-a-unit", TimeUnit: "weird-time-unit",
		Iterations: new(int32(7)),
		Mean:       new(99.9), Min: new(1.0), Max: new(2.0), Median: new(1.5),
		Q1: new(1.2), Q3: new(1.8), Stdev: new(0.4), Iqr: new(0.6),
	}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{"stack":"trace"}`, string(row.Error))
	assert.Equal(t, []*float64{new(1.5), nil}, row.Data)
	assert.Equal(t, []*float64{nil, new(0.5)}, row.Times)
	assert.Equal(t, "definitely-not-a-unit", *row.Unit) // raw, unvalidated
	assert.Equal(t, "weird-time-unit", *row.TimeUnit)
	assert.Equal(t, int32(7), *row.Iterations)
	assert.InDelta(t, 99.9, *row.Mean, 1e-12) // user aggregates stored verbatim
	assert.InDelta(t, 0.6, *row.Iqr, 1e-12)
}

func TestSubmitPartialDataPreservesRawStats(t *testing.T) {
	// variant B: no error key, null element in data.
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Stats = &service.StatsInput{
		Data: []*float64{new(1.5), nil, new(2.0)},
		Unit: "s",
		Mean: new(42.0),
	}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{"status":"Partial result: not all iterations completed"}`, string(row.Error))
	assert.Equal(t, []*float64{new(1.5), nil, new(2.0)}, row.Data)
	assert.InDelta(t, 42.0, *row.Mean, 1e-12) // user aggregate preserved on the error path
}

func TestSubmitEmptyDataIsPartialAndStoredVerbatim(t *testing.T) {
	// variant B via the other looksLikeError route: an empty data array (no
	// null element). Legacy stores the empty array verbatim with the partial
	// error; this also pins the empty-numeric[] round-trip shape.
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Stats = &service.StatsInput{
		Data: []*float64{},
		Unit: "s",
	}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{"status":"Partial result: not all iterations completed"}`, string(row.Error))
	assert.Equal(t, []*float64{}, row.Data)
}

func TestSubmitEmptyErrorObjectIsErrored(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Error = service.JSONObject{Present: true, Value: map[string]any{}}
	req.Stats = nil
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{}`, string(row.Error))
	assert.Nil(t, row.Data) // error-only submission: stats columns stay NULL
	assert.Nil(t, row.Unit)
}

func TestSubmitNullErrorRejected(t *testing.T) {
	ing, _, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Error = service.JSONObject{Present: true, Null: true}
	_, err := ing.Submit(ctx, req)
	var ve *service.ValidationError
	require.ErrorAs(t, err, &ve)
}

func TestSubmitSuccessStoresTimesVerbatimAndIgnoresUserAggregates(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.Stats = &service.StatsInput{
		Data:  []*float64{new(1.0), new(2.0), new(3.0)},
		Times: []*float64{new(0.1), nil, new(0.3)}, // legacy stores times as-given even on success
		Unit:  "s",
		Mean:  new(1234.5), // must lose to the computed mean
	}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.Nil(t, row.Error)
	assert.Equal(t, []*float64{new(1.0), new(2.0), new(3.0)}, row.Data)
	assert.Equal(t, []*float64{new(0.1), nil, new(0.3)}, row.Times)
	assert.InDelta(t, 2.0, *row.Mean, 1e-12) // computed wins
	assert.NotNil(t, row.Stdev)              // >= 3 samples: full aggregates
}

func TestSubmitEmptyRunNameStillDiverts(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.RunName = new("")
	req.RunTags = nil
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{"name":""}`, string(row.RunTags)) // presence-keyed, legacy line 274
}

func TestSubmitStoresAnnotationFields(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.OptionalBenchmarkInfo = map[string]any{"trace_id": "abc"}
	req.Validation = map[string]any{"type": "pandas.testing", "success": true}
	req.ChangeAnnotations = map[string]any{
		"begins_distribution_change": true,
		"dropme":                     nil, // null-valued keys are dropped on create
	}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{"trace_id":"abc"}`, string(row.OptionalBenchmarkInfo))
	assert.JSONEq(t, `{"type":"pandas.testing","success":true}`, string(row.Validation))
	assert.JSONEq(t, `{"begins_distribution_change":true}`, string(row.ChangeAnnotations))
}

func TestSubmitAnnotationFieldsAbsent(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	res, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.Nil(t, row.OptionalBenchmarkInfo)              // NULL column
	assert.Nil(t, row.Validation)                         // NULL column
	assert.JSONEq(t, `{}`, string(row.ChangeAnnotations)) // always an object, legacy line 283
}

func TestSubmitValidationErrors(t *testing.T) {
	// These all fail before any DB access, so a nil-pool store is never queried.
	ing := service.NewIngester(db.NewStore(nil), commit.LocalProvider{})
	ctx := context.Background()

	cases := []struct {
		name   string
		mutate func(*service.SubmitRequest)
	}{
		{"no hardware", func(r *service.SubmitRequest) { r.MachineInfo = nil }},
		{"both hardware", func(r *service.SubmitRequest) {
			r.ClusterInfo = &service.ClusterInfo{Name: "c", Info: map[string]any{"x": 1}}
		}},
		{"no stats or error", func(r *service.SubmitRequest) { r.Stats = nil }},
		{"missing name tag", func(r *service.SubmitRequest) { r.Tags = map[string]any{"x": "1"} }},
		{"unknown unit", func(r *service.SubmitRequest) {
			r.Stats = &service.StatsInput{Data: samples(1, 2, 3), Unit: "furlongs"}
		}},
		{"object tag value", func(r *service.SubmitRequest) {
			r.Tags = map[string]any{"name": "b", "nested": map[string]any{"a": 1}}
		}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			req := machineReq(samples(1, 2, 3), "s")
			c.mutate(&req)
			_, err := ing.Submit(ctx, req)
			var ve *service.ValidationError
			require.ErrorAs(t, err, &ve)
		})
	}
}

// TestSubmitWithGitHubProviderEndToEnd drives the full Leaf 2 path: enrichment
// on first submit, short-circuit on resubmit, degradation to an unknown row
// for an unknown sha (and a second short-circuited resubmit of that unknown
// sha that must not re-enrich or re-count), and the enqueued backfill catching
// up the gap commit.
func TestSubmitWithGitHubProviderEndToEnd(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	const sha = "02addad336ba19a654f9c857ede546331be7b631"
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo/commits/"+sha, githubtest.Fixture(t, "github_child.json"))
	srv.HandleJSON("/repos/org/repo", []byte(`{"fork":false,"owner":{"login":"org"},"default_branch":"main"}`))
	srv.HandleJSON("/repos/org/repo/compare/org:main..."+sha,
		[]byte(`{"merge_base_commit":{"sha":"`+sha+`"}}`))
	srv.HandleStatus("/repos/org/repo/commits/deadbeef", http.StatusNotFound)
	srv.Mux.HandleFunc("/repos/org/repo/commits", func(w http.ResponseWriter, _ *http.Request) {
		body := `[
		 {"sha":"` + sha + `","commit":{"author":{"name":"Diana Clarke","date":"2021-02-25T01:02:51Z"},"message":"m"},"author":null,"parents":[]},
		 {"sha":"gapcommit","commit":{"author":{"name":"dev","date":"2021-02-24T00:00:00Z"},"message":"gap"},"author":null,"parents":[]},
		 {"sha":"oldtracked","commit":{"author":{"name":"dev","date":"2021-02-20T00:00:00Z"},"message":"old"},"author":null,"parents":[]}
		]`
		_, _ = w.Write([]byte(body))
	})

	client := commit.NewGitHubClient("", srv.URL)
	backfiller := commit.NewBackfiller(client, store)
	provider := commit.NewGitHubProvider(client, 5*time.Second, backfiller)
	ing := service.NewIngester(store, provider)

	// Seed the "last tracked" default-branch commit so the backfill window is
	// bounded.
	branch := "org:main"
	seedTS := time.Date(2021, 2, 20, 0, 0, 0, 0, time.UTC)
	_, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "oldtracked", Repository: testRepo, Branch: &branch, Timestamp: &seedTS,
	})
	require.NoError(t, err)

	// 1. Enriched submit.
	req := machineReq(samples(1, 2, 3), "s")
	req.GitHub.Commit = sha
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	require.NotNil(t, row.CommitID)

	// Drain the async backfill enqueued by step 1 BEFORE snapshotting request
	// counts: its /commits page would otherwise race the assertions below. The
	// gap commit landed, exclusive of the window bounds. Later steps never
	// enqueue (resubmits short-circuit, unknown commits do not backfill), so
	// the drained backfiller stays out of the picture.
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	backfiller.Shutdown(shutdownCtx)
	_, err = store.GetCommitID(ctx, "gapcommit", testRepo)
	require.NoError(t, err, "backfill should have inserted the gap commit")

	// 2. Resubmit: short-circuit, request count to GitHub unchanged.
	before := len(srv.Requests())
	req2 := machineReq(samples(2, 3, 4), "s")
	req2.GitHub.Commit = sha
	_, err = ing.Submit(ctx, req2)
	require.NoError(t, err)
	assert.Len(t, srv.Requests(), before, "resubmission must not call GitHub")

	// 3. Unknown sha: degraded row, result persists.
	req3 := machineReq(samples(3, 4, 5), "s")
	req3.GitHub.Commit = "deadbeef"
	res3, err := ing.Submit(ctx, req3)
	require.NoError(t, err)
	row3, err := store.GetBenchmarkResultByID(ctx, res3.ID)
	require.NoError(t, err)
	assert.NotNil(t, row3.CommitID, "unknown commits still get a commit row")
	assert.Equal(t, int64(1), provider.UnknownCommitCount())

	// 3b. Resubmit the same unknown sha: the existence short-circuit means the
	// provider never runs, so GitHub is not called again and the unknown
	// counter does not increment (the previously-unknown row stays unknown).
	beforeUnknown := len(srv.Requests())
	req3b := machineReq(samples(4, 5, 6), "s")
	req3b.GitHub.Commit = "deadbeef"
	_, err = ing.Submit(ctx, req3b)
	require.NoError(t, err)
	assert.Len(t, srv.Requests(), beforeUnknown, "resubmitting an unknown sha must not retry enrichment")
	assert.Equal(t, int64(1), provider.UnknownCommitCount(), "short-circuit must not re-count the unknown commit")
}
