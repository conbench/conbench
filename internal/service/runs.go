package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/conbench/conbench/internal/storage"
)

const (
	recentRunsPageSizeDefault = 25
	recentRunsPageSizeMax     = 100
	recentRunsCandidateMin    = int32(1000)
	recentRunsCandidateMax    = int32(10000)
	recentRunsCandidateFactor = int32(200)
	recentRunsAttentionLimit  = 5
)

// RecentRunsQuery is the parsed recent-runs input.
type RecentRunsQuery struct {
	PageSize         int
	IncludeAttention bool
}

// RecentRunAttention is an opt-in, bounded CI triage summary for a recent run.
// It is present only when the run needs attention; successful/skipped reports
// and default-branch-only action-required reports are omitted.
type RecentRunAttention struct {
	Status       CIReportStatus            `json:"status" enum:"success,failure,action_required,skipped"`
	StatusReason string                    `json:"status_reason"`
	ReportURL    string                    `json:"report_url"`
	Summary      RecentRunAttentionSummary `json:"summary"`
}

// RecentRunAttentionSummary is the small subset of CI report summary counts
// needed to make the home page actionable without embedding full report rows.
type RecentRunAttentionSummary struct {
	Compared        int `json:"compared"`
	Regressions     int `json:"regressions"`
	BenchmarkErrors int `json:"benchmark_errors"`
	MissingBaseline int `json:"missing_baseline"`
	NotComparable   int `json:"not_comparable"`
}

// RecentRunListItem is one grouped run on the dashboard landing page.
type RecentRunListItem struct {
	RunID         string              `json:"run_id"`
	RunReason     *string             `json:"run_reason"`
	RunTags       map[string]any      `json:"run_tags"`
	BatchCount    int64               `json:"batch_count"`
	LatestBatchID *string             `json:"latest_batch_id"`
	ResultCount   int64               `json:"result_count"`
	ErrorCount    int64               `json:"error_count"`
	SeriesCount   int64               `json:"series_count"`
	LatestResult  string              `json:"latest_result_id"`
	Repository    string              `json:"repository"`
	CommitSHA     *string             `json:"commit_sha"`
	FirstResultAt time.Time           `json:"first_result_at"`
	LastResultAt  time.Time           `json:"last_result_at"`
	Commit        *ListCommit         `json:"commit"`
	Attention     *RecentRunAttention `json:"attention,omitempty"`
}

// RecentRunsPage is the GET /api/runs/recent response.
type RecentRunsPage struct {
	Runs []RecentRunListItem `json:"runs"`
}

// ListRecentRuns returns grouped summaries for the newest runs.
func (r *Reader) ListRecentRuns(ctx context.Context, q RecentRunsQuery) (*RecentRunsPage, error) {
	pageSize := q.PageSize
	if pageSize <= 0 {
		pageSize = recentRunsPageSizeDefault
	}
	if pageSize > recentRunsPageSizeMax {
		pageSize = recentRunsPageSizeMax
	}

	rows, err := r.store.SelectRecentRuns(ctx, storage.RecentRunsParams{
		CandidateResultCount: recentRunsCandidateCount(pageSize),
		PageSize:             int32(pageSize),
	})
	if err != nil {
		return nil, fmt.Errorf("list recent runs: %w", err)
	}

	items := make([]RecentRunListItem, 0, len(rows))
	for _, row := range rows {
		item, err := recentRunListItem(row)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	if q.IncludeAttention {
		r.attachRecentRunAttention(ctx, items)
	}
	return &RecentRunsPage{Runs: items}, nil
}

func recentRunsCandidateCount(pageSize int) int32 {
	limit := int32(pageSize) * recentRunsCandidateFactor
	if limit < recentRunsCandidateMin {
		return recentRunsCandidateMin
	}
	if limit > recentRunsCandidateMax {
		return recentRunsCandidateMax
	}
	return limit
}

func (r *Reader) attachRecentRunAttention(ctx context.Context, items []RecentRunListItem) {
	reporter := NewCIReporter(r.store)
	limit := min(len(items), recentRunsAttentionLimit)
	for i := range limit {
		items[i].Attention = r.recentRunAttention(ctx, reporter, items[i])
	}
}

func (r *Reader) recentRunAttention(ctx context.Context, reporter *CIReporter, item RecentRunListItem) *RecentRunAttention {
	q := CIReportQuery{
		RunIDs:   []string{item.RunID},
		Baseline: CIReportBaselineForkPoint,
	}
	if item.Repository != "" && item.CommitSHA != nil && *item.CommitSHA != "" {
		q.Repository = item.Repository
		q.CommitSHA = *item.CommitSHA
	}
	report, err := reporter.Report(ctx, q)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			return nil
		}
		return &RecentRunAttention{
			Status:       CIReportStatusActionRequired,
			StatusReason: "CI report could not be evaluated",
			ReportURL:    reporter.ciReportURL(q, item.Repository, item.CommitSHA, CIReportBaselineForkPoint, 0, 0),
			Summary:      RecentRunAttentionSummary{},
		}
	}
	return recentRunAttentionFromReport(report)
}

func recentRunAttentionFromReport(report *CIReport) *RecentRunAttention {
	if report.Status == CIReportStatusSuccess || report.Status == CIReportStatusSkipped {
		return nil
	}
	if ciReportIsDefaultBranchOnly(report) {
		return nil
	}
	return &RecentRunAttention{
		Status:       report.Status,
		StatusReason: report.StatusReason,
		ReportURL:    report.ReportURL,
		Summary: RecentRunAttentionSummary{
			Compared:        report.Summary.Compared,
			Regressions:     report.Summary.Regressions,
			BenchmarkErrors: report.Summary.BenchmarkErrors,
			MissingBaseline: report.Summary.MissingBaseline,
			NotComparable:   report.Summary.NotComparable,
		},
	}
}

func ciReportIsDefaultBranchOnly(report *CIReport) bool {
	if report.Status != CIReportStatusActionRequired || len(report.Runs) == 0 {
		return false
	}
	for _, run := range report.Runs {
		if run.BaselineError == nil || run.BaselineError.Code != CIReportBaselineErrorDefaultBranchRun {
			return false
		}
	}
	return true
}

func recentRunListItem(row storage.RecentRunRow) (RecentRunListItem, error) {
	runTags, err := jsonObject(row.RunTags)
	if err != nil {
		return RecentRunListItem{}, err
	}
	return RecentRunListItem{
		RunID:         row.RunID,
		RunReason:     row.RunReason,
		RunTags:       runTags,
		BatchCount:    row.BatchCount,
		LatestBatchID: row.LatestBatchID,
		ResultCount:   row.ResultCount,
		ErrorCount:    row.ErrorCount,
		SeriesCount:   row.SeriesCount,
		LatestResult:  row.LatestResultID,
		Repository:    row.Repository,
		CommitSHA:     row.CommitSha,
		FirstResultAt: row.FirstResultAt,
		LastResultAt:  row.LastResultAt,
		Commit:        recentRunCommit(row),
	}, nil
}

func recentRunCommit(row storage.RecentRunRow) *ListCommit {
	if row.CommitSha == nil {
		return nil
	}
	return &ListCommit{
		Hash:       *row.CommitSha,
		Repository: derefString(row.CommitRepository),
		Timestamp:  row.CommitTimestamp,
	}
}
