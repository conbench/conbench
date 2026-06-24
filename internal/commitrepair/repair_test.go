package commitrepair

import (
	"context"
	"encoding/base64"
	"errors"
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/storage"
)

func TestCursorRoundTrip(t *testing.T) {
	want := Cursor{Repository: "https://github.com/org/repo", Sha: "abc123"}

	encoded, err := EncodeCursor(want)
	require.NoError(t, err)

	got, err := DecodeCursor(encoded)
	require.NoError(t, err)
	assert.Equal(t, want, got)
}

func TestMalformedCursorReturnsError(t *testing.T) {
	_, err := DecodeCursor("not valid base64!")

	require.Error(t, err)
}

func TestEmptyCursorFieldsRejected(t *testing.T) {
	_, err := EncodeCursor(Cursor{Repository: "", Sha: "abc123"})
	require.Error(t, err)

	_, err = EncodeCursor(Cursor{Repository: "https://github.com/org/repo", Sha: ""})
	require.Error(t, err)

	encoded := base64.RawURLEncoding.EncodeToString([]byte(`{"repository":"","sha":"abc123"}`))
	_, err = DecodeCursor(encoded)
	require.Error(t, err)

	encoded = base64.RawURLEncoding.EncodeToString([]byte(`{"repository":"https://github.com/org/repo","sha":""}`))
	_, err = DecodeCursor(encoded)
	require.Error(t, err)
}

func TestCursorRepositoryMismatchWithFilterReturnsError(t *testing.T) {
	repo := "https://github.com/other/repo"
	cursor := Cursor{Repository: "https://github.com/org/repo", Sha: "abc123"}
	r := NewRepairer(&fakeStore{}, &fakeEnricher{}, &fakeBackfiller{})

	_, err := r.Run(context.Background(), Options{Repository: &repo, Limit: 1, Cursor: &cursor})

	require.Error(t, err)
}

func TestRunInvalidLimitReturnsError(t *testing.T) {
	r := NewRepairer(&fakeStore{}, &fakeEnricher{}, nil)

	_, err := r.Run(context.Background(), Options{Limit: 0})

	require.Error(t, err)
}

func TestRunNilStoreReturnsConfigurationError(t *testing.T) {
	r := NewRepairer(nil, &fakeEnricher{}, nil)

	_, err := r.Run(context.Background(), Options{Limit: 1})

	require.Error(t, err)
}

func TestRunNilEnricherReturnsConfigurationError(t *testing.T) {
	r := NewRepairer(&fakeStore{}, nil, nil)

	_, err := r.Run(context.Background(), Options{Limit: 1})

	require.Error(t, err)
}

func TestRunStoreSelectErrorReturnsError(t *testing.T) {
	wantErr := errors.New("select failed")
	store := &fakeStore{selectErr: wantErr}
	r := NewRepairer(store, &fakeEnricher{}, nil)

	_, err := r.Run(context.Background(), Options{Limit: 1})

	require.ErrorIs(t, err, wantErr)
}

func TestRunDryRunEnrichesWithoutUpdatingOrBackfilling(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	store := &fakeStore{candidates: []storage.UnknownCommitCandidate{
		candidate("id-1", "https://github.com/org/repo", "abc123"),
	}}
	enricher := &fakeEnricher{infos: map[string]*commit.Info{
		"abc123": commitInfo("https://github.com/org/repo", "abc123", ts, "fork"),
	}}
	backfiller := &fakeBackfiller{}
	r := NewRepairer(store, enricher, backfiller)

	summary, err := r.Run(context.Background(), Options{Limit: 10, DryRun: true, Backfill: true})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.Scanned)
	assert.Equal(t, 1, summary.WouldRepair)
	assert.Len(t, enricher.requests, 1)
	assert.Empty(t, store.updates)
	assert.Empty(t, backfiller.jobs)
}

func TestRunUnsupportedRepositoryIncrementsUnsupportedRepository(t *testing.T) {
	store := &fakeStore{candidates: []storage.UnknownCommitCandidate{
		candidate("id-1", "https://gitlab.com/org/repo", "abc123"),
	}}
	enricher := &fakeEnricher{errs: map[string]error{
		"abc123": commit.ErrUnsupportedRepository,
	}}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 10})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.UnsupportedRepository)
	assert.Equal(t, 0, summary.Failed)
	assert.Empty(t, summary.Failures)
}

