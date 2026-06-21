package service

import (
	"context"
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
)

// RecentRunsQuery is the parsed recent-runs input.
type RecentRunsQuery struct {
	PageSize int
}

// RecentRunListItem is one grouped run on the dashboard landing page.
type RecentRunListItem struct {
	RunID         string         `json:"run_id"`
	RunReason     *string        `json:"run_reason"`
	RunTags       map[string]any `json:"run_tags"`
	BatchCount    int64          `json:"batch_count"`
	LatestBatchID *string        `json:"latest_batch_id"`
	ResultCount   int64          `json:"result_count"`
	ErrorCount    int64          `json:"error_count"`
	SeriesCount   int64          `json:"series_count"`
	LatestResult  string         `json:"latest_result_id"`
	Repository    string         `json:"repository"`
	CommitSHA     *string        `json:"commit_sha"`
	FirstResultAt time.Time      `json:"first_result_at"`
	LastResultAt  time.Time      `json:"last_result_at"`
	Commit        *ListCommit    `json:"commit"`
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
