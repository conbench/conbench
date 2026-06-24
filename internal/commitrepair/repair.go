package commitrepair

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/storage"
)

const maxFailureSamples = 10
const maxInt32 = int(1<<31 - 1)

// Store is the minimal persistence surface the repair engine needs.
type Store interface {
	SelectUnknownCommitRepairCandidates(context.Context, storage.UnknownCommitCandidateParams) ([]storage.UnknownCommitCandidate, error)
	UpdateUnknownCommit(context.Context, storage.UpdateUnknownCommitParams) (int64, error)
}

// Enricher resolves commit metadata without request-time degradation.
type Enricher interface {
	Enrich(context.Context, commit.Request) (*commit.Info, *commit.BackfillJob, error)
}

// BackfillEnqueuer accepts default-branch ancestry backfill work.
type BackfillEnqueuer interface {
	Enqueue(commit.BackfillJob)
}

// Options bounds one repair run.
type Options struct {
	Repository *string
	Limit      int
	Cursor     *Cursor
	DryRun     bool
	Backfill   bool
}

// Summary reports the outcome of one bounded repair run.
type Summary struct {
	Scanned               int       `json:"scanned"`
	Repaired              int       `json:"repaired"`
	WouldRepair           int       `json:"would_repair"`
	UnsupportedRepository int       `json:"unsupported_repository"`
	Failed                int       `json:"failed"`
	AuthOrQuotaFailures   int       `json:"auth_or_quota_failures"`
	AlreadyRepaired       int       `json:"already_repaired"`
	BackfillEnqueued      int       `json:"backfill_enqueued"`
	WouldBackfill         int       `json:"would_backfill"`
	BackfillTimedOut      bool      `json:"backfill_timed_out"`
	NextCursor            *string   `json:"next_cursor"`
	Failures              []Failure `json:"failures,omitempty"`
}

// Failure is a bounded sample of per-row enrichment failures.
type Failure struct {
	Repository string `json:"repository"`
	Sha        string `json:"sha"`
	Error      string `json:"error"`
}

// Repairer repairs persisted unknown commit rows through narrow collaborators.
type Repairer struct {
	store    Store
	enricher Enricher
	backfill BackfillEnqueuer
}

// NewRepairer constructs a repair engine.
func NewRepairer(store Store, enricher Enricher, backfill BackfillEnqueuer) *Repairer {
	return &Repairer{store: store, enricher: enricher, backfill: backfill}
}

// Run scans and repairs at most opts.Limit unknown commit candidates.
func (r *Repairer) Run(ctx context.Context, opts Options) (Summary, error) {
	var summary Summary
	if opts.Limit <= 0 {
		return summary, errors.New("limit must be greater than 0")
	}
	if opts.Limit >= maxInt32 {
		return summary, errors.New("limit is too large")
	}
	if opts.Cursor != nil {
		if err := validateCursor(*opts.Cursor); err != nil {
			return summary, err
		}
		if opts.Repository != nil && *opts.Repository != opts.Cursor.Repository {
			return summary, fmt.Errorf("cursor repository %q does not match repository filter %q", opts.Cursor.Repository, *opts.Repository)
		}
	}
	if r == nil {
		return summary, errors.New("repairer is required")
	}
	if r.store == nil {
		return summary, errors.New("repair store is required")
	}
	if r.enricher == nil {
		return summary, errors.New("commit enricher is required")
	}
	if err := ctx.Err(); err != nil {
		return summary, err
	}

	params := storage.UnknownCommitCandidateParams{
		Repository:   opts.Repository,
		LimitPlusOne: int32(opts.Limit + 1),
	}
	if opts.Cursor != nil {
		params.AfterRepository = &opts.Cursor.Repository
		params.AfterSha = &opts.Cursor.Sha
	}

	candidates, err := r.store.SelectUnknownCommitRepairCandidates(ctx, params)
	if err != nil {
		return summary, err
	}

	inspect := candidates
	if len(inspect) > opts.Limit {
		inspect = inspect[:opts.Limit]
		last := inspect[len(inspect)-1]
		encoded, err := EncodeCursor(Cursor{Repository: last.Repository, Sha: last.Sha})
		if err != nil {
			return summary, err
		}
		summary.NextCursor = &encoded
	}

	for _, candidate := range inspect {
		if err := ctx.Err(); err != nil {
			return summary, err
		}
		summary.Scanned++
		info, job, err := r.enricher.Enrich(ctx, commit.Request{
			Commit:     candidate.Sha,
			Repository: candidate.Repository,
		})
		if err != nil {
			if ctxErr := ctx.Err(); ctxErr != nil {
				return summary, ctxErr
			}
		}
		if errors.Is(err, commit.ErrUnsupportedRepository) {
			summary.UnsupportedRepository++
			continue
		}
		if err != nil {
			recordFailure(&summary, candidate, err)
			continue
		}
		if info == nil || info.Timestamp == nil || info.ForkPointSha == nil {
			recordFailure(&summary, candidate, errors.New("enrichment returned incomplete commit metadata"))
			continue
		}

		if opts.DryRun {
			summary.WouldRepair++
			if job != nil {
				summary.WouldBackfill++
			}
			continue
		}

		rows, err := r.store.UpdateUnknownCommit(ctx, updateParams(candidate.ID, info))
		if err != nil {
			return summary, err
		}
		if rows == 0 {
			summary.AlreadyRepaired++
			continue
		}
		summary.Repaired++

		if job == nil {
			continue
		}
		if opts.Backfill && r.backfill != nil && rows == 1 {
			r.backfill.Enqueue(*job)
			summary.BackfillEnqueued++
			continue
		}
		summary.WouldBackfill++
	}

	return summary, nil
}

func updateParams(id string, info *commit.Info) storage.UpdateUnknownCommitParams {
	return storage.UpdateUnknownCommitParams{
		ID:           id,
		Parent:       info.Parent,
		Message:      info.Message,
		AuthorName:   info.AuthorName,
		AuthorLogin:  info.AuthorLogin,
		AuthorAvatar: info.AuthorAvatar,
		Timestamp:    *info.Timestamp,
		Branch:       info.Branch,
		ForkPointSha: info.ForkPointSha,
	}
}

func recordFailure(summary *Summary, candidate storage.UnknownCommitCandidate, err error) {
	summary.Failed++
	if isGitHubAuthOrQuotaFailure(err) {
		summary.AuthOrQuotaFailures++
	}
	if len(summary.Failures) >= maxFailureSamples {
		return
	}
	summary.Failures = append(summary.Failures, Failure{
		Repository: candidate.Repository,
		Sha:        candidate.Sha,
		Error:      err.Error(),
	})
}

func isGitHubAuthOrQuotaFailure(err error) bool {
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "unexpected github response 401") ||
		strings.Contains(msg, "unexpected github response 403") ||
		strings.Contains(msg, "github 403") ||
		strings.Contains(msg, "bad credentials") ||
		strings.Contains(msg, "quota exhausted")
}