func TestRunContextCanceledBeforeSelectReturnsError(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	store := &fakeStore{candidates: []storage.UnknownCommitCandidate{
		candidate("id-1", "https://github.com/org/repo", "abc123"),
	}}
	r := NewRepairer(store, &fakeEnricher{}, nil)

	_, err := r.Run(ctx, Options{Limit: 10})

	require.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, 0, store.selects)
}

func TestRunEnrichContextCancellationReturnsTopLevelError(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	store := &fakeStore{candidates: []storage.UnknownCommitCandidate{
		candidate("id-1", "https://github.com/org/repo", "abc123"),
	}}
	enricher := &fakeEnricher{errs: map[string]error{
		"abc123": context.Canceled,
	}}
	enricher.beforeErr = cancel
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(ctx, Options{Limit: 10})

	require.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, 0, summary.Failed)
	assert.Empty(t, summary.Failures)
	assert.Empty(t, store.updates)
}

func TestRunEnrichContextDeadlineReturnsTopLevelError(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	store := &fakeStore{candidates: []storage.UnknownCommitCandidate{
		candidate("id-1", "https://github.com/org/repo", "abc123"),
	}}
	enricher := &fakeEnricher{errs: map[string]error{
		"abc123": context.DeadlineExceeded,
	}}
	enricher.beforeErr = cancel
	r := NewRepairer(store, enricher, nil)

	_, err := r.Run(ctx, Options{Limit: 10})

	require.ErrorIs(t, err, context.Canceled)
}

func TestRunPerRequestDeadlineRecordsFailureWhenParentContextIsLive(t *testing.T) {
	store := &fakeStore{candidates: []storage.UnknownCommitCandidate{
		candidate("id-1", "https://github.com/org/repo", "abc123"),
	}}
	enricher := &fakeEnricher{errs: map[string]error{
		"abc123": context.DeadlineExceeded,
	}}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 10})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.Failed)
	require.Len(t, summary.Failures, 1)
	assert.Equal(t, "abc123", summary.Failures[0].Sha)
	assert.Empty(t, store.updates)
}

func TestRunEnrichmentFailureIncrementsFailedAndBoundsFailureSamples(t *testing.T) {
	candidates := make([]storage.UnknownCommitCandidate, 0, 11)
	errs := make(map[string]error, 11)
	for i := range 11 {
		sha := fmt.Sprintf("sha-%02d", i)
		candidates = append(candidates, candidate(fmt.Sprintf("id-%02d", i), "https://github.com/org/repo", sha))
		errs[sha] = fmt.Errorf("boom %02d", i)
	}
	store := &fakeStore{candidates: candidates}
	enricher := &fakeEnricher{errs: errs}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 11})

	require.NoError(t, err)
	assert.Equal(t, 11, summary.Failed)
	require.Len(t, summary.Failures, 10)
	assert.Equal(t, "sha-00", summary.Failures[0].Sha)
	assert.Equal(t, "sha-09", summary.Failures[9].Sha)
}

func TestRunTracksAuthOrQuotaFailuresBeyondFailureSamples(t *testing.T) {
	candidates := make([]storage.UnknownCommitCandidate, 0, 11)
	errs := make(map[string]error, 11)
	for i := range 11 {
		sha := fmt.Sprintf("sha-%02d", i)
		candidates = append(candidates, candidate(fmt.Sprintf("id-%02d", i), "https://github.com/org/repo", sha))
		errs[sha] = errors.New("fetch commit metadata: unexpected github response 401: bad credentials")
	}
	store := &fakeStore{candidates: candidates}
	enricher := &fakeEnricher{errs: errs}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 11})

	require.NoError(t, err)
	assert.Equal(t, 11, summary.Failed)
	assert.Equal(t, 11, summary.AuthOrQuotaFailures)
	require.Len(t, summary.Failures, 10)
}

func TestRunMissingForkPointFailsWithoutUpdating(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	info := commitInfo("https://github.com/org/repo", "abc123", ts, "fork")
	info.ForkPointSha = nil
	store := &fakeStore{candidates: []storage.UnknownCommitCandidate{
		candidate("id-1", "https://github.com/org/repo", "abc123"),
	}}
	enricher := &fakeEnricher{infos: map[string]*commit.Info{"abc123": info}}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 10})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.Failed)
	assert.Empty(t, store.updates)
	require.Len(t, summary.Failures, 1)
	assert.Equal(t, "abc123", summary.Failures[0].Sha)
}

