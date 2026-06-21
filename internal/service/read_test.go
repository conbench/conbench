package service_test

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/service"
)

// offBranchProvider resolves commits whose fork point differs from the sha, i.e.
// results that are NOT on the default branch and must be excluded from history.
type offBranchProvider struct{ forkPoint string }

func (p offBranchProvider) Resolve(_ context.Context, req commit.Request) (*commit.Info, error) {
	if req.Commit == "" {
		return nil, nil
	}
	fp := p.forkPoint
	ts := req.ResultTimestamp
	return &commit.Info{
		Sha:          req.Commit,
		Repository:   commit.NormalizeRepoURL(req.Repository),
		ForkPointSha: &fp,
		Timestamp:    &ts,
	}, nil
}

// withCommit returns a copy of a machine request with a specific commit sha.
func withCommit(sha string) service.SubmitRequest {
	r := machineReq(samples(1, 2, 3), "s")
	r.GitHub.Commit = sha
	return r
}

func TestResultDetail(t *testing.T) {
	ing, store, _, ctx := newIngester(t)
	reader := service.NewReader(store)

	res, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
	require.NoError(t, err)

	d, err := reader.ResultDetail(ctx, res.ID)
	require.NoError(t, err)
	assert.Equal(t, res.ID, d.ID)
	assert.Equal(t, "bench", d.Tags["name"])
	assert.Equal(t, "test", d.Tags["source"])
	assert.Equal(t, "gcc", d.Context["compiler"])
	assert.Equal(t, machineHash(), d.Hardware.Hash)
	assert.Equal(t, "machine", d.Hardware.Type)
	if assert.NotNil(t, d.Commit) {
		assert.Equal(t, "abc123", d.Commit.Sha)
		assert.Equal(t, testRepo, d.Commit.Repository)
	}
	if assert.NotNil(t, d.Unit) {
		assert.Equal(t, "s", *d.Unit)
	}
	assert.Len(t, d.Data, 3)
	if assert.NotNil(t, d.Stats.Mean) {
		assert.InDelta(t, 2.0, *d.Stats.Mean, 1e-9)
	}
	// "s" is less-is-better, so the best single value is the minimum.
	if assert.NotNil(t, d.SVS) {
		assert.InDelta(t, 1.0, *d.SVS, 1e-9)
		assert.Equal(t, "min", d.SVSType)
	}
}

func TestResultDetailNotFound(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	reader := service.NewReader(store)

	_, err := reader.ResultDetail(ctx, "0000000000000000000000000000dead")
	require.ErrorIs(t, err, service.ErrNotFound)
}

// TestResultDetailErroredUnknownUnit reads back an errored result whose raw,
// unvalidated unit is not recognized. Reading must not 500 on the unit-direction
// lookup: the single value summary is null and its type falls back to "n/a".
func TestResultDetailErroredUnknownUnit(t *testing.T) {
	ing, store, _, ctx := newIngester(t)
	reader := service.NewReader(store)

	// A null sample makes this a partial (errored) result; errored results keep
	// the unit raw, so an unrecognized unit reaches the read path.
	res, err := ing.Submit(ctx, machineReq([]*float64{new(1.0), nil, new(3.0)}, "bananas-per-second"))
	require.NoError(t, err)

	d, err := reader.ResultDetail(ctx, res.ID)
	require.NoError(t, err)
	assert.Nil(t, d.SVS)
	assert.Equal(t, "n/a", d.SVSType)
	assert.NotNil(t, d.Error)
}

// TestHistoryMembership submits five results sharing one fingerprint and asserts
// that only the two non-errored, commit-joined, default-branch results appear:
// the partial (error), the commitless, and the off-branch results are excluded.
func TestHistoryMembership(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	local := service.NewIngester(store, commit.LocalProvider{})
	offBranch := service.NewIngester(store, offBranchProvider{forkPoint: "different-fork-point"})
	reader := service.NewReader(store)

	// Two included default-branch results.
	a, err := local.Submit(ctx, withCommit("sha-a"))
	require.NoError(t, err)
	b, err := local.Submit(ctx, withCommit("sha-b"))
	require.NoError(t, err)
	fp := a.HistoryFingerprint
	require.Equal(t, fp, b.HistoryFingerprint, "fingerprints differ for same case/context/hw/repo")

	// Excluded: error IS NOT NULL (partial data).
	partial := machineReq([]*float64{new(1.0), nil, new(3.0)}, "s")
	partial.GitHub.Commit = "sha-c"
	_, err = local.Submit(ctx, partial)
	require.NoError(t, err)
	// Excluded: no commit.
	noCommit := withCommit("")
	_, err = local.Submit(ctx, noCommit)
	require.NoError(t, err)
	// Excluded: sha != fork_point_sha (off the default branch).
	_, err = offBranch.Submit(ctx, withCommit("sha-e"))
	require.NoError(t, err)

	series, err := reader.History(ctx, fp)
	require.NoError(t, err)
	assert.Equal(t, fp, series.HistoryFingerprint)
	require.Len(t, series.Samples, 2, "history must exclude error/no-commit/off-branch")
	got := map[string]bool{series.Samples[0].BenchmarkResultID: true, series.Samples[1].BenchmarkResultID: true}
	assert.True(t, got[a.ID] && got[b.ID], "history samples = %v, want %s and %s", got, a.ID, b.ID)
}

func TestHistorySVS(t *testing.T) {
	ing, store, _, ctx := newIngester(t)
	reader := service.NewReader(store)

	a, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
	require.NoError(t, err)

	series, err := reader.History(ctx, a.HistoryFingerprint)
	require.NoError(t, err)
	require.Len(t, series.Samples, 1)
	s := series.Samples[0]
	// "s" is less-is-better: svs is the minimum of the samples.
	assert.InDelta(t, 1.0, s.SVS, 1e-9)
	assert.Equal(t, "min", s.SVSType)
	if assert.NotNil(t, s.Mean) {
		assert.InDelta(t, 2.0, *s.Mean, 1e-9)
	}
}

func TestHistoryForResult(t *testing.T) {
	ing, store, _, ctx := newIngester(t)
	reader := service.NewReader(store)

	res, err := ing.Submit(ctx, machineReq(samples(1, 2, 3), "s"))
	require.NoError(t, err)

	series, err := reader.HistoryForResult(ctx, res.ID)
	require.NoError(t, err)
	assert.Equal(t, res.HistoryFingerprint, series.HistoryFingerprint)
	assert.Len(t, series.Samples, 1)

	_, err = reader.HistoryForResult(ctx, "0000000000000000000000000000dead")
	assert.ErrorIs(t, err, service.ErrNotFound)
}
