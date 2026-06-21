package service

import (
	"context"
	"fmt"
	"time"

	"github.com/conbench/conbench/internal/storage"
)

// listPageSizeDefault and listPageSizeMax bound the page size (spec: default 100,
// clamp to 1000).
const (
	listPageSizeDefault = 100
	listPageSizeMax     = 1000
)

// ListQuery is the already-parsed list/search input.
type ListQuery struct {
	RunID     string
	BatchID   string
	RunReason string
	Earliest  *time.Time
	Latest    *time.Time
	Cursor    string
	PageSize  int
}

// ListCommit is the minimal commit subset on a list item. The blank nullable
// marker makes huma emit it as nullable (null for a commitless result).
type ListCommit struct {
	_          struct{}   `json:"-" nullable:"true"`
	Hash       string     `json:"hash"`
	Repository string     `json:"repository"`
	Timestamp  *time.Time `json:"timestamp"`
}

// ResultListItem is one row of the list/search response.
type ResultListItem struct {
	ID                 string         `json:"id"`
	RunID              string         `json:"run_id"`
	RunReason          *string        `json:"run_reason"`
	RunTags            map[string]any `json:"run_tags"`
	BatchID            *string        `json:"batch_id"`
	Timestamp          time.Time      `json:"timestamp"`
	Unit               *string        `json:"unit"`
	SVS                *float64       `json:"single_value_summary"`
	SVSType            string         `json:"single_value_summary_type"`
	HistoryFingerprint string         `json:"history_fingerprint"`
	Commit             *ListCommit    `json:"commit"`
	HasError           bool           `json:"has_error"`
}

// ResultPage is the list/search response: a page of items plus the cursor for the
// next page (null when the page was not full).
type ResultPage struct {
	Results        []ResultListItem `json:"results"`
	NextPageCursor *string          `json:"next_page_cursor"`
}

// ListResults returns one filtered, cursor-paginated page of results.
func (r *Reader) ListResults(ctx context.Context, q ListQuery) (*ResultPage, error) {
	pageSize := q.PageSize
	if pageSize <= 0 {
		pageSize = listPageSizeDefault
	}
	if pageSize > listPageSizeMax {
		pageSize = listPageSizeMax
	}

	params := storage.ListResultsParams{
		Earliest: q.Earliest,
		Latest:   q.Latest,
		PageSize: int32(pageSize),
	}
	if q.RunID != "" {
		params.RunID = &q.RunID
	}
	if q.BatchID != "" {
		params.BatchID = &q.BatchID
	}
	if q.RunReason != "" {
		params.RunReason = &q.RunReason
	}
	// Treat "" and the literal "null" (a client echoing a JSON null) as no cursor.
	if q.Cursor != "" && q.Cursor != "null" {
		params.Cursor = &q.Cursor
	}

	rows, err := r.store.SelectBenchmarkResults(ctx, params)
	if err != nil {
		return nil, fmt.Errorf("list results: %w", err)
	}

	items := make([]ResultListItem, 0, len(rows))
	for _, row := range rows {
		svs, svsType, err := resultSVS(row.Unit, nonNullFloats(row.Data), row.Error != nil)
		if err != nil {
			return nil, err
		}
		runTags, err := jsonObject(row.RunTags)
		if err != nil {
			return nil, err
		}
		items = append(items, ResultListItem{
			ID:                 row.ID,
			RunID:              row.RunID,
			RunReason:          row.RunReason,
			RunTags:            runTags,
			BatchID:            row.BatchID,
			Timestamp:          row.Timestamp,
			Unit:               row.Unit,
			SVS:                svs,
			SVSType:            svsType,
			HistoryFingerprint: row.HistoryFingerprint,
			Commit:             listCommit(row),
			HasError:           row.Error != nil,
		})
	}

	page := &ResultPage{Results: items}
	if len(items) == pageSize {
		last := items[len(items)-1].ID
		page.NextPageCursor = &last
	}
	return page, nil
}

// listCommit builds the minimal commit subset, or nil when the result has none.
func listCommit(row storage.ResultListRow) *ListCommit {
	if row.CommitSha == nil {
		return nil
	}
	return &ListCommit{
		Hash:       *row.CommitSha,
		Repository: derefString(row.CommitRepository),
		Timestamp:  row.CommitTimestamp,
	}
}