func TestRunSuccessfulUpdateIncrementsRepaired(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	store := &fakeStore{
		candidates: []storage.UnknownCommitCandidate{candidate("id-1", "https://github.com/org/repo", "abc123")},
		updateRows: []int64{1},
	}
	enricher := &fakeEnricher{infos: map[string]*commit.Info{
		"abc123": commitInfo("https://github.com/org/repo", "abc123", ts, "fork"),
	}}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 10})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.Repaired)
	require.Len(t, store.updates, 1)
	assert.Equal(t, "id-1", store.updates[0].ID)
	assert.Equal(t, ts, store.updates[0].Timestamp)
}

func TestRunUpdateRowsAffectedZeroIncrementsAlreadyRepaired(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	store := &fakeStore{
		candidates: []storage.UnknownCommitCandidate{candidate("id-1", "https://github.com/org/repo", "abc123")},
		updateRows: []int64{0},
	}
	enricher := &fakeEnricher{infos: map[string]*commit.Info{
		"abc123": commitInfo("https://github.com/org/repo", "abc123", ts, "fork"),
	}}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 10})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.AlreadyRepaired)
	assert.Equal(t, 0, summary.Repaired)
}

func TestRunStoreUpdateErrorReturnsError(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	wantErr := errors.New("update failed")
	store := &fakeStore{
		candidates: []storage.UnknownCommitCandidate{candidate("id-1", "https://github.com/org/repo", "abc123")},
		updateErr:  wantErr,
	}
	enricher := &fakeEnricher{infos: map[string]*commit.Info{
		"abc123": commitInfo("https://github.com/org/repo", "abc123", ts, "fork"),
	}}
	r := NewRepairer(store, enricher, nil)

	_, err := r.Run(context.Background(), Options{Limit: 10})

	require.ErrorIs(t, err, wantErr)
}

func TestRunDefaultBranchRepairWithoutBackfillIncrementsWouldBackfill(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	store := &fakeStore{
		candidates: []storage.UnknownCommitCandidate{candidate("id-1", "https://github.com/org/repo", "abc123")},
		updateRows: []int64{1},
	}
	enricher := &fakeEnricher{
		infos: map[string]*commit.Info{
			"abc123": commitInfo("https://github.com/org/repo", "abc123", ts, "abc123"),
		},
		jobs: map[string]*commit.BackfillJob{
			"abc123": backfillJob("https://github.com/org/repo", ts),
		},
	}
	backfiller := &fakeBackfiller{}
	r := NewRepairer(store, enricher, backfiller)

	summary, err := r.Run(context.Background(), Options{Limit: 10})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.Repaired)
	assert.Equal(t, 1, summary.WouldBackfill)
	assert.Empty(t, backfiller.jobs)
}

func TestRunDefaultBranchRepairWithBackfillEnqueues(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	store := &fakeStore{
		candidates: []storage.UnknownCommitCandidate{candidate("id-1", "https://github.com/org/repo", "abc123")},
		updateRows: []int64{1},
	}
	job := backfillJob("https://github.com/org/repo", ts)
	enricher := &fakeEnricher{
		infos: map[string]*commit.Info{
			"abc123": commitInfo("https://github.com/org/repo", "abc123", ts, "abc123"),
		},
		jobs: map[string]*commit.BackfillJob{"abc123": job},
	}
	backfiller := &fakeBackfiller{}
	r := NewRepairer(store, enricher, backfiller)

	summary, err := r.Run(context.Background(), Options{Limit: 10, Backfill: true})

	require.NoError(t, err)
	assert.Equal(t, 1, summary.BackfillEnqueued)
	require.Len(t, backfiller.jobs, 1)
	assert.Equal(t, *job, backfiller.jobs[0])
}

