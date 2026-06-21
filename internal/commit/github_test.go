package commit_test

import (
	"context"
	"net/http"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/commit/githubtest"
)

var _ commit.Provider = (*commit.GitHubProvider)(nil)

const childSha = "02addad336ba19a654f9c857ede546331be7b631"

// enqueueRecorder captures backfill enqueues.
type enqueueRecorder struct{ jobs []commit.BackfillJob }

func (r *enqueueRecorder) Enqueue(j commit.BackfillJob) { r.jobs = append(r.jobs, j) }

func newProvider(t *testing.T, srv *githubtest.Server, rec commit.BackfillEnqueuer) *commit.GitHubProvider {
	t.Helper()
	return commit.NewGitHubProvider(commit.NewGitHubClient("", srv.URL), 5*time.Second, rec)
}

// fakeRepo wires the happy-path endpoints: commit metadata, repo (default
// branch org:main), and a compare result whose merge base is the sha itself
// (i.e. the commit is on the default branch).
func fakeRepo(t *testing.T, srv *githubtest.Server) {
	t.Helper()
	srv.HandleJSON("/repos/org/repo/commits/"+childSha, githubtest.Fixture(t, "github_child.json"))
	srv.HandleJSON("/repos/org/repo", []byte(`{"fork":false,"owner":{"login":"org"},"default_branch":"main"}`))
	srv.HandleJSON("/repos/org/repo/compare/org:main..."+childSha,
		[]byte(`{"merge_base_commit":{"sha":"`+childSha+`"}}`))
}

func TestGitHubProviderEnrichesDefaultBranchCommit(t *testing.T) {
	srv := githubtest.NewServer(t)
	fakeRepo(t, srv)
	rec := &enqueueRecorder{}
	p := newProvider(t, srv, rec)

	info, err := p.Resolve(context.Background(), commit.Request{
		Commit: childSha, Repository: "https://github.com/org/repo/",
	})
	require.NoError(t, err)
	require.NotNil(t, info)
	assert.Equal(t, childSha, info.Sha)
	assert.Equal(t, "https://github.com/org/repo", info.Repository, "normalized")
	assert.Equal(t, "Diana Clarke", info.AuthorName)
	require.NotNil(t, info.Branch)
	assert.Equal(t, "org:main", *info.Branch)
	require.NotNil(t, info.ForkPointSha)
	assert.Equal(t, childSha, *info.ForkPointSha)
	require.NotNil(t, info.Timestamp)
	assert.True(t, info.Timestamp.Equal(time.Date(2021, 2, 25, 1, 2, 51, 0, time.UTC)))

	// Default-branch commit with a timestamp: backfill enqueued.
	require.Len(t, rec.jobs, 1)
	assert.Equal(t, "https://github.com/org/repo", rec.jobs[0].RepoURL)
	assert.Equal(t, "org/repo", rec.jobs[0].Spec)
	assert.Equal(t, "org:main", rec.jobs[0].DefaultBranch)
	assert.True(t, rec.jobs[0].Until.Equal(*info.Timestamp))
}

func TestGitHubProviderEnrichReturnsBackfillJobWithoutCountingUnknown(t *testing.T) {
	srv := githubtest.NewServer(t)
	fakeRepo(t, srv)
	p := newProvider(t, srv, nil)

	info, job, err := p.Enrich(context.Background(), commit.Request{
		Commit: childSha, Repository: "https://github.com/org/repo/",
	})
	require.NoError(t, err)
	require.NotNil(t, info)
	require.NotNil(t, job)
	assert.Equal(t, childSha, info.Sha)
	assert.Equal(t, "https://github.com/org/repo", info.Repository)
	assert.Equal(t, "org/repo", job.Spec)
	assert.Equal(t, int64(0), p.UnknownCommitCount())
}

func TestGitHubProviderEnrichUnsupportedRepositoryIsTyped(t *testing.T) {
	srv := githubtest.NewServer(t)
	p := newProvider(t, srv, nil)

	info, job, err := p.Enrich(context.Background(), commit.Request{
		Commit: "abc", Repository: "https://gitlab.com/org/repo",
	})
	require.ErrorIs(t, err, commit.ErrUnsupportedRepository)
	assert.Nil(t, info)
	assert.Nil(t, job)
	assert.Empty(t, srv.Requests())
	assert.Equal(t, int64(0), p.UnknownCommitCount(), "Enrich does not degrade/count")
}

func TestGitHubProviderExplicitBranchSkipsPRLookup(t *testing.T) {
	srv := githubtest.NewServer(t)
	fakeRepo(t, srv)
	rec := &enqueueRecorder{}
	p := newProvider(t, srv, rec)

	pr := 7
	info, err := p.Resolve(context.Background(), commit.Request{
		Commit: childSha, Repository: "https://github.com/org/repo",
		Branch: "org:feature", PRNumber: &pr,
	})
	require.NoError(t, err)
	require.NotNil(t, info.Branch)
	assert.Equal(t, "org:feature", *info.Branch, "explicit branch beats pr_number")
	for _, r := range srv.Requests() {
		assert.NotContains(t, r, "/pulls/", "explicit branch must not trigger a PR lookup")
	}
	// merge base == sha here, so this still looks like a default-branch
	// commit and enqueues; the branch label alone does not gate backfill.
	assert.Len(t, rec.jobs, 1)
}

