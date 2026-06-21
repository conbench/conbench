package db_test

import (
	"context"
	"os"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"

	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/storage"
)

// newTestStore starts an ephemeral Postgres (the pinned image), applies the
// generated schema, and returns a Store. It skips when Docker is unavailable so
// `go test ./...` stays green off-CI; when Docker is present the tests run
// against real Postgres, never mocks.
func newTestStore(t *testing.T) (*db.Store, *pgxpool.Pool, context.Context) {
	t.Helper()
	if testing.Short() {
		t.Skip("skipping Postgres-backed test in -short mode")
	}
	ctx := context.Background()

	container, err := postgres.Run(ctx, "postgres:15.2-alpine",
		postgres.WithDatabase("conbench"),
		postgres.WithUsername("postgres"),
		postgres.WithPassword("postgres"),
		postgres.BasicWaitStrategies(),
	)
	if err != nil {
		t.Skipf("skipping: cannot start Postgres container (Docker required): %v", err)
	}
	t.Cleanup(func() { _ = testcontainers.TerminateContainer(container) })

	connStr, err := container.ConnectionString(ctx, "sslmode=disable")
	require.NoError(t, err, "connection string")
	pool, err := pgxpool.New(ctx, connStr)
	require.NoError(t, err, "open pool")
	t.Cleanup(pool.Close)

	schema, err := os.ReadFile("schema.sql")
	require.NoError(t, err, "read schema.sql")
	_, err = pool.Exec(ctx, string(schema))
	require.NoError(t, err, "apply schema")
	return db.NewStore(pool), pool, ctx
}

func machineParams(name string) storage.InsertHardwareParams {
	return storage.InsertHardwareParams{
		Type:             "machine",
		Name:             name,
		Hash:             "machinehash-" + name,
		ArchitectureName: new("x86_64"),
		CpuCoreCount:     new(int32(8)),
		CpuThreadCount:   new(int32(16)),
		MemoryBytes:      new(int64(16) << 30),
		GpuCount:         new(int32(0)),
		GpuProductNames:  []string{},
	}
}

// TestGetOrCreateIdempotent covers the core acceptance criterion: get-or-create
// returns the same id for the same natural key and a new id for a new key,
// across case, context, info, and hardware (machine, cluster, and the NULL-field
// machine that the IS NOT DISTINCT FROM key must still dedup).
func TestGetOrCreateIdempotent(t *testing.T) {
	store, _, ctx := newTestStore(t)

	t.Run("case", func(t *testing.T) {
		a, err := store.GetOrCreateCase(ctx, "bench-a", []byte(`{"k":"v"}`))
		mustID(t, a, err)
		b, err := store.GetOrCreateCase(ctx, "bench-a", []byte(`{"k":"v"}`))
		mustID(t, b, err)
		assert.Equal(t, a, b, "same case key returned different ids")
		c, err := store.GetOrCreateCase(ctx, "bench-a", []byte(`{"k":"other"}`))
		mustID(t, c, err)
		assert.NotEqual(t, a, c, "different tags returned the same id")
	})

	t.Run("context", func(t *testing.T) {
		a, err := store.GetOrCreateContext(ctx, []byte(`{"compiler":"gcc"}`))
		mustID(t, a, err)
		b, err := store.GetOrCreateContext(ctx, []byte(`{"compiler":"gcc"}`))
		mustID(t, b, err)
		assert.Equal(t, a, b, "same context returned different ids")
	})

	t.Run("info", func(t *testing.T) {
		a, err := store.GetOrCreateInfo(ctx, []byte(`{"v":"1"}`))
		mustID(t, a, err)
		b, err := store.GetOrCreateInfo(ctx, []byte(`{"v":"1"}`))
		mustID(t, b, err)
		assert.Equal(t, a, b, "same info returned different ids")
	})

	t.Run("machine", func(t *testing.T) {
		a, err := store.GetOrCreateHardware(ctx, machineParams("m1"))
		mustID(t, a, err)
		b, err := store.GetOrCreateHardware(ctx, machineParams("m1"))
		mustID(t, b, err)
		assert.Equal(t, a, b, "same machine returned different ids")
		other, err := store.GetOrCreateHardware(ctx, machineParams("m2"))
		mustID(t, other, err)
		assert.NotEqual(t, a, other, "different machine returned the same id")
	})

	t.Run("machine with NULL fields dedups via IS NOT DISTINCT FROM", func(t *testing.T) {
		p := storage.InsertHardwareParams{Type: "machine", Name: "sparse", Hash: "h-sparse", GpuProductNames: []string{}}
		a, err := store.GetOrCreateHardware(ctx, p)
		mustID(t, a, err)
		b, err := store.GetOrCreateHardware(ctx, p)
		mustID(t, b, err)
		assert.Equal(t, a, b, "NULL-field machine not deduped")
	})

	t.Run("cluster", func(t *testing.T) {
		p := storage.InsertHardwareParams{Type: "cluster", Name: "c1", Hash: "h-c1", Info: []byte(`{"nodes":3}`)}
		a, err := store.GetOrCreateHardware(ctx, p)
		mustID(t, a, err)
		b, err := store.GetOrCreateHardware(ctx, p)
		mustID(t, b, err)
		assert.Equal(t, a, b, "same cluster returned different ids")
		p2 := storage.InsertHardwareParams{Type: "cluster", Name: "c1", Hash: "h-c1b", Info: []byte(`{"nodes":4}`)}
		other, err := store.GetOrCreateHardware(ctx, p2)
		mustID(t, other, err)
		assert.NotEqual(t, a, other, "different cluster info returned the same id")
	})
}