func TestRunLimitPlusOneSetsNextCursorAndDoesNotInspectExtraRow(t *testing.T) {
	ts := time.Date(2026, 6, 17, 12, 0, 0, 0, time.UTC)
	store := &fakeStore{
		candidates: []storage.UnknownCommitCandidate{
			candidate("id-1", "https://github.com/org/repo", "sha-1"),
			candidate("id-2", "https://github.com/org/repo", "sha-2"),
			candidate("id-3", "https://github.com/org/repo", "sha-3"),
		},
		updateRows: []int64{1, 1},
	}
	enricher := &fakeEnricher{infos: map[string]*commit.Info{
		"sha-1": commitInfo("https://github.com/org/repo", "sha-1", ts, "fork-1"),
		"sha-2": commitInfo("https://github.com/org/repo", "sha-2", ts, "fork-2"),
	}}
	r := NewRepairer(store, enricher, nil)

	summary, err := r.Run(context.Background(), Options{Limit: 2})

	require.NoError(t, err)
	require.NotNil(t, summary.NextCursor)
	cursor, err := DecodeCursor(*summary.NextCursor)
	require.NoError(t, err)
	assert.Equal(t, Cursor{Repository: "https://github.com/org/repo", Sha: "sha-2"}, cursor)
	assert.Equal(t, int32(3), store.params.LimitPlusOne)
	assert.Equal(t, []string{"sha-1", "sha-2"}, enricher.seenShas())
	assert.Equal(t, 2, summary.Scanned)
}

type fakeStore struct {
	candidates []storage.UnknownCommitCandidate
	params     storage.UnknownCommitCandidateParams
	updates    []storage.UpdateUnknownCommitParams
	updateRows []int64
	selectErr  error
	updateErr  error
	selects    int
}

func (s *fakeStore) SelectUnknownCommitRepairCandidates(
	_ context.Context,
	p storage.UnknownCommitCandidateParams,
) ([]storage.UnknownCommitCandidate, error) {
	s.selects++
	s.params = p
	if s.selectErr != nil {
		return nil, s.selectErr
	}
	return s.candidates, nil
}

func (s *fakeStore) UpdateUnknownCommit(_ context.Context, p storage.UpdateUnknownCommitParams) (int64, error) {
	s.updates = append(s.updates, p)
	if s.updateErr != nil {
		return 0, s.updateErr
	}
	if len(s.updateRows) == 0 {
		return 1, nil
	}
	rows := s.updateRows[0]
	s.updateRows = s.updateRows[1:]
	return rows, nil
}

type fakeEnricher struct {
	infos     map[string]*commit.Info
	jobs      map[string]*commit.BackfillJob
	errs      map[string]error
	requests  []commit.Request
	beforeErr func()
}

func (e *fakeEnricher) Enrich(_ context.Context, req commit.Request) (*commit.Info, *commit.BackfillJob, error) {
	e.requests = append(e.requests, req)
	if err := e.errs[req.Commit]; err != nil {
		if e.beforeErr != nil {
			e.beforeErr()
		}
		return nil, nil, err
	}
	return e.infos[req.Commit], e.jobs[req.Commit], nil
}

func (e *fakeEnricher) seenShas() []string {
	shas := make([]string, 0, len(e.requests))
	for _, req := range e.requests {
		shas = append(shas, req.Commit)
	}
	return shas
}

type fakeBackfiller struct {
	jobs []commit.BackfillJob
}

func (b *fakeBackfiller) Enqueue(job commit.BackfillJob) {
	b.jobs = append(b.jobs, job)
}

func candidate(id, repo, sha string) storage.UnknownCommitCandidate {
	return storage.UnknownCommitCandidate{ID: id, Repository: repo, Sha: sha}
}

func commitInfo(repo, sha string, ts time.Time, forkPoint string) *commit.Info {
	parent := "parent"
	branch := "org:main"
	login := "octocat"
	avatar := "https://example.com/avatar.png"
	return &commit.Info{
		Sha:          sha,
		Repository:   repo,
		Parent:       &parent,
		Message:      "message",
		AuthorName:   "Author",
		AuthorLogin:  &login,
		AuthorAvatar: &avatar,
		Timestamp:    &ts,
		Branch:       &branch,
		ForkPointSha: &forkPoint,
	}
}

func backfillJob(repo string, until time.Time) *commit.BackfillJob {
	return &commit.BackfillJob{
		RepoURL:       repo,
		Spec:          "org/repo",
		DefaultBranch: "org:main",
		Until:         until,
	}
}

var _ Store = (*fakeStore)(nil)
var _ Enricher = (*fakeEnricher)(nil)
var _ BackfillEnqueuer = (*fakeBackfiller)(nil)
