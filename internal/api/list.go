package api

import (
	"context"
	"time"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/service"
)

// ListResultsInput is the list/search query. Timestamps are RFC3339 strings,
// parsed in the handler so a bad value is a 422 rather than a silent zero.
type ListResultsInput struct {
	RunID     string `query:"run_id" doc:"Filter by run id."`
	BatchID   string `query:"batch_id" doc:"Filter by batch id."`
	RunReason string `query:"run_reason" doc:"Filter by run reason."`
	Earliest  string `query:"earliest_timestamp" doc:"Lower bound (inclusive), RFC3339."`
	Latest    string `query:"latest_timestamp" doc:"Upper bound (inclusive), RFC3339."`
	Cursor    string `query:"cursor" doc:"Pagination cursor (previous page's last id)."`
	PageSize  int    `query:"page_size" default:"100" doc:"Page size (max 1000)."`
}

// ListResultsOutput carries a list/search page body.
type ListResultsOutput struct {
	Body service.ResultPage
}

func (h *ReadHandler) getResults(ctx context.Context, in *ListResultsInput) (*ListResultsOutput, error) {
	q := service.ListQuery{
		RunID:     in.RunID,
		BatchID:   in.BatchID,
		RunReason: in.RunReason,
		Cursor:    in.Cursor,
		PageSize:  in.PageSize,
	}
	if in.Earliest != "" {
		ts, err := time.Parse(time.RFC3339, in.Earliest)
		if err != nil {
			return nil, huma.Error422UnprocessableEntity("invalid earliest_timestamp: " + err.Error())
		}
		// The storage column is `timestamp without time zone` (UTC convention), so
		// normalize an offset input to UTC before bounding. .UTC() shifts the
		// location, not the instant.
		utc := ts.UTC()
		q.Earliest = &utc
	}
	if in.Latest != "" {
		ts, err := time.Parse(time.RFC3339, in.Latest)
		if err != nil {
			return nil, huma.Error422UnprocessableEntity("invalid latest_timestamp: " + err.Error())
		}
		utc := ts.UTC()
		q.Latest = &utc
	}
	page, err := h.reader.ListResults(ctx, q)
	if err != nil {
		return nil, mapReadError(err)
	}
	return &ListResultsOutput{Body: *page}, nil
}