// TestInsertBenchmarkResultFKFlow creates the parent rows, inserts a result that
// references them, and reads it back.
func TestInsertBenchmarkResultFKFlow(t *testing.T) {
	store, _, ctx := newTestStore(t)

	caseID, err := store.GetOrCreateCase(ctx, "bench", []byte(`{"k":"v"}`))
	mustID(t, caseID, err)
	contextID, err := store.GetOrCreateContext(ctx, []byte(`{"c":"1"}`))
	mustID(t, contextID, err)
	infoID, err := store.GetOrCreateInfo(ctx, []byte(`{}`))
	mustID(t, infoID, err)
	hardwareID, err := store.GetOrCreateHardware(ctx, machineParams("m1"))
	mustID(t, hardwareID, err)
	commitID, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "abc", Repository: "https://github.com/org/repo", Message: "", AuthorName: "",
		ForkPointSha: new("abc"),
	})
	mustID(t, commitID, err)

	resultID, err := store.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
		CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hardwareID,
		RunID: "run-1", RunTags: []byte(`{"name":"bench"}`), CommitID: new(commitID),
		CommitRepoUrl: "https://github.com/org/repo", HistoryFingerprint: "fp-1",
		Timestamp: time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC),
		Unit:      new("s"), Data: []*float64{new(1.0), new(2.0), new(3.0)}, Mean: new(2.0),
	})
	mustID(t, resultID, err)

	got, err := store.GetBenchmarkResultByID(ctx, resultID)
	require.NoError(t, err)
	assert.Equal(t, caseID, got.CaseID)
	assert.Equal(t, hardwareID, got.HardwareID)
	if assert.NotNil(t, got.CommitID) {
		assert.Equal(t, commitID, *got.CommitID)
	}
	if assert.Len(t, got.Data, 3) {
		require.NotNil(t, got.Data[0])
		assert.InDelta(t, 1.0, *got.Data[0], 1e-9)
	}
	if assert.NotNil(t, got.Mean) {
		assert.InDelta(t, 2.0, *got.Mean, 1e-9)
	}
}

// TestBenchmarkResultNullableElements round-trips data/times arrays that contain
// null elements through the store, exercising the []*float64 storage shape that
// errored results need. The ingest path still stores nil arrays for errored
// results; this verifies the column can hold per-element nulls when written
// directly, independent of that behavior gate.
func TestBenchmarkResultNullableElements(t *testing.T) {
	store, _, ctx := newTestStore(t)

	caseID, err := store.GetOrCreateCase(ctx, "bench", []byte(`{}`))
	require.NoError(t, err)
	contextID, err := store.GetOrCreateContext(ctx, []byte(`{}`))
	require.NoError(t, err)
	infoID, err := store.GetOrCreateInfo(ctx, []byte(`{}`))
	require.NoError(t, err)
	hwID, err := store.GetOrCreateHardware(ctx, storage.InsertHardwareParams{
		Type: "machine", Name: "m", Hash: "h",
	})
	require.NoError(t, err)

	id, err := store.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
		CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hwID,
		RunID: "r1", RunTags: []byte(`{}`), CommitRepoUrl: "https://github.com/x/y",
		HistoryFingerprint: "fp-null-elems",
		Timestamp:          time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC),
		Error:              []byte(`{"status":"boom"}`),
		Data:               []*float64{new(1.5), nil, new(2.0)},
		Times:              []*float64{nil, new(0.25)},
	})
	require.NoError(t, err)

	got, err := store.GetBenchmarkResultByID(ctx, id)
	require.NoError(t, err)
	require.Equal(t, []*float64{new(1.5), nil, new(2.0)}, got.Data)
	require.Equal(t, []*float64{nil, new(0.25)}, got.Times)
}

