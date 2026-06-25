// Package seed populates a development database with a deterministic, hand-built
// benchmark history so `make dev` produces a useful demo: one fingerprint
// (same case/context/hardware/repo) measured across several default-branch
// commits with a visible upward trend, plus a couple of excluded results (an
// off-branch commit and an errored run) to exercise the membership rules.
//
// It seeds through the ingestion service (not raw SQL) so the seeded rows are
// produced by exactly the same path as real submissions. It is idempotent: it
// skips when the database already holds results.
package seed

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

const (
	repo          = "https://github.com/conbench/demo"
	benchmarkName = "demo-benchmark"

	// IncludedHistoryPoints is how many seeded results are members of the
	// history series (the default-branch, non-errored commits).
	IncludedHistoryPoints = 5
)

// Summary reports what a seed run did.
type Summary struct {
	Fingerprint  string              // the seeded history series (empty when skipped)
	ProductSmoke ProductSmokeTargets // named targets for API/browser/docs smoke coverage
	Inserted     int                 // results submitted
	Skipped      bool                // true when the database already held results
}

// ProductSmokeTargets names deterministic seed rows used by product smoke tests,
// docs screenshots, and migration validation. The IDs come from normal ingestion;
// the run, batch, repository, and commit values are stable seed inputs.
type ProductSmokeTargets struct {
	Repository                string
	Fingerprint               string
	LatestResultID            string
	BaselineResultID          string
	ContenderResultID         string
	RecentRunID               string
	RecentBatchID             string
	CIRegressionRunID         string
	CIRegressionCommitSHA     string
	CIActionRequiredRunID     string
	CIActionRequiredCommitSHA string
	ErroredRunID              string
	ErroredResultID           string
}

// includedCommits are the default-branch commits whose results form the history
// series. The minima trend upward (a slowdown, with a regression at commit-04).
var includedCommits = []struct {
	sha     string
	message string
	day     int
	min     float64
}{
	{"commit-01", "Add baseline sort", 1, 1.00},
	{"commit-02", "Tune pivot selection", 2, 1.05},
	{"commit-03", "Vectorize partition", 3, 1.10},
	{"commit-04", "Parallelize merge (regressed)", 5, 1.40},
	{"commit-05", "Cache-friendly layout", 6, 1.45},
}

// Run seeds the database, returning a summary. It is idempotent: when results
// already exist it makes no changes.
func Run(ctx context.Context, store storage.Store) (Summary, error) {
	n, err := store.CountBenchmarkResults(ctx)
	if err != nil {
		return Summary{}, fmt.Errorf("count results: %w", err)
	}
	if n > 0 {
		return Summary{Skipped: true}, nil
	}

	ingester := service.NewIngester(store, commit.MapProvider{Commits: commitMap()})
	reqs := requests()
	var fingerprint string
	resultByLabel := make(map[string]*service.Result, len(reqs))
	for _, r := range reqs {
		res, err := ingester.Submit(ctx, r.req)
		if err != nil {
			return Summary{}, fmt.Errorf("seed submit %s: %w", r.label, err)
		}
		resultByLabel[r.label] = res
		if r.included {
			fingerprint = res.HistoryFingerprint
		}
	}
	targets, err := productSmokeTargets(fingerprint, resultByLabel)
	if err != nil {
		return Summary{}, err
	}
	return Summary{Fingerprint: fingerprint, ProductSmoke: targets, Inserted: len(reqs)}, nil
}

// DevTokenStore is the slice of the data layer DevToken needs. *db.Store
// satisfies it.
type DevTokenStore interface {
	GetOrCreateUserByEmail(ctx context.Context, email, name, password string) (string, error)
	GetAPITokenByHash(ctx context.Context, tokenHash string) (storage.APIToken, error)
	CreateAPIToken(ctx context.Context, p storage.InsertAPITokenParams) (string, error)
}

// DevToken get-or-creates a dev user and a user-attributed API token whose hash
// is auth.HashToken(plaintext), so a development or e2e run can exercise
// user-attributed endpoints without an OIDC round-trip. It is idempotent: if a
// token with that hash already exists it does nothing. The plaintext is never
// logged (only the prefix is returned). It requires plaintext of at least 8
// characters (the prefix width).
func DevToken(ctx context.Context, store DevTokenStore, plaintext string) (prefix string, err error) {
	runes := []rune(plaintext)
	if len(runes) < 8 {
		return "", fmt.Errorf("dev token must be at least 8 characters, got %d", len(runes))
	}
	prefix = string(runes[:8]) // rune-safe so a multi-byte value cannot cut mid-rune
	hash := auth.HashToken(plaintext)

	_, err = store.GetAPITokenByHash(ctx, hash)
	switch {
	case err == nil:
		return prefix, nil
	case errors.Is(err, storage.ErrNotFound):
		// fall through to create
	default:
		return "", fmt.Errorf("lookup dev token: %w", err)
	}

	userID, err := store.GetOrCreateUserByEmail(ctx, "dev@conbench.local", "Dev (seeded)", "!")
	if err != nil {
		return "", fmt.Errorf("get-or-create dev user: %w", err)
	}
	if _, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID:      userID,
		Name:        "dev seed token",
		TokenHash:   hash,
		TokenPrefix: prefix,
		CreatedAt:   time.Now().UTC(),
	}); err != nil {
		return "", fmt.Errorf("create dev token: %w", err)
	}
	return prefix, nil
}

