package db_test

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/storage"
)

const ciReportRepo = "https://github.com/org/repo"

type ciReportSeed struct {
	CaseID     string
	ContextID  string
	InfoID     string
	HardwareID string
}

type ciResultSeed struct {
	RunID              string
	RunTags            []byte
	RunReason          *string
	CommitID           string
	CommitRepoURL      string
	HistoryFingerprint string
	ResultTimestamp    time.Time
	Unit               *string
	Data               []*float64
	Error              []byte
}

func TestSelectCIReportRunsByCommit(t *testing.T) {
	st, _, ctx := newTestStore(t)
	seed := newCIReportSeed(t, st, ctx)
	ts := ciReportTime(1)
	commitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "commit-a", "parent-a", "fork-a", &ts, "contender")
	otherRepoCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo+"/", "commit-a", "", "commit-a", &ts, "unnormalized")
	otherShaCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "commit-b", "", "commit-b", &ts, "other")

	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-a", RunTags: []byte(`{"github_run_id":"1"}`), RunReason: new("pull request"),
		CommitID: commitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-a",
		ResultTimestamp: ciReportTime(10), Unit: new("ns"), Data: []*float64{new(1.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-a", RunTags: []byte(`{"github_run_id":"1"}`), RunReason: new("pull request"),
		CommitID: commitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-b",
		ResultTimestamp: ciReportTime(11), Unit: new("ns"), Data: []*float64{new(2.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-b", RunTags: []byte(`{"github_run_id":"2"}`), RunReason: new("pull request"),
		CommitID: commitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-c",
		ResultTimestamp: ciReportTime(12), Unit: new("ns"), Data: []*float64{new(3.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-unnormalized", RunTags: []byte(`{}`), RunReason: new("pull request"),
		CommitID: otherRepoCommitID, CommitRepoURL: ciReportRepo + "/", HistoryFingerprint: "fp-other-repo",
		ResultTimestamp: ciReportTime(13), Unit: new("ns"), Data: []*float64{new(4.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-other-sha", RunTags: []byte(`{}`), RunReason: new("pull request"),
		CommitID: otherShaCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-other-sha",
		ResultTimestamp: ciReportTime(14), Unit: new("ns"), Data: []*float64{new(5.0)},
	})

	rows, err := st.SelectCIReportRunsByCommit(ctx, ciReportRepo, "commit-a")

	require.NoError(t, err)
	require.Len(t, rows, 2, "two distinct runs for the normalized repo+commit")
	byRun := ciReportRunsByID(rows)
	assert.ElementsMatch(t, []string{"run-a", "run-b"}, ciReportRunIDs(rows))
	runA := byRun["run-a"]
	assert.JSONEq(t, `{"github_run_id":"1"}`, string(runA.RunTags))
	require.NotNil(t, runA.RunReason)
	assert.Equal(t, "pull request", *runA.RunReason)
	assert.Equal(t, ciReportRepo, runA.CommitRepoURL)
	require.NotNil(t, runA.CommitID)
	assert.Equal(t, commitID, *runA.CommitID)
	require.NotNil(t, runA.CommitSha)
	assert.Equal(t, "commit-a", *runA.CommitSha)
	require.NotNil(t, runA.CommitRepository)
	assert.Equal(t, ciReportRepo, *runA.CommitRepository)
	require.NotNil(t, runA.CommitParent)
	assert.Equal(t, "parent-a", *runA.CommitParent)
	require.NotNil(t, runA.CommitForkPointSha)
	assert.Equal(t, "fork-a", *runA.CommitForkPointSha)
	require.NotNil(t, runA.CommitTimestamp)
	assert.True(t, runA.CommitTimestamp.Equal(ts))
}

func TestSelectCIReportRunsByIDs(t *testing.T) {
	st, _, ctx := newTestStore(t)
	seed := newCIReportSeed(t, st, ctx)
	ts := ciReportTime(1)
	commitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "commit-a", "", "commit-a", &ts, "commit")

	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-present", RunTags: []byte(`{"attempt":1}`), RunReason: new("commit"),
		CommitID: commitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-a",
		ResultTimestamp: ciReportTime(10), Unit: new("s"), Data: []*float64{new(1.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-present", RunTags: []byte(`{"attempt":1}`), RunReason: new("commit"),
		CommitID: commitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-b",
		ResultTimestamp: ciReportTime(11), Unit: new("s"), Data: []*float64{new(2.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-other", RunTags: []byte(`{}`), RunReason: new("commit"),
		CommitID: commitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-c",
		ResultTimestamp: ciReportTime(12), Unit: new("s"), Data: []*float64{new(3.0)},
	})

	rows, err := st.SelectCIReportRunsByIDs(ctx, []string{"missing-run", "run-present"})

	require.NoError(t, err)
	require.Len(t, rows, 1, "missing run IDs are omitted for the service to diagnose")
	assert.Equal(t, "run-present", rows[0].RunID)
	assert.Equal(t, ciReportRepo, rows[0].CommitRepoURL)
	require.NotNil(t, rows[0].CommitSha)
	assert.Equal(t, "commit-a", *rows[0].CommitSha)
}

func TestSelectCIReportRunsByIDsReturnsCommitlessRuns(t *testing.T) {
	st, _, ctx := newTestStore(t)
	seed := newCIReportSeed(t, st, ctx)

	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-commitless", RunTags: []byte(`{"attempt":1}`), RunReason: new("pull request"),
		CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-commitless",
		ResultTimestamp: ciReportTime(10), Unit: new("s"), Data: []*float64{new(1.0)},
	})

	rows, err := st.SelectCIReportRunsByIDs(ctx, []string{"run-commitless"})

	require.NoError(t, err)
	require.Len(t, rows, 1, "explicit run selection must return commitless runs for service classification")
	assert.Equal(t, "run-commitless", rows[0].RunID)
	assert.Equal(t, ciReportRepo, rows[0].CommitRepoURL)
	assert.JSONEq(t, `{"attempt":1}`, string(rows[0].RunTags))
	require.NotNil(t, rows[0].RunReason)
	assert.Equal(t, "pull request", *rows[0].RunReason)
	assert.Nil(t, rows[0].CommitID)
	assert.Nil(t, rows[0].CommitSha)
	assert.Nil(t, rows[0].CommitRepository)
	assert.Nil(t, rows[0].CommitParent)
	assert.Nil(t, rows[0].CommitForkPointSha)
	assert.Nil(t, rows[0].CommitTimestamp)
}

func TestGetCIReportCommit(t *testing.T) {
	st, _, ctx := newTestStore(t)
	ts := ciReportTime(2)
	commitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "commit-a", "parent-a", "fork-a", &ts, "subject")

	row, err := st.GetCIReportCommit(ctx, ciReportRepo, "commit-a")

	require.NoError(t, err)
	assert.Equal(t, commitID, row.CommitID)
	assert.Equal(t, "commit-a", row.CommitSha)
	assert.Equal(t, ciReportRepo, row.Repository)
	require.NotNil(t, row.Parent)
	assert.Equal(t, "parent-a", *row.Parent)
	require.NotNil(t, row.ForkPointSha)
	assert.Equal(t, "fork-a", *row.ForkPointSha)
	require.NotNil(t, row.Timestamp)
	assert.True(t, row.Timestamp.Equal(ts))
	assert.Equal(t, "subject", row.Message)

	_, err = st.GetCIReportCommit(ctx, ciReportRepo, "missing")
	require.ErrorIs(t, err, storage.ErrNotFound)
}

func TestSelectLatestDefaultCommit(t *testing.T) {
	st, _, ctx := newTestStore(t)
	older := ciReportTime(1)
	newer := ciReportTime(2)
	later := ciReportTime(3)
	insertCIReportCommit(t, st, ctx, ciReportRepo, "default-a", "", "default-a", &older, "older")
	insertCIReportCommit(t, st, ctx, ciReportRepo, "default-b", "", "default-b", &newer, "newer b")
	wantID := insertCIReportCommit(t, st, ctx, ciReportRepo, "default-c", "", "default-c", &newer, "newer c")
	insertCIReportCommit(t, st, ctx, ciReportRepo, "feature-z", "", "default-c", &later, "feature")
	insertCIReportCommit(t, st, ctx, ciReportRepo, "no-timestamp", "", "no-timestamp", nil, "unknown")
	insertCIReportCommit(t, st, ctx, "https://github.com/org/other", "other", "", "other", &later, "other repo")

	row, err := st.SelectLatestDefaultCommit(ctx, ciReportRepo)

	require.NoError(t, err)
	assert.Equal(t, wantID, row.CommitID)
	assert.Equal(t, "default-c", row.CommitSha, "ties on timestamp break by sha DESC")
	require.NotNil(t, row.Timestamp)
	assert.True(t, row.Timestamp.Equal(newer))

	_, err = st.SelectLatestDefaultCommit(ctx, "https://github.com/org/none")
	require.ErrorIs(t, err, storage.ErrNotFound)
}

func TestSelectCIReportBaselineAncestry(t *testing.T) {
	st, _, ctx := newTestStore(t)
	ts := ciReportTime(1)
	insertCIReportCommit(t, st, ctx, ciReportRepo, "grandparent", "", "grandparent", &ts, "grandparent")
	insertCIReportCommit(t, st, ctx, ciReportRepo, "parent", "grandparent", "parent", &ts, "parent")
	insertCIReportCommit(t, st, ctx, ciReportRepo, "head", "parent", "head", &ts, "head")
	insertCIReportCommit(t, st, ctx, "https://github.com/org/other", "parent", "evil", "parent", &ts, "other repo")

	rows, err := st.SelectCIReportBaselineAncestry(ctx, ciReportRepo, "head", 2)

	require.NoError(t, err)
	assert.Equal(t, []string{"head", "parent"}, ciReportCommitShas(rows),
		"ancestry includes the starting commit and follows same-repository parents up to the limit")
}

func TestCountCIReportRows(t *testing.T) {
	st, _, ctx := newTestStore(t)
	seed := newCIReportSeed(t, st, ctx)
	ts := ciReportTime(1)
	commitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "commit-a", "", "commit-a", &ts, "commit")
	otherCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "commit-b", "", "commit-b", &ts, "other commit")

	for _, runID := range []string{"run-a", "run-a", "run-b", "run-c"} {
		insertCIReportResult(t, st, ctx, seed, ciResultSeed{
			RunID: runID, RunTags: []byte(`{}`), RunReason: new("commit"),
			CommitID: commitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-" + runID,
			ResultTimestamp: ciReportTime(10), Unit: new("s"), Data: []*float64{new(1.0)},
		})
	}
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-a", RunTags: []byte(`{}`), RunReason: new("commit"),
		CommitID: otherCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-other-commit",
		ResultTimestamp: ciReportTime(11), Unit: new("s"), Data: []*float64{new(99.0)},
	})

	count, err := st.CountCIReportRows(ctx, []storage.CIReportRunKey{
		{RunID: "run-a", CommitID: commitID},
		{RunID: "run-b", CommitID: commitID},
		{RunID: "missing", CommitID: commitID},
	})

	require.NoError(t, err)
	assert.Equal(t, int64(3), count)

	empty, err := st.CountCIReportRows(ctx, nil)
	require.NoError(t, err)
	assert.Equal(t, int64(0), empty)
}