// TestHistoryFiltersMembership asserts the membership query drops errored
// results, results with no commit, and results not on the default branch
// (sha != fork_point_sha), keeping only the matching-fingerprint default-branch
// non-errored result.
func TestHistoryFiltersMembership(t *testing.T) {
	store, _, ctx := newTestStore(t)
	const fp = "fp-history"

	caseID, _ := store.GetOrCreateCase(ctx, "bench", []byte(`{}`))
	contextID, _ := store.GetOrCreateContext(ctx, []byte(`{}`))
	infoID, _ := store.GetOrCreateInfo(ctx, []byte(`{}`))
	hardwareID, _ := store.GetOrCreateHardware(ctx, machineParams("m1"))

	commitTS := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	defaultCommit, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "default-sha", Repository: "repo", Message: "", AuthorName: "",
		ForkPointSha: new("default-sha"), // on default branch: sha == fork_point_sha
		Timestamp:    new(commitTS),      // membership requires a non-null commit timestamp
	})
	mustID(t, defaultCommit, err)
	featureCommit, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "feature-sha", Repository: "repo", Message: "", AuthorName: "",
		ForkPointSha: new("base-sha"), // off default branch: sha != fork_point_sha
		Timestamp:    new(commitTS),
	})
	mustID(t, featureCommit, err)

	insert := func(p storage.InsertBenchmarkResultParams) string {
		p.CaseID, p.ContextID, p.InfoID, p.HardwareID = caseID, contextID, infoID, hardwareID
		p.RunID, p.RunTags, p.CommitRepoUrl = "run", []byte(`{"name":"b"}`), "repo"
		p.Timestamp = time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
		id, err := store.InsertBenchmarkResult(ctx, p)
		mustID(t, id, err)
		return id
	}

	wantID := insert(storage.InsertBenchmarkResultParams{HistoryFingerprint: fp, CommitID: new(defaultCommit)})
	insert(storage.InsertBenchmarkResultParams{HistoryFingerprint: fp, CommitID: new(defaultCommit), Error: []byte(`{"x":1}`)})
	insert(storage.InsertBenchmarkResultParams{HistoryFingerprint: fp, CommitID: nil})
	insert(storage.InsertBenchmarkResultParams{HistoryFingerprint: fp, CommitID: new(featureCommit)})
	insert(storage.InsertBenchmarkResultParams{HistoryFingerprint: "other-fp", CommitID: new(defaultCommit)})

	rows, err := store.SelectHistoryForFingerprint(ctx, fp)
	require.NoError(t, err)
	require.Len(t, rows, 1, "errored/no-commit/non-default must be excluded")
	assert.Equal(t, wantID, rows[0].ID)
}

// TestHistorySelectsChangeAnnotations asserts the membership query returns the
// change_annotations column so the service can read begins_distribution_change.
func TestHistorySelectsChangeAnnotations(t *testing.T) {
	store, pool, ctx := newTestStore(t)
	const fp = "fp-annotations"

	caseID, _ := store.GetOrCreateCase(ctx, "bench", []byte(`{}`))
	contextID, _ := store.GetOrCreateContext(ctx, []byte(`{}`))
	infoID, _ := store.GetOrCreateInfo(ctx, []byte(`{}`))
	hardwareID, _ := store.GetOrCreateHardware(ctx, machineParams("m1"))
	commitID, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "sha-ann", Repository: "repo", Message: "", AuthorName: "",
		ForkPointSha: new("sha-ann"),
		Timestamp:    new(time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)), // membership requires non-null
	})
	mustID(t, commitID, err)

	id, err := store.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
		CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hardwareID,
		RunID: "run", RunTags: []byte(`{"name":"b"}`), CommitID: new(commitID),
		CommitRepoUrl: "repo", HistoryFingerprint: fp,
		Timestamp: time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC),
		Unit:      new("s"), Data: []*float64{new(1.0), new(2.0), new(3.0)},
	})
	mustID(t, id, err)

	_, err = pool.Exec(ctx,
		`UPDATE benchmark_result SET change_annotations = $1 WHERE id = $2`,
		[]byte(`{"begins_distribution_change":true}`), id)
	require.NoError(t, err)

	rows, err := store.SelectHistoryForFingerprint(ctx, fp)
	require.NoError(t, err)
	require.Len(t, rows, 1)
	assert.JSONEq(t, `{"begins_distribution_change":true}`, string(rows[0].ChangeAnnotations))
}