// seedResult is one planned submission and whether it should join the history.
type seedResult struct {
	label    string
	included bool
	req      service.SubmitRequest
}

// requests is the full seed plan: the included series plus two excluded results.
func requests() []seedResult {
	out := make([]seedResult, 0, len(includedCommits)+2)
	for _, c := range includedCommits {
		out = append(out, seedResult{label: c.sha, included: true, req: baseReq(c.sha, c.day, trend(c.min))})
	}
	// Excluded: an off-branch commit (sha != fork_point_sha), shaped as a clear
	// PR regression against commit-03 for CI report smoke coverage.
	out = append(out, seedResult{label: "feature-branch-1", included: false, req: baseReq("feature-branch-1", 4, trend(1.80))})
	// Excluded: an errored run (a missing iteration -> partial result).
	out = append(out, seedResult{label: "commit-06-broken", included: false, req: baseReq("commit-06-broken", 7, partial(1.00))})
	return out
}

func productSmokeTargets(fingerprint string, results map[string]*service.Result) (ProductSmokeTargets, error) {
	resultID := func(label string) (string, error) {
		res, ok := results[label]
		if !ok || res == nil || res.ID == "" {
			return "", fmt.Errorf("seed target %s missing result id", label)
		}
		return res.ID, nil
	}

	latestID, err := resultID("commit-05")
	if err != nil {
		return ProductSmokeTargets{}, err
	}
	baselineID, err := resultID("commit-01")
	if err != nil {
		return ProductSmokeTargets{}, err
	}
	erroredID, err := resultID("commit-06-broken")
	if err != nil {
		return ProductSmokeTargets{}, err
	}

	return ProductSmokeTargets{
		Repository:                repo,
		Fingerprint:               fingerprint,
		LatestResultID:            latestID,
		BaselineResultID:          baselineID,
		ContenderResultID:         latestID,
		RecentRunID:               "run-commit-05",
		RecentBatchID:             "batch-commit-05",
		CIRegressionRunID:         "run-feature-branch-1",
		CIRegressionCommitSHA:     "feature-branch-1",
		CIActionRequiredRunID:     "run-commit-05",
		CIActionRequiredCommitSHA: "commit-05",
		ErroredRunID:              "run-commit-06-broken",
		ErroredResultID:           erroredID,
	}, nil
}

// commitMap gives each seeded sha a real message and timestamp. Included commits
// default to the default branch (fork_point_sha == sha); feature-branch-1 forks
// from commit-03 so it is excluded from history.
func commitMap() map[string]commit.Info {
	m := make(map[string]commit.Info, len(includedCommits)+2)
	for _, c := range includedCommits {
		ts := day(c.day)
		m[c.sha] = commit.Info{Message: c.message, Timestamp: &ts}
	}
	branchPoint := includedCommits[2].sha
	featureTS := day(4)
	m["feature-branch-1"] = commit.Info{Message: "WIP: experimental layout", Timestamp: &featureTS, ForkPointSha: &branchPoint}
	brokenTS := day(7)
	m["commit-06-broken"] = commit.Info{Message: "Broken nightly run", Timestamp: &brokenTS}
	return m
}

// baseReq builds a submission sharing one fingerprint (case/context/hardware/repo)
// for the given commit, timestamp, and samples.
func baseReq(sha string, d int, data []*float64) service.SubmitRequest {
	runName := "nightly"
	return service.SubmitRequest{
		Tags:        map[string]any{"name": benchmarkName, "dataset": "uniform"},
		Context:     map[string]any{"compiler": "gcc-13", "optimization": "O2"},
		Info:        map[string]any{"benchmark_language": "C++"},
		MachineInfo: machine(),
		GitHub:      service.GitHubInfo{Commit: sha, Repository: repo},
		RunID:       "run-" + sha,
		RunName:     &runName,
		BatchID:     "batch-" + sha,
		Timestamp:   day(d),
		Stats:       &service.StatsInput{Data: data, Unit: "s"},
	}
}

func machine() *service.MachineInfo {
	architectureName := "arm64"
	osName := "Linux"
	cpuModelName := "Demo CPU"
	cpuCoreCount := int32(10)
	cpuThreadCount := int32(10)
	memoryBytes := int64(32 << 30)
	gpuCount := int32(0)
	return &service.MachineInfo{
		Name:             "demo-runner",
		ArchitectureName: &architectureName,
		OsName:           &osName,
		CpuModelName:     &cpuModelName,
		CpuCoreCount:     &cpuCoreCount,
		CpuThreadCount:   &cpuThreadCount,
		MemoryBytes:      &memoryBytes,
		GpuCount:         &gpuCount,
	}
}

// trend returns three increasing samples whose minimum (the single value summary
// for the less-is-better "s" unit) is min.
func trend(min float64) []*float64 {
	a, b, c := min, min+0.02, min+0.04
	return []*float64{&a, &b, &c}
}

// partial returns samples with a missing middle iteration, marking an errored run.
func partial(min float64) []*float64 {
	a, c := min, min+0.04
	return []*float64{&a, nil, &c}
}

func day(d int) time.Time {
	return time.Date(2024, 1, d, 12, 0, 0, 0, time.UTC)
}
