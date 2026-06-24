package api

import (
	"context"

	"github.com/conbench/conbench/internal/service"
)

// ListRecentRunsInput is the recent-runs dashboard query.
type ListRecentRunsInput struct {
	PageSize int `query:"page_size" default:"25" doc:"Page size (max 100)."`
}

// ListRecentRunsOutput carries the recent-runs page body.
type ListRecentRunsOutput struct {
	Body service.RecentRunsPage
}

func (h *ReadHandler) getRecentRuns(ctx context.Context, in *ListRecentRunsInput) (*ListRecentRunsOutput, error) {
	page, err := h.reader.ListRecentRuns(ctx, service.RecentRunsQuery{PageSize: in.PageSize})
	if err != nil {
		return nil, mapReadError(err)
	}
	return &ListRecentRunsOutput{Body: *page}, nil
}