// TestGetResultForCompare returns the comparison fields for one result and maps a
// missing id to ErrNotFound.
func TestGetResultForCompare(t *testing.T) {
	store, _, ctx := newTestStore(t)
	caseID, _ := store.GetOrCreateCase(ctx, "bench", []byte(`{}`))
	contextID, _ := store.GetOrCreateContext(ctx, []byte(`{}`))
	infoID, _ := store.GetOrCreateInfo(ctx, []byte(`{}`))
	hardwareID, _ := store.GetOrCreateHardware(ctx, machineParams("m1"))
	ct := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	commitID, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "sha-cmp", Repository: "repo", Message: "", AuthorName: "",
		ForkPointSha: new("sha-cmp"), Timestamp: new(ct),
	})
	mustID(t, commitID, err)
	id, err := store.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
		CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hardwareID,
		RunID: "run-x", RunTags: []byte(`{"name":"b"}`), CommitID: new(commitID),
		CommitRepoUrl: "repo", HistoryFingerprint: "fp-cmp",
		Timestamp: ct, Unit: new("s"), Data: []*float64{new(1.0), new(2.0), new(3.0)},
	})
	mustID(t, id, err)

	row, err := store.GetResultForCompare(ctx, id)
	require.NoError(t, err)
	assert.Equal(t, "run-x", row.RunID)
	assert.Equal(t, "fp-cmp", row.HistoryFingerprint)
	require.NotNil(t, row.Unit)
	assert.Equal(t, "s", *row.Unit)
	assert.Len(t, row.Data, 3)
	require.NotNil(t, row.CommitID)
	require.NotNil(t, row.CommitTimestamp)
	assert.True(t, row.CommitTimestamp.Equal(ct))

	_, err = store.GetResultForCompare(ctx, "0000000000000000000000000000ffff")
	require.ErrorIs(t, err, storage.ErrNotFound)
}

// TestSelectHistoryAsOfCutoff asserts the baseline window honors the timestamp
// cutoff (inclusive), keeps tied-at-cutoff rows, and applies the same membership
// filters as the full history query.
func TestSelectHistoryAsOfCutoff(t *testing.T) {
	store, _, ctx := newTestStore(t)
	const fp = "fp-asof"
	caseID, _ := store.GetOrCreateCase(ctx, "bench", []byte(`{}`))
	contextID, _ := store.GetOrCreateContext(ctx, []byte(`{}`))
	infoID, _ := store.GetOrCreateInfo(ctx, []byte(`{}`))
	hardwareID, _ := store.GetOrCreateHardware(ctx, machineParams("m1"))

	mkCommit := func(sha string, fork string, d int) string {
		ts := time.Date(2026, 6, d, 12, 0, 0, 0, time.UTC)
		id, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
			Sha: sha, Repository: "repo", Message: "", AuthorName: "",
			ForkPointSha: new(fork), Timestamp: new(ts),
		})
		mustID(t, id, err)
		return id
	}
	day1 := mkCommit("d1", "d1", 1)
	day2 := mkCommit("d2", "d2", 2)
	day2tie := mkCommit("d2b", "d2b", 2) // same commit timestamp as day2
	day3 := mkCommit("d3", "d3", 3)
	offBranch := mkCommit("f1", "base", 2) // sha != fork_point_sha

	insert := func(commitID string, errBytes []byte) string {
		id, err := store.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
			CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hardwareID,
			RunID: "run", RunTags: []byte(`{"name":"b"}`), CommitID: new(commitID),
			CommitRepoUrl: "repo", HistoryFingerprint: fp,
			Timestamp: time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC),
			Unit:      new("s"), Data: []*float64{new(1.0)}, Error: errBytes,
		})
		mustID(t, id, err)
		return id
	}
	insert(day1, nil)
	insert(day2, nil)
	insert(day2tie, nil)
	insert(day3, nil)          // after cutoff: excluded
	insert(offBranch, nil)     // off default branch: excluded
	insert(day1, []byte(`{}`)) // errored: excluded

	cutoff := time.Date(2026, 6, 2, 12, 0, 0, 0, time.UTC)
	rows, err := store.SelectHistoryForFingerprintAsOf(ctx, fp, cutoff)
	require.NoError(t, err)
	// day1 + day2 + day2tie; day3/off-branch/errored excluded.
	require.Len(t, rows, 3, "cutoff inclusive of ties, exclusive of later/off-branch/errored")
	got := map[string]bool{}
	for _, r := range rows {
		got[r.CommitSha] = true
	}
	assert.Equal(t, map[string]bool{"d1": true, "d2": true, "d2b": true}, got,
		"as-of window must return exactly the at-or-before-cutoff default-branch rows")
}