func TestSelectCIReportRows(t *testing.T) {
	st, _, ctx := newTestStore(t)
	seed := newCIReportSeed(t, st, ctx)
	contenderTS := ciReportTime(5)
	baselineOlderTS := ciReportTime(1)
	baselineNewerTS := ciReportTime(2)
	otherTS := ciReportTime(6)
	contenderCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "contender", "parent", "base", &contenderTS, "contender")
	baselineOlderCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "base-old", "", "base-old", &baselineOlderTS, "base old")
	baselineNewerCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "base-new", "", "base-new", &baselineNewerTS, "base new")
	otherCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "other", "", "other", &otherTS, "other")

	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-contender", RunTags: []byte(`{}`), RunReason: new("pull request"),
		CommitID: contenderCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-dup",
		ResultTimestamp: ciReportTime(20), Unit: new("ns"), Data: []*float64{new(10.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-contender", RunTags: []byte(`{}`), RunReason: new("pull request"),
		CommitID: contenderCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-dup",
		ResultTimestamp: ciReportTime(21), Unit: new("ns"), Data: []*float64{new(11.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-contender", RunTags: []byte(`{}`), RunReason: new("pull request"),
		CommitID: contenderCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-error",
		ResultTimestamp: ciReportTime(22), Unit: new("ns"), Data: []*float64{new(12.0)},
		Error: []byte(`{"message":"boom"}`),
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-baseline", RunTags: []byte(`{}`), RunReason: new("commit"),
		CommitID: baselineOlderCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-dup",
		ResultTimestamp: ciReportTime(30), Unit: new("ns"), Data: []*float64{new(9.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-baseline", RunTags: []byte(`{}`), RunReason: new("commit"),
		CommitID: baselineNewerCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-dup",
		ResultTimestamp: ciReportTime(31), Unit: new("ns"), Data: []*float64{new(8.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-baseline", RunTags: []byte(`{}`), RunReason: new("commit"),
		CommitID: baselineNewerCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-error",
		ResultTimestamp: ciReportTime(32), Unit: new("ns"), Data: []*float64{new(7.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-baseline", RunTags: []byte(`{}`), RunReason: new("commit"),
		CommitID: baselineNewerCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-baseline-only",
		ResultTimestamp: ciReportTime(33), Unit: new("ns"), Data: []*float64{new(6.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-contender", RunTags: []byte(`{}`), RunReason: new("pull request"),
		CommitID: otherCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-contaminant",
		ResultTimestamp: ciReportTime(40), Unit: new("ns"), Data: []*float64{new(99.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-baseline", RunTags: []byte(`{}`), RunReason: new("commit"),
		CommitID: otherCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-dup",
		ResultTimestamp: ciReportTime(41), Unit: new("ns"), Data: []*float64{new(100.0)},
	})

	rows, err := st.SelectCIReportRows(ctx,
		[]storage.CIReportRunKey{{RunID: "run-contender", CommitID: contenderCommitID}},
		[]storage.CIReportRunKey{{RunID: "run-baseline", CommitID: baselineNewerCommitID}},
	)

	require.NoError(t, err)
	require.Len(t, rows, 5, "all contender rows plus one deterministic baseline per run/fingerprint")
	byRun := ciReportRowsByRun(rows)
	require.Len(t, byRun["run-contender"], 3, "contender duplicate fingerprints are preserved")
	require.Len(t, byRun["run-baseline"], 2, "baseline rows are scoped to contender fingerprints and collapse duplicates")
	assert.Empty(t, ciReportRowsForFingerprint(byRun["run-baseline"], "fp-baseline-only"),
		"baseline-only fingerprints are not fetched for the report")

	baselineDup := ciReportOnlyRowForFingerprint(t, byRun["run-baseline"], "fp-dup")
	require.NotNil(t, baselineDup.CommitSha)
	assert.Equal(t, "base-new", *baselineDup.CommitSha, "baseline duplicate choice prefers newest commit timestamp")
	require.Len(t, baselineDup.Data, 1)
	require.NotNil(t, baselineDup.Data[0])
	assert.InDelta(t, 8.0, *baselineDup.Data[0], 1e-9)

	contenderError := ciReportOnlyRowForFingerprint(t, byRun["run-contender"], "fp-error")
	assert.JSONEq(t, `{"suite":"ci-report"}`, string(contenderError.CaseTags))
	assert.JSONEq(t, `{"compiler":"clang"}`, string(contenderError.ContextTags))
	assert.JSONEq(t, `{"variant":"nightly"}`, string(contenderError.InfoTags))
	assert.Equal(t, seed.HardwareID, contenderError.HardwareID)
	assert.Equal(t, "machine", contenderError.HardwareType)
	assert.Equal(t, "ci-runner", contenderError.HardwareName)
	assert.Equal(t, "machinehash-ci-runner", contenderError.HardwareHash)
	assert.Equal(t, "benchmark-ci-report", contenderError.CaseName)
	require.NotNil(t, contenderError.Unit)
	assert.Equal(t, "ns", *contenderError.Unit)
	assert.JSONEq(t, `{"message":"boom"}`, string(contenderError.Error))
	require.NotNil(t, contenderError.CommitSha)
	assert.Equal(t, "contender", *contenderError.CommitSha)
}

func newCIReportSeed(t *testing.T, st *db.Store, ctx context.Context) ciReportSeed {
	t.Helper()
	caseID, err := st.GetOrCreateCase(ctx, "benchmark-ci-report", []byte(`{"suite":"ci-report"}`))
	mustID(t, caseID, err)
	contextID, err := st.GetOrCreateContext(ctx, []byte(`{"compiler":"clang"}`))
	mustID(t, contextID, err)
	infoID, err := st.GetOrCreateInfo(ctx, []byte(`{"variant":"nightly"}`))
	mustID(t, infoID, err)
	hardwareID, err := st.GetOrCreateHardware(ctx, machineParams("ci-runner"))
	mustID(t, hardwareID, err)
	return ciReportSeed{CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hardwareID}
}

func insertCIReportCommit(
	t *testing.T,
	st *db.Store,
	ctx context.Context,
	repository string,
	sha string,
	parent string,
	forkPoint string,
	timestamp *time.Time,
	message string,
) string {
	t.Helper()
	params := storage.InsertCommitParams{
		Sha: sha, Repository: repository, Message: message, AuthorName: "CI",
		Timestamp: timestamp,
	}
	if parent != "" {
		params.Parent = new(parent)
	}
	if forkPoint != "" {
		params.ForkPointSha = new(forkPoint)
	}
	id, err := st.GetOrCreateCommit(ctx, params)
	mustID(t, id, err)
	return id
}

func insertCIReportResult(t *testing.T, st *db.Store, ctx context.Context, seed ciReportSeed, row ciResultSeed) string {
	t.Helper()
	var commitID *string
	if row.CommitID != "" {
		commitID = new(row.CommitID)
	}
	id, err := st.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
		CaseID: seed.CaseID, ContextID: seed.ContextID, InfoID: seed.InfoID, HardwareID: seed.HardwareID,
		RunID: row.RunID, RunTags: row.RunTags, RunReason: row.RunReason, CommitID: commitID,
		CommitRepoUrl: row.CommitRepoURL, HistoryFingerprint: row.HistoryFingerprint,
		Timestamp: row.ResultTimestamp, Unit: row.Unit, Data: row.Data, Error: row.Error,
	})
	mustID(t, id, err)
	return id
}

func ciReportTime(day int) time.Time {
	return time.Date(2026, 6, day, 12, 0, 0, 0, time.UTC)
}

func ciReportRunsByID(rows []storage.CIReportRunRow) map[string]storage.CIReportRunRow {
	out := make(map[string]storage.CIReportRunRow, len(rows))
	for _, row := range rows {
		out[row.RunID] = row
	}
	return out
}

func ciReportRunIDs(rows []storage.CIReportRunRow) []string {
	out := make([]string, 0, len(rows))
	for _, row := range rows {
		out = append(out, row.RunID)
	}
	return out
}

func ciReportCommitShas(rows []storage.CIReportCommitRow) []string {
	out := make([]string, 0, len(rows))
	for _, row := range rows {
		out = append(out, row.CommitSha)
	}
	return out
}

func ciReportRowsByRun(rows []storage.CIReportResultRow) map[string][]storage.CIReportResultRow {
	out := map[string][]storage.CIReportResultRow{}
	for _, row := range rows {
		out[row.RunID] = append(out[row.RunID], row)
	}
	return out
}

func ciReportRowsForFingerprint(
	rows []storage.CIReportResultRow,
	fingerprint string,
) []storage.CIReportResultRow {
	var matches []storage.CIReportResultRow
	for _, row := range rows {
		if row.HistoryFingerprint == fingerprint {
			matches = append(matches, row)
		}
	}
	return matches
}

func ciReportOnlyRowForFingerprint(
	t *testing.T,
	rows []storage.CIReportResultRow,
	fingerprint string,
) storage.CIReportResultRow {
	t.Helper()
	var matches []storage.CIReportResultRow
	for _, row := range rows {
		if row.HistoryFingerprint == fingerprint {
			matches = append(matches, row)
		}
	}
	require.Len(t, matches, 1, "expected exactly one row for fingerprint %s", fingerprint)
	return matches[0]
}
