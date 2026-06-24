package commit_test

import (
	"context"
	"encoding/json"
	"net/http"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/commit/githubtest"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/storage"
)

const repoURL = "https://github.com/org/repo"

type blockingBackfillStore struct{}

func (blockingBackfillStore) LatestCommitTimestampOnBranch(
	ctx context.Context,
	_, _ string,
	_ time.Time,
) (*time.Time, error) {
	<-ctx.Done()
	return nil, ctx.Err()
}

func (blockingBackfillStore) GetOrCreateCommit(context.Context, storage.InsertCommitParams) (string, error) {
	return "", nil
}

// commitListJSON builds a GitHub commits-list response, newest first, from
// (sha, RFC3339 timestamp) pairs.
func commitListJSON(t *testing.T, items [][2]string) []byte {
	t.Helper()
	var objs []map[string]any
	for _, it := range items {
		objs = append(objs, map[string]any{
			"sha": it[0],
			"commit": map[string]any{
				"author":  map[string]any{"name": "dev", "date": it[1]},
				"message": "msg " + it[0],
			},
			"author":  nil,
			"parents": []any{},
		})
	}
	b, err := json.Marshal(objs)
	require.NoError(t, err)
	return b
}

func TestBackfillerShutdownReportsNoTimeoutWhenDrained(t *testing.T) {
	b := commit.NewBackfiller(commit.NewGitHubClient("", ""), blockingBackfillStore{})

	shutdownCtx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	timedOut := b.Shutdown(shutdownCtx)

	assert.False(t, timedOut)
}

func TestBackfillerShutdownReportsTimeoutBranch(t *testing.T) {
	b := commit.NewBackfiller(commit.NewGitHubClient("", ""), blockingBackfillStore{})
	b.Enqueue(commit.BackfillJob{
		RepoURL:       repoURL,
		Spec:          "org/repo",
		DefaultBranch: "org:main",
		Until:         time.Date(2021, 1, 4, 0, 0, 0, 0, time.UTC),
	})

	shutdownCtx, cancel := context.WithTimeout(context.Background(), time.Millisecond)
	defer cancel()
	timedOut := b.Shutdown(shutdownCtx)

	assert.True(t, timedOut)
}

func TestBackfillerInsertsWindowExclusiveBounds(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	// Last tracked default-branch commit at T1; the submitted commit is T4.
	branch := "org:main"
	_, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha: "tracked", Repository: repoURL, Branch: &branch,
		Timestamp: new(time.Date(2021, 1, 1, 0, 0, 0, 0, time.UTC)),
	})
	require.NoError(t, err)

	srv := githubtest.NewServer(t)
	srv.Mux.HandleFunc("/repos/org/repo/commits", func(w http.ResponseWriter, r *http.Request) {
		// GitHub returns the window newest-first, bounds inclusive.
		assert.Equal(t, "2021-01-01T00:00:00Z", r.URL.Query().Get("since"))
		assert.Equal(t, "2021-01-04T00:00:00Z", r.URL.Query().Get("until"))
		_, _ = w.Write(commitListJSON(t, [][2]string{
			{"submitted", "2021-01-04T00:00:00Z"},
			{"mid2", "2021-01-03T00:00:00Z"},
			{"mid1", "2021-01-02T00:00:00Z"},
			{"tracked", "2021-01-01T00:00:00Z"},
		}))
	})

	b := commit.NewBackfiller(commit.NewGitHubClient("", srv.URL), store)
	b.Enqueue(commit.BackfillJob{
		RepoURL: repoURL, Spec: "org/repo", DefaultBranch: branch,
		Until: time.Date(2021, 1, 4, 0, 0, 0, 0, time.UTC),
	})
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	b.Shutdown(shutdownCtx)

	// Exclusive bounds: mid1 and mid2 inserted; the bounds themselves were
	// dropped (legacy commits[1:-1]).
	for _, sha := range []string{"mid1", "mid2"} {
		id, err := store.GetCommitID(ctx, sha, repoURL)
		require.NoError(t, err, "expected backfilled commit %s", sha)
		assert.NotEmpty(t, id)
	}
	_, err = store.GetCommitID(ctx, "submitted", repoURL)
	assert.ErrorIs(t, err, storage.ErrNotFound, "the until bound is not the backfiller's to insert")
}