func TestGitHubProviderPRNumberResolvesBranch(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo/commits/"+childSha, githubtest.Fixture(t, "github_child.json"))
	srv.HandleJSON("/repos/org/repo", []byte(`{"fork":false,"owner":{"login":"org"},"default_branch":"main"}`))
	srv.HandleJSON("/repos/org/repo/pulls/7", []byte(`{"head":{"label":"someuser:feature"}}`))
	srv.HandleJSON("/repos/org/repo/compare/org:main..."+childSha,
		[]byte(`{"merge_base_commit":{"sha":"otherforkpoint"}}`))
	rec := &enqueueRecorder{}
	p := newProvider(t, srv, rec)

	pr := 7
	info, err := p.Resolve(context.Background(), commit.Request{
		Commit: childSha, Repository: "https://github.com/org/repo", PRNumber: &pr,
	})
	require.NoError(t, err)
	require.NotNil(t, info.Branch)
	assert.Equal(t, "someuser:feature", *info.Branch)
	require.NotNil(t, info.ForkPointSha)
	assert.Equal(t, "otherforkpoint", *info.ForkPointSha)
	assert.Empty(t, rec.jobs, "non-default-branch commit must not enqueue backfill")
}

func TestGitHubProviderDegradesToUnknownOnAPIError(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleStatus("/repos/org/repo/commits/"+childSha, http.StatusNotFound)
	rec := &enqueueRecorder{}
	p := newProvider(t, srv, rec)

	info, err := p.Resolve(context.Background(), commit.Request{
		Commit: childSha, Repository: "https://github.com/org/repo",
	})
	require.NoError(t, err, "degradation must not surface an error; the result must persist")
	require.NotNil(t, info)
	assert.Equal(t, childSha, info.Sha)
	assert.Equal(t, "https://github.com/org/repo", info.Repository)
	assert.Empty(t, info.Message)
	assert.Empty(t, info.AuthorName)
	assert.Nil(t, info.Timestamp)
	assert.Nil(t, info.Branch)
	assert.Nil(t, info.ForkPointSha)
	assert.Nil(t, info.Parent)
	assert.Equal(t, int64(1), p.UnknownCommitCount())
	assert.Empty(t, rec.jobs, "unknown commits never enqueue backfill")
}

func TestGitHubProviderDegradesOnBranchResolutionError(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo/commits/"+childSha, githubtest.Fixture(t, "github_child.json"))
	srv.HandleStatus("/repos/org/repo", http.StatusNotFound) // default-branch lookup fails
	p := newProvider(t, srv, nil)

	info, err := p.Resolve(context.Background(), commit.Request{
		Commit: childSha, Repository: "https://github.com/org/repo",
	})
	require.NoError(t, err)
	assert.Nil(t, info.Timestamp, "degradation discards the partial metadata (legacy parity)")
	assert.Equal(t, int64(1), p.UnknownCommitCount())
}

func TestGitHubProviderNonGitHubRepoDegradesWithoutAPICall(t *testing.T) {
	srv := githubtest.NewServer(t)
	p := newProvider(t, srv, nil)

	// Lookalike URLs must not pass the host check: only the real
	// https://github.com/ prefix may trigger API calls.
	repos := []string{
		"https://gitlab.com/org/repo",
		"https://evil.example/github.com/org/repo",
		"https://foo.github.com/org/repo",
		"github.com/org/repo",
	}
	for _, repo := range repos {
		info, err := p.Resolve(context.Background(), commit.Request{
			Commit: "abc", Repository: repo,
		})
		require.NoError(t, err, "repo %q", repo)
		require.NotNil(t, info, "repo %q", repo)
		assert.Equal(t, repo, info.Repository, "repo %q", repo)
		assert.Empty(t, info.AuthorName, "repo %q", repo)
	}
	assert.Empty(t, srv.Requests(), "no GitHub API call for any non-GitHub URL")
	assert.Equal(t, int64(len(repos)), p.UnknownCommitCount())
}

func TestGitHubProviderBudgetDegrades(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.Mux.HandleFunc("/repos/org/repo/commits/"+childSha, func(w http.ResponseWriter, _ *http.Request) {
		time.Sleep(300 * time.Millisecond)
		_, _ = w.Write(githubtest.Fixture(t, "github_child.json"))
	})
	p := commit.NewGitHubProvider(commit.NewGitHubClient("", srv.URL), 50*time.Millisecond, nil)

	start := time.Now()
	info, err := p.Resolve(context.Background(), commit.Request{
		Commit: childSha, Repository: "https://github.com/org/repo",
	})
	require.NoError(t, err)
	assert.Nil(t, info.Timestamp, "budget blown -> unknown commit")
	assert.Less(t, time.Since(start), 250*time.Millisecond, "Resolve must respect the budget, not the handler sleep")
}

func TestGitHubProviderNoCommitYieldsNil(t *testing.T) {
	srv := githubtest.NewServer(t)
	p := newProvider(t, srv, nil)
	info, err := p.Resolve(context.Background(), commit.Request{Repository: "https://github.com/org/repo"})
	require.NoError(t, err)
	assert.Nil(t, info)
}

func TestHasUsableGitHubToken(t *testing.T) {
	assert.False(t, commit.HasUsableGitHubToken(""))
	assert.False(t, commit.HasUsableGitHubToken("x, bad"))
	assert.True(t, commit.HasUsableGitHubToken("abcde"))
	assert.Equal(t, "abcde", commit.FirstUsableGitHubToken("x, abcde, fghij"))
	assert.Empty(t, commit.FirstUsableGitHubToken("x, bad"))
}