// TestSelectBenchmarkResultsFiltersAndCursor covers run_id/batch_id/run_reason/timestamp
// filters, id-DESC ordering, the cursor bound, and the page-size limit.
func TestSelectBenchmarkResultsFiltersAndCursor(t *testing.T) {
	store, _, ctx := newTestStore(t)
	caseID, _ := store.GetOrCreateCase(ctx, "bench", []byte(`{}`))
	contextID, _ := store.GetOrCreateContext(ctx, []byte(`{}`))
	infoID, _ := store.GetOrCreateInfo(ctx, []byte(`{}`))
	hardwareID, _ := store.GetOrCreateHardware(ctx, machineParams("m1"))

	mk := func(runID, batchID, runReason string, d int) string {
		id, err := store.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
			CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hardwareID,
			RunID: runID, BatchID: new(batchID), RunReason: new(runReason), RunTags: []byte(`{"name":"b"}`),
			CommitRepoUrl: "repo", HistoryFingerprint: "fp",
			Timestamp: time.Date(2026, 6, d, 12, 0, 0, 0, time.UTC),
			Unit:      new("s"), Data: []*float64{new(1.0)},
		})
		mustID(t, id, err)
		return id
	}
	a := mk("run-a", "batch-a", "commit", 1)
	b := mk("run-a", "batch-b", "pull request", 2)
	c := mk("run-b", "batch-b", "commit", 3)

	all, err := store.SelectBenchmarkResults(ctx, storage.ListResultsParams{PageSize: 100})
	require.NoError(t, err)
	require.Len(t, all, 3)
	// id DESC == newest-first; a<b<c by UUIDv7 insertion order.
	assert.Equal(t, []string{c, b, a}, []string{all[0].ID, all[1].ID, all[2].ID})

	byRun, err := store.SelectBenchmarkResults(ctx, storage.ListResultsParams{RunID: new("run-a"), PageSize: 100})
	require.NoError(t, err)
	require.Len(t, byRun, 2)

	byBatch, err := store.SelectBenchmarkResults(ctx, storage.ListResultsParams{BatchID: new("batch-b"), PageSize: 100})
	require.NoError(t, err)
	require.Len(t, byBatch, 2)
	assert.Equal(t, []string{c, b}, []string{byBatch[0].ID, byBatch[1].ID})

	byReason, err := store.SelectBenchmarkResults(ctx, storage.ListResultsParams{RunReason: new("pull request"), PageSize: 100})
	require.NoError(t, err)
	require.Len(t, byReason, 1)
	assert.Equal(t, b, byReason[0].ID)

	page1, err := store.SelectBenchmarkResults(ctx, storage.ListResultsParams{PageSize: 2})
	require.NoError(t, err)
	require.Len(t, page1, 2)
	assert.Equal(t, []string{c, b}, []string{page1[0].ID, page1[1].ID})
	page2, err := store.SelectBenchmarkResults(ctx, storage.ListResultsParams{Cursor: new(page1[1].ID), PageSize: 2})
	require.NoError(t, err)
	require.Len(t, page2, 1)
	assert.Equal(t, a, page2[0].ID)
}

// TestResultLookupNotFound asserts the adapter maps a missing row to the
// storage.ErrNotFound sentinel for both result lookups, so the service never
// sees the backend's pgx.ErrNoRows.
func TestResultLookupNotFound(t *testing.T) {
	store, _, ctx := newTestStore(t)
	const missing = "0000000000000000000000000000ffff"

	_, err := store.GetBenchmarkResultByID(ctx, missing)
	require.ErrorIs(t, err, storage.ErrNotFound)

	_, err = store.GetBenchmarkResultDetail(ctx, missing)
	require.ErrorIs(t, err, storage.ErrNotFound)
}

// TestGetCommitID maps a missing (sha, repository) to ErrNotFound and returns
// the get-or-create id when the row exists. The ingester uses this to
// short-circuit GitHub enrichment for known commits.
func TestGetCommitID(t *testing.T) {
	store, _, ctx := newTestStore(t)

	_, err := store.GetCommitID(ctx, "nosuch", "https://github.com/org/repo")
	require.ErrorIs(t, err, storage.ErrNotFound)

	id, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "abc", Repository: "https://github.com/org/repo",
	})
	require.NoError(t, err)

	got, err := store.GetCommitID(ctx, "abc", "https://github.com/org/repo")
	require.NoError(t, err)
	assert.Equal(t, id, got)
}