func TestBackfillerNoTrackedCommitUsesEpoch(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	srv := githubtest.NewServer(t)
	srv.Mux.HandleFunc("/repos/org/repo/commits", func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "1970-01-01T00:00:00Z", r.URL.Query().Get("since"), "no tracked commit -> full history (legacy parity)")
		_, _ = w.Write(commitListJSON(t, [][2]string{
			{"submitted", "2021-01-04T00:00:00Z"},
			{"old", "2021-01-02T00:00:00Z"},
			{"first", "2021-01-01T00:00:00Z"},
		}))
	})

	b := commit.NewBackfiller(commit.NewGitHubClient("", srv.URL), store)
	b.Enqueue(commit.BackfillJob{
		RepoURL: repoURL, Spec: "org/repo", DefaultBranch: "org:main",
		Until: time.Date(2021, 1, 4, 0, 0, 0, 0, time.UTC),
	})
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	b.Shutdown(shutdownCtx)

	_, err := store.GetCommitID(ctx, "old", repoURL)
	require.NoError(t, err)
	// commits[1:-1]: both bounds dropped even when the oldest element is not
	// actually tracked — exact legacy behavior.
	_, err = store.GetCommitID(ctx, "first", repoURL)
	assert.ErrorIs(t, err, storage.ErrNotFound)
}

func TestBackfillerQueuesEveryInFlightJob(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)

	release := make(chan struct{})
	var mu sync.Mutex
	var listCalls int
	srv := githubtest.NewServer(t)
	srv.Mux.HandleFunc("/repos/org/repo/commits", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		listCalls++
		first := listCalls == 1
		mu.Unlock()
		if first {
			<-release // hold the first job in flight
		}
		_, _ = w.Write(commitListJSON(t, [][2]string{
			{"submitted", "2021-01-04T00:00:00Z"},
			{"mid", "2021-01-03T00:00:00Z"},
			{"tracked", "2021-01-01T00:00:00Z"},
		}))
	})

	b := commit.NewBackfiller(commit.NewGitHubClient("", srv.URL), store)
	job := commit.BackfillJob{
		RepoURL: repoURL, Spec: "org/repo", DefaultBranch: "org:main",
		Until: time.Date(2021, 1, 4, 0, 0, 0, 0, time.UTC),
	}
	b.Enqueue(job)
	// While job 1 is blocked in flight, subsequent jobs queue as independent
	// windows rather than collapsing into one latest-window rerun.
	b.Enqueue(job)
	b.Enqueue(job)
	close(release)

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	b.Shutdown(shutdownCtx)

	mu.Lock()
	defer mu.Unlock()
	assert.Equal(t, 3, listCalls, "three enqueues while one is in flight still run three queued windows")
	_, err := store.GetCommitID(ctx, "mid", repoURL)
	require.NoError(t, err)
}

func TestBackfillerPreservesOutOfOrderPendingWindows(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)

	release := make(chan struct{})
	var mu sync.Mutex
	var untils []string
	srv := githubtest.NewServer(t)
	srv.Mux.HandleFunc("/repos/org/repo/commits", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		untils = append(untils, r.URL.Query().Get("until"))
		first := len(untils) == 1
		mu.Unlock()
		if first {
			<-release // hold the first job in flight
		}
		_, _ = w.Write([]byte(`[]`))
	})

	b := commit.NewBackfiller(commit.NewGitHubClient("", srv.URL), store)
	job := func(day int) commit.BackfillJob {
		return commit.BackfillJob{
			RepoURL: repoURL, Spec: "org/repo", DefaultBranch: "org:main",
			Until: time.Date(2021, 1, day, 0, 0, 0, 0, time.UTC),
		}
	}
	b.Enqueue(job(1))
	// While job 1 is in flight: a newer commit, then an out-of-order older one.
	b.Enqueue(job(4))
	b.Enqueue(job(2))
	close(release)

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	b.Shutdown(shutdownCtx)

	mu.Lock()
	defer mu.Unlock()
	require.Equal(t, []string{
		"2021-01-01T00:00:00Z",
		"2021-01-04T00:00:00Z",
		"2021-01-02T00:00:00Z",
	}, untils)
}

func TestBackfillerAPIFailureIsSwallowed(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)

	srv := githubtest.NewServer(t)
	srv.HandleStatus("/repos/org/repo/commits", http.StatusNotFound)

	b := commit.NewBackfiller(commit.NewGitHubClient("", srv.URL), store)
	b.Enqueue(commit.BackfillJob{
		RepoURL: repoURL, Spec: "org/repo", DefaultBranch: "org:main",
		Until: time.Date(2021, 1, 4, 0, 0, 0, 0, time.UTC),
	})
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	b.Shutdown(shutdownCtx) // must return; the failure is logged, not propagated
}

func TestBackfillerEnqueueAfterShutdownDropped(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := githubtest.NewServer(t)

	b := commit.NewBackfiller(commit.NewGitHubClient("", srv.URL), store)
	shutdownCtx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	b.Shutdown(shutdownCtx)
	b.Enqueue(commit.BackfillJob{RepoURL: repoURL, Spec: "org/repo", DefaultBranch: "org:main", Until: time.Now().UTC()})
	assert.Empty(t, srv.Requests(), "post-shutdown enqueues are dropped")
}
