package commit

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/conbench/conbench/internal/storage"
)

// backfillCallTimeout bounds each logical GitHub GET during backfill (legacy's
// per-request retry deadline was 20s, commit.py:848). The job as a whole is
// unbounded — a first-ever backfill of a large repo legitimately pages for a
// while — but every page fetch must conclude.
const backfillCallTimeout = 20 * time.Second

// BackfillStore is the slice of the data layer the backfiller needs; *db.Store
// satisfies it.
type BackfillStore interface {
	LatestCommitTimestampOnBranch(ctx context.Context, repository, branch string, before time.Time) (*time.Time, error)
	GetOrCreateCommit(ctx context.Context, p storage.InsertCommitParams) (string, error)
}

// Backfiller catches up default-branch ancestry asynchronously: one in-flight
// job per repository, with later enqueues for the same repository queued as
// independent ancestry windows. Failures are logged and never affect the
// originating submit. Shutdown drains in-flight and pending work, aborting via
// context cancellation if the drain deadline passes.
type Backfiller struct {
	client *GitHubClient
	store  BackfillStore

	//nolint:containedctx // The root context is the worker's lifecycle handle:
	// async backfill goroutines outlive any single Enqueue caller, and Shutdown
	// cancels through it to abort in-flight GitHub calls on drain overrun.
	ctx    context.Context
	cancel context.CancelFunc

	mu     sync.Mutex
	state  map[string]*repoState
	closed bool
	wg     sync.WaitGroup
}

type repoState struct {
	running bool
	pending []BackfillJob
}

// NewBackfiller builds a worker over the GitHub client and the data layer.
func NewBackfiller(client *GitHubClient, store BackfillStore) *Backfiller {
	ctx, cancel := context.WithCancel(context.Background())
	return &Backfiller{client: client, store: store, ctx: ctx, cancel: cancel, state: make(map[string]*repoState)}
}

// Enqueue implements BackfillEnqueuer. It never blocks: if the repo already
// has a job in flight, the job is queued behind it. Keeping every requested
// window matters for out-of-order repaired default-branch commits; after
// Shutdown, jobs are dropped.
func (b *Backfiller) Enqueue(job BackfillJob) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		slog.Info("backfill: enqueue after shutdown, dropping", "repository", job.RepoURL)
		return
	}
	st := b.state[job.RepoURL]
	if st == nil {
		st = &repoState{}
		b.state[job.RepoURL] = st
	}
	if st.running {
		st.pending = append(st.pending, job)
		return
	}
	st.running = true
	b.wg.Add(1)
	go b.runLoop(job)
}

// Shutdown stops accepting jobs and waits for in-flight (and already-pending)
// work to drain. If ctx expires first, outstanding GitHub calls are cancelled
// and Shutdown waits for the goroutines to observe that. The returned bool is
// true only when Shutdown took that timeout branch.
func (b *Backfiller) Shutdown(ctx context.Context) bool {
	b.mu.Lock()
	b.closed = true
	b.mu.Unlock()

	timedOut := false
	done := make(chan struct{})
	go func() {
		b.wg.Wait()
		close(done)
	}()
	select {
	case <-done:
	case <-ctx.Done():
		timedOut = true
		slog.Warn("backfill: drain deadline passed, aborting in-flight work")
		b.cancel()
		<-done
	}
	b.cancel()
	return timedOut
}

// runLoop runs the job, then any jobs queued while it ran. The repo's state
// entry is removed once it goes idle so the map stays bounded by active repos,
// not by every repo ever seen.
func (b *Backfiller) runLoop(job BackfillJob) {
	defer b.wg.Done()
	for {
		b.runOne(job)
		b.mu.Lock()
		st := b.state[job.RepoURL]
		if len(st.pending) == 0 {
			delete(b.state, job.RepoURL)
			b.mu.Unlock()
			return
		}
		job = st.pending[0]
		copy(st.pending, st.pending[1:])
		st.pending = st.pending[:len(st.pending)-1]
		b.mu.Unlock()
	}
}

// runOne executes a single backfill: window lookup, paged fetch, trimmed
// upsert. Every failure path logs and returns; nothing propagates.
func (b *Backfiller) runOne(job BackfillJob) {
	since, err := b.sinceBound(job)
	if err != nil {
		slog.Error("backfill: query last tracked commit", "repository", job.RepoURL, "error", err)
		return
	}

	commits, err := b.fetchWindow(job, since)
	if err != nil {
		slog.Error("backfill: fetch commit window", "repository", job.RepoURL, "error", err)
		return
	}
	// GitHub's since/until are inclusive and the list is newest-first; legacy
	// drops the first and last element to make the window exclusive on both
	// ends (commits[1:-1], commit.py:526).
	if len(commits) <= 2 {
		return
	}
	commits = commits[1 : len(commits)-1]

	inserted := 0
	for i := range commits {
		if b.insertOne(job, commits[i]) {
			inserted++
		}
	}
	slog.Info("backfill: done", "repository", job.RepoURL, "window_commits", len(commits), "inserted", inserted)
}

// sinceBound returns the last tracked default-branch commit timestamp, or the
// epoch when the branch is untracked (legacy: fetch since beginning of time).
func (b *Backfiller) sinceBound(job BackfillJob) (time.Time, error) {
	ctx, cancel := context.WithTimeout(b.ctx, backfillCallTimeout)
	defer cancel()
	ts, err := b.store.LatestCommitTimestampOnBranch(ctx, job.RepoURL, job.DefaultBranch, job.Until)
	if err != nil {
		return time.Time{}, err
	}
	if ts == nil {
		return time.Date(1970, 1, 1, 0, 0, 0, 0, time.UTC), nil
	}
	return *ts, nil
}

// fetchWindow pages the commits-list API for the job's window. The per-call
// timeout applies to each page fetch via the client; the paging loop itself
// runs under the backfiller's root context so shutdown can abort it.
func (b *Backfiller) fetchWindow(job BackfillJob, since time.Time) ([]commitJSON, error) {
	return b.client.commitsOnBranch(b.ctx, job.Spec, job.DefaultBranch, since, job.Until)
}

// insertOne parses and upserts one backfilled commit: on the default branch by
// definition (fork_point_sha = own sha), conflict-do-nothing via get-or-create.
func (b *Backfiller) insertOne(job BackfillJob, cj commitJSON) bool {
	parsed, err := parseCommit(cj)
	if err != nil {
		slog.Warn("backfill: skip unparseable commit", "repository", job.RepoURL, "sha", cj.Sha, "error", err)
		return false
	}
	ctx, cancel := context.WithTimeout(b.ctx, backfillCallTimeout)
	defer cancel()
	sha := cj.Sha
	branch := job.DefaultBranch
	ts := parsed.Timestamp
	_, err = b.store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha:          sha,
		Parent:       parsed.Parent,
		Repository:   job.RepoURL,
		Message:      parsed.Message,
		AuthorName:   parsed.AuthorName,
		AuthorLogin:  parsed.AuthorLogin,
		AuthorAvatar: parsed.AuthorAvatar,
		Timestamp:    &ts,
		Branch:       &branch,
		ForkPointSha: &sha,
	})
	if err != nil {
		slog.Warn("backfill: insert commit", "repository", job.RepoURL, "sha", cj.Sha, "error", err)
		return false
	}
	return true
}
