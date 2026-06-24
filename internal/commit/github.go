package commit

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"sync/atomic"
	"time"
)

// ErrUnsupportedRepository reports that a commit request cannot be enriched
// through the GitHub API because its repository URL is not a supported
// github.com repository.
var ErrUnsupportedRepository = errors.New("unsupported github repository")

// BackfillJob asks the ancestry backfiller to catch up the default branch of a
// repo through Until (the enriched commit's author timestamp).
type BackfillJob struct {
	RepoURL       string // normalized https URL (commit.repository column value)
	Spec          string // "org/repo" for API calls
	DefaultBranch string // "org:branch" form (commit.branch column value)
	Until         time.Time
}

// BackfillEnqueuer accepts backfill jobs; *Backfiller implements it, and tests
// substitute recorders.
type BackfillEnqueuer interface {
	Enqueue(job BackfillJob)
}

// GitHubProvider resolves commit metadata from the GitHub HTTP API within a
// per-resolve time budget. Any enrichment failure degrades to legacy's minimal
// "unknown" commit row (sha + repository only) — the benchmark result always
// persists — and is logged at WARN with a running counter. Budget exhaustion,
// including a parent request context with little time remaining, degrades the
// same way, and the unknown row persists permanently (resubmission
// short-circuits on it; only the Phase 6 repair job re-enriches). Successful
// enrichment of a default-branch commit enqueues an async ancestry backfill.
type GitHubProvider struct {
	client   *GitHubClient
	budget   time.Duration
	backfill BackfillEnqueuer // nil disables backfill (tests, spec emission)
	unknown  atomic.Int64
}

// NewGitHubProvider builds the provider. budget bounds the total in-request
// GitHub interaction per Resolve (spec default 5s).
func NewGitHubProvider(client *GitHubClient, budget time.Duration, backfill BackfillEnqueuer) *GitHubProvider {
	return &GitHubProvider{client: client, budget: budget, backfill: backfill}
}

// HasUsableGitHubToken reports whether tokenEnv contains at least one token
// accepted by the legacy-compatible token parser.
func HasUsableGitHubToken(tokenEnv string) bool {
	return len(parseTokenEnv(tokenEnv)) > 0
}

// FirstUsableGitHubToken returns the first token accepted by the
// legacy-compatible token parser, or "" when the env value contains none.
func FirstUsableGitHubToken(tokenEnv string) string {
	tokens := parseTokenEnv(tokenEnv)
	if len(tokens) == 0 {
		return ""
	}
	return tokens[0]
}

// UnknownCommitCount reports how many resolves degraded to an unknown commit
// row since process start (Prometheus formalization lands in Phase 6).
func (p *GitHubProvider) UnknownCommitCount() int64 { return p.unknown.Load() }

// Resolve implements Provider.
func (p *GitHubProvider) Resolve(ctx context.Context, req Request) (*Info, error) {
	info, job, err := p.Enrich(ctx, req)
	if err != nil {
		repoURL := NormalizeRepoURL(req.Repository)
		p.unknown.Add(1)
		slog.Warn("github enrichment failed; storing unknown commit",
			"repository", repoURL, "sha", req.Commit, "error", err)
		return &Info{Sha: req.Commit, Repository: repoURL}, nil
	}
	if p.backfill != nil && job != nil {
		p.backfill.Enqueue(*job)
	}
	return info, nil
}

// Enrich resolves commit metadata from GitHub and returns any default-branch
// backfill job the caller may choose to enqueue.
func (p *GitHubProvider) Enrich(ctx context.Context, req Request) (*Info, *BackfillJob, error) {
	if req.Commit == "" {
		return nil, nil, nil
	}
	repoURL := NormalizeRepoURL(req.Repository)

	ctx, cancel := context.WithTimeout(ctx, p.budget)
	defer cancel()

	enr, err := p.enrich(ctx, repoURL, req)
	if err != nil {
		return nil, nil, err
	}

	info := enr.info
	var job *BackfillJob
	if info.Timestamp != nil && info.ForkPointSha != nil && *info.ForkPointSha == info.Sha {
		job = &BackfillJob{
			RepoURL: repoURL, Spec: enr.spec,
			DefaultBranch: enr.defaultBranch, Until: *info.Timestamp,
		}
	}
	return info, job, nil
}

// enrichment carries the successful enrich outputs Resolve needs beyond the
// Info itself: the API spec and default branch the backfill job reuses.
type enrichment struct {
	info          *Info
	spec          string
	defaultBranch string
}

// enrich performs the in-request GitHub calls in legacy order: commit
// metadata, branch resolution (explicit branch > pr_number > default branch),
// then the fork point (merge base against the default branch). The default
// branch is fetched once and reused for the fork-point base (legacy fetches it
// twice; same dependency set). Any error aborts the whole enrichment.
func (p *GitHubProvider) enrich(ctx context.Context, repoURL string, req Request) (enrichment, error) {
	var zero enrichment
	spec, ok := repoSpec(repoURL)
	if !ok {
		return zero, fmt.Errorf("%w: %s", ErrUnsupportedRepository, repoURL)
	}

	meta, err := p.client.commitInfo(ctx, spec, req.Commit)
	if err != nil {
		return zero, fmt.Errorf("fetch commit metadata: %w", err)
	}
	defaultBranch, err := p.client.defaultBranch(ctx, spec)
	if err != nil {
		return zero, fmt.Errorf("resolve default branch: %w", err)
	}

	branch := req.Branch
	if branch == "" && req.PRNumber != nil {
		branch, err = p.client.prBranch(ctx, spec, *req.PRNumber)
		if err != nil {
			return zero, fmt.Errorf("resolve branch from pr %d: %w", *req.PRNumber, err)
		}
	}
	if branch == "" {
		branch = defaultBranch
	}

	forkPoint, err := p.client.mergeBase(ctx, spec, defaultBranch, req.Commit)
	if err != nil {
		return zero, fmt.Errorf("resolve fork point: %w", err)
	}

	ts := meta.Timestamp
	info := &Info{
		Sha:          req.Commit,
		Repository:   repoURL,
		Parent:       meta.Parent,
		Message:      meta.Message,
		AuthorName:   meta.AuthorName,
		AuthorLogin:  meta.AuthorLogin,
		AuthorAvatar: meta.AuthorAvatar,
		Timestamp:    &ts,
		Branch:       &branch,
		ForkPointSha: &forkPoint,
	}
	return enrichment{info: info, spec: spec, defaultBranch: defaultBranch}, nil
}

// repoSpec extracts "org/repo" from a normalized repository URL. Only URLs on
// the real github.com host qualify: legacy enforces the https://github.com
// prefix at request validation (benchmark_result.py:1499) before its substring
// split (repository_to_name, commit.py:365-387), so the prefix check here
// keeps lookalikes such as https://evil.example/github.com/org/repo or
// https://foo.github.com/org/repo from triggering GitHub API calls. ok is
// false for everything else, which degrades to an unknown row with no call.
func repoSpec(repoURL string) (string, bool) {
	after, found := strings.CutPrefix(repoURL, "https://github.com/")
	if !found || after == "" {
		return "", false
	}
	return after, true
}