func TestUnknownCommitRepairCandidates(t *testing.T) {
	store, _, ctx := newTestStore(t)

	mk := func(sha, repository string, timestamp *time.Time, forkPointSha *string) string {
		id, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
			Sha: sha, Repository: repository, Timestamp: timestamp, ForkPointSha: forkPointSha,
		})
		require.NoError(t, err)
		return id
	}

	repoA := "https://github.com/org/a"
	repoB := "https://github.com/org/b"
	knownTS := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	idA2 := mk("a2", repoA, nil, nil)
	idB1 := mk("b1", repoB, nil, nil)
	idB2 := mk("b2", repoB, nil, nil)
	mk("a1", repoA, &knownTS, nil)
	mk("a3", repoA, nil, new(string))
	mk("", repoA, nil, nil)
	mk("a4", "", nil, nil)

	t.Run("selects unknown rows with nonempty keys ordered by repository then sha", func(t *testing.T) {
		rows, err := store.SelectUnknownCommitRepairCandidates(ctx, storage.UnknownCommitCandidateParams{
			LimitPlusOne: 10,
		})
		require.NoError(t, err)
		require.Equal(t, []storage.UnknownCommitCandidate{
			{ID: idA2, Sha: "a2", Repository: repoA},
			{ID: idB1, Sha: "b1", Repository: repoB},
			{ID: idB2, Sha: "b2", Repository: repoB},
		}, rows)
	})

	t.Run("repository filter matches exact stored value", func(t *testing.T) {
		rows, err := store.SelectUnknownCommitRepairCandidates(ctx, storage.UnknownCommitCandidateParams{
			Repository:   &repoB,
			LimitPlusOne: 10,
		})
		require.NoError(t, err)
		require.Equal(t, []storage.UnknownCommitCandidate{
			{ID: idB1, Sha: "b1", Repository: repoB},
			{ID: idB2, Sha: "b2", Repository: repoB},
		}, rows)

		normalizedElsewhere := repoB + "/"
		rows, err = store.SelectUnknownCommitRepairCandidates(ctx, storage.UnknownCommitCandidateParams{
			Repository:   &normalizedElsewhere,
			LimitPlusOne: 10,
		})
		require.NoError(t, err)
		assert.Empty(t, rows)
	})

	t.Run("cursor starts after repository and sha", func(t *testing.T) {
		rows, err := store.SelectUnknownCommitRepairCandidates(ctx, storage.UnknownCommitCandidateParams{
			AfterRepository: &repoA,
			AfterSha:        new("a2"),
			LimitPlusOne:    10,
		})
		require.NoError(t, err)
		require.Equal(t, []storage.UnknownCommitCandidate{
			{ID: idB1, Sha: "b1", Repository: repoB},
			{ID: idB2, Sha: "b2", Repository: repoB},
		}, rows)
	})
}

func TestUpdateUnknownCommit(t *testing.T) {
	store, pool, ctx := newTestStore(t)

	id, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "unknown-sha", Repository: "https://github.com/org/repo",
	})
	require.NoError(t, err)

	parent := "parent-sha"
	authorLogin := "octocat"
	authorAvatar := "https://avatars.githubusercontent.com/u/1"
	branch := "main"
	forkPointSha := "unknown-sha"
	ts := time.Date(2026, 6, 17, 12, 30, 0, 0, time.UTC)

	rows, err := store.UpdateUnknownCommit(ctx, storage.UpdateUnknownCommitParams{
		ID: id, Parent: &parent, Message: "subject", AuthorName: "Author",
		AuthorLogin: &authorLogin, AuthorAvatar: &authorAvatar,
		Timestamp: ts, Branch: &branch, ForkPointSha: &forkPointSha,
	})
	require.NoError(t, err)
	assert.Equal(t, int64(1), rows)

	var got struct {
		Parent       *string
		Message      string
		AuthorName   string
		AuthorLogin  *string
		AuthorAvatar *string
		Timestamp    *time.Time
		Branch       *string
		ForkPointSha *string
	}
	err = pool.QueryRow(ctx, `
		SELECT parent, message, author_name, author_login, author_avatar, timestamp, branch, fork_point_sha
		FROM commit
		WHERE id = $1`, id).Scan(
		&got.Parent, &got.Message, &got.AuthorName, &got.AuthorLogin, &got.AuthorAvatar,
		&got.Timestamp, &got.Branch, &got.ForkPointSha,
	)
	require.NoError(t, err)
	require.NotNil(t, got.Parent)
	assert.Equal(t, parent, *got.Parent)
	assert.Equal(t, "subject", got.Message)
	assert.Equal(t, "Author", got.AuthorName)
	require.NotNil(t, got.AuthorLogin)
	assert.Equal(t, authorLogin, *got.AuthorLogin)
	require.NotNil(t, got.AuthorAvatar)
	assert.Equal(t, authorAvatar, *got.AuthorAvatar)
	require.NotNil(t, got.Timestamp)
	assert.True(t, got.Timestamp.Equal(ts))
	require.NotNil(t, got.Branch)
	assert.Equal(t, branch, *got.Branch)
	require.NotNil(t, got.ForkPointSha)
	assert.Equal(t, forkPointSha, *got.ForkPointSha)

	overwriteParent := "overwrite-parent"
	overwriteFork := "overwrite-fork"
	rows, err = store.UpdateUnknownCommit(ctx, storage.UpdateUnknownCommitParams{
		ID: id, Parent: &overwriteParent, Message: "overwrite", AuthorName: "Other",
		Timestamp: ts.Add(time.Hour), ForkPointSha: &overwriteFork,
	})
	require.NoError(t, err)
	assert.Equal(t, int64(0), rows)

	err = pool.QueryRow(ctx, `
		SELECT parent, message, author_name, timestamp, fork_point_sha
		FROM commit
		WHERE id = $1`, id).Scan(&got.Parent, &got.Message, &got.AuthorName, &got.Timestamp, &got.ForkPointSha)
	require.NoError(t, err)
	require.NotNil(t, got.Parent)
	assert.Equal(t, parent, *got.Parent)
	assert.Equal(t, "subject", got.Message)
	assert.Equal(t, "Author", got.AuthorName)
	require.NotNil(t, got.Timestamp)
	assert.True(t, got.Timestamp.Equal(ts))
	require.NotNil(t, got.ForkPointSha)
	assert.Equal(t, forkPointSha, *got.ForkPointSha)
}

// TestAPITokenRoundTrip mints a token row and reads it back by hash, asserting
// the stored columns and the nil-by-default last_used_at/revoked_at, and maps a
// missing hash to ErrNotFound.
func TestAPITokenRoundTrip(t *testing.T) {
	store, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)

	created := time.Date(2026, 6, 12, 10, 0, 0, 0, time.UTC)
	id, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: userID, Name: "ci", TokenHash: "deadbeef", TokenPrefix: "cb_dead1",
		CreatedAt: created,
	})
	require.NoError(t, err)
	require.NotEmpty(t, id)

	row, err := store.GetAPITokenByHash(ctx, "deadbeef")
	require.NoError(t, err)
	assert.Equal(t, id, row.ID)
	assert.Equal(t, userID, row.UserID)
	assert.Equal(t, "ci", row.Name)
	assert.Equal(t, "cb_dead1", row.TokenPrefix)
	assert.True(t, row.CreatedAt.Equal(created))
	assert.Nil(t, row.LastUsedAt)
	assert.Nil(t, row.RevokedAt)

	_, err = store.GetAPITokenByHash(ctx, "nosuch")
	require.ErrorIs(t, err, storage.ErrNotFound)
}

// TestAPITokenTouchAndRevoke updates last_used_at then revoked_at and reads each
// back through the by-hash lookup.
func TestAPITokenTouchAndRevoke(t *testing.T) {
	store, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)

	id, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: userID, Name: "ci", TokenHash: "h1", TokenPrefix: "cb_h1xxx",
		CreatedAt: time.Date(2026, 6, 12, 10, 0, 0, 0, time.UTC),
	})
	require.NoError(t, err)

	used := time.Date(2026, 6, 12, 11, 0, 0, 0, time.UTC)
	require.NoError(t, store.TouchAPITokenLastUsed(ctx, id, used))
	row, err := store.GetAPITokenByHash(ctx, "h1")
	require.NoError(t, err)
	require.NotNil(t, row.LastUsedAt)
	assert.True(t, row.LastUsedAt.Equal(used))

	revoked := used.Add(time.Hour)
	require.NoError(t, store.RevokeAPIToken(ctx, id, revoked))
	row, err = store.GetAPITokenByHash(ctx, "h1")
	require.NoError(t, err)
	require.NotNil(t, row.RevokedAt)
	assert.True(t, row.RevokedAt.Equal(revoked))

	err = store.RevokeAPIToken(ctx, "nosuchid", revoked)
	assert.ErrorIs(t, err, storage.ErrNotFound, "revoking a nonexistent id must not look like success")
}

// TestAPITokenHashUniqueViolation asserts the unique index on token_hash rejects
// a second row with the same hash.
func TestAPITokenHashUniqueViolation(t *testing.T) {
	store, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)

	p := storage.InsertAPITokenParams{
		UserID: userID, Name: "ci", TokenHash: "dup", TokenPrefix: "cb_dupxx",
		CreatedAt: time.Date(2026, 6, 12, 10, 0, 0, 0, time.UTC),
	}
	_, err := store.CreateAPIToken(ctx, p)
	require.NoError(t, err)
	_, err = store.CreateAPIToken(ctx, p)
	require.Error(t, err, "duplicate token_hash must violate the unique constraint")
}

// TestListAPITokensByUser asserts the list returns only the given user's tokens,
// newest first, and an empty (non-error) result for an unknown user.
func TestListAPITokensByUser(t *testing.T) {
	store, pool, ctx := newTestStore(t)
	u1 := dbtest.SeedUser(t, ctx, pool)
	u2 := dbtest.SeedUser(t, ctx, pool)

	mk := func(user, hash, prefix string, at time.Time) string {
		id, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
			UserID: user, Name: "n", TokenHash: hash, TokenPrefix: prefix, CreatedAt: at,
		})
		require.NoError(t, err)
		return id
	}
	older := time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC)
	newer := time.Date(2026, 6, 2, 0, 0, 0, 0, time.UTC)
	a := mk(u1, "h-a", "cb_aaaaa", older)
	b := mk(u1, "h-b", "cb_bbbbb", newer)
	mk(u2, "h-c", "cb_ccccc", newer)

	rows, err := store.ListAPITokensByUser(ctx, u1)
	require.NoError(t, err)
	require.Len(t, rows, 2, "only u1's tokens")
	assert.Equal(t, b, rows[0].ID, "newest first")
	assert.Equal(t, a, rows[1].ID)

	none, err := store.ListAPITokensByUser(ctx, "nobody")
	require.NoError(t, err)
	assert.Empty(t, none)
}

// TestGetAPITokenByID reads a token by id and maps a missing id to ErrNotFound.
func TestGetAPITokenByID(t *testing.T) {
	store, pool, ctx := newTestStore(t)
	u := dbtest.SeedUser(t, ctx, pool)
	id, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: u, Name: "ci", TokenHash: "h1", TokenPrefix: "cb_h1xxx",
		CreatedAt: time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC),
	})
	require.NoError(t, err)

	row, err := store.GetAPITokenByID(ctx, id)
	require.NoError(t, err)
	assert.Equal(t, u, row.UserID)
	assert.Equal(t, "ci", row.Name)

	_, err = store.GetAPITokenByID(ctx, "nope")
	require.ErrorIs(t, err, storage.ErrNotFound)
}

func mustID(t *testing.T, id string, err error) {
	t.Helper()
	require.NoError(t, err)
	require.NotEmpty(t, id, "got empty id")
}

func TestGetOrCreateUserByEmail(t *testing.T) {
	store, _, ctx := newTestStore(t)

	id1, err := store.GetOrCreateUserByEmail(ctx, "dev@example.com", "Dev One", "!")
	require.NoError(t, err)
	require.NotEmpty(t, id1)

	// Same email returns the same row (no duplicate), even with a different name.
	id2, err := store.GetOrCreateUserByEmail(ctx, "dev@example.com", "Renamed", "!")
	require.NoError(t, err)
	assert.Equal(t, id1, id2)

	// A different email is a different row.
	id3, err := store.GetOrCreateUserByEmail(ctx, "other@example.com", "Other", "!")
	require.NoError(t, err)
	assert.NotEqual(t, id1, id3)

	row, err := store.GetUserByID(ctx, id1)
	require.NoError(t, err)
	assert.Equal(t, "dev@example.com", row.Email)
	assert.Equal(t, "Dev One", row.Name, "first-write name is kept; get-or-create does not update")
}

func TestGetUserByIDNotFound(t *testing.T) {
	store, _, ctx := newTestStore(t)
	_, err := store.GetUserByID(ctx, "nosuchuser")
	require.ErrorIs(t, err, storage.ErrNotFound)
}
