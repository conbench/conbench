package api

import (
	"context"
	"encoding/base64"
	"strings"
	"time"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/service"
)

// ListSeriesInput is the series list/search query. Timestamps are RFC3339 strings
// parsed in the handler so a bad value is a 422, and the cursor is the opaque token
// returned by a previous page; the API owns its encoding, so the service only ever
// sees the decoded (timestamp, fingerprint) pair.
type ListSeriesInput struct {
	Q           string `query:"q" doc:"Substring match on case name and case tags."`
	Hardware    string `query:"hardware" doc:"Filter by hardware name."`
	Repository  string `query:"repository" doc:"Filter by repository URL."`
	Fingerprint string `query:"fingerprint" doc:"Filter by history fingerprint."`
	ActiveSince string `query:"active_since" doc:"Latest commit at or after this instant, RFC3339."`
	ActiveUntil string `query:"active_until" doc:"Latest commit at or before this instant, RFC3339."`
	Cursor      string `query:"cursor" doc:"Pagination cursor from a previous page's next_page_cursor."`
	PageSize    int    `query:"page_size" default:"100" doc:"Page size (max 1000)."`
}

// SeriesPage is the series list/search response: a page of rows plus the opaque
// cursor for the next page (null when the page was not full).
type SeriesPage struct {
	Series         []service.SeriesListItem `json:"series"`
	NextPageCursor *string                  `json:"next_page_cursor"`
}

// ListSeriesOutput carries a series list/search page body.
type ListSeriesOutput struct {
	Body SeriesPage
}

func (h *ReadHandler) getSeries(ctx context.Context, in *ListSeriesInput) (*ListSeriesOutput, error) {
	q := service.SeriesQuery{PageSize: in.PageSize}
	setIfNonEmpty(&q.Q, in.Q)
	setIfNonEmpty(&q.Hardware, in.Hardware)
	setIfNonEmpty(&q.Repository, in.Repository)
	setIfNonEmpty(&q.Fingerprint, in.Fingerprint)

	if err := parseUTCBound(in.ActiveSince, "active_since", &q.ActiveSince); err != nil {
		return nil, err
	}
	if err := parseUTCBound(in.ActiveUntil, "active_until", &q.ActiveUntil); err != nil {
		return nil, err
	}
	if in.Cursor != "" && in.Cursor != "null" {
		cur, err := decodeCursor(in.Cursor)
		if err != nil {
			return nil, huma.Error422UnprocessableEntity("invalid cursor: " + err.Error())
		}
		q.CursorTs = &cur.Ts
		q.CursorFp = &cur.Fp
	}

	result, err := h.reader.ListSeries(ctx, q)
	if err != nil {
		return nil, mapReadError(err)
	}

	body := SeriesPage{Series: result.Series}
	if result.NextCursor != nil {
		encoded := encodeCursor(*result.NextCursor)
		body.NextPageCursor = &encoded
	}
	return &ListSeriesOutput{Body: body}, nil
}

// setIfNonEmpty points dst at v when v is non-empty, leaving dst nil otherwise so an
// absent query parameter stays an unconstrained (nil) filter for the service.
func setIfNonEmpty(dst **string, v string) {
	if v != "" {
		*dst = &v
	}
}

// parseUTCBound parses an optional RFC3339 active-window bound into dst, normalizing
// an offset input to UTC (the storage column is timestamp-without-time-zone under the
// UTC convention). An empty value leaves dst nil; a malformed value is a 422.
func parseUTCBound(value, field string, dst **time.Time) error {
	if value == "" {
		return nil
	}
	ts, err := time.Parse(time.RFC3339, value)
	if err != nil {
		return huma.Error422UnprocessableEntity("invalid " + field + ": " + err.Error())
	}
	utc := ts.UTC()
	*dst = &utc
	return nil
}

// cursorSeparator splits the encoded cursor's timestamp from its fingerprint. A
// fingerprint is hex, so '|' never collides with the fingerprint bytes.
const cursorSeparator = "|"

// encodeCursor renders a structured cursor as the opaque token returned to clients:
// base64(std) of "<RFC3339Nano>|<fingerprint>". The matching decodeCursor is the
// only place the service-facing (timestamp, fingerprint) pair is reconstructed.
func encodeCursor(c service.SeriesCursor) string {
	raw := c.Ts.UTC().Format(time.RFC3339Nano) + cursorSeparator + c.Fp
	return base64.StdEncoding.EncodeToString([]byte(raw))
}

// decodeCursor reverses encodeCursor. A token that is not valid base64, is missing
// the separator, or carries an unparseable timestamp is an error the handler maps to
// a 422; the timestamp is normalized to UTC.
func decodeCursor(token string) (*service.SeriesCursor, error) {
	decoded, err := base64.StdEncoding.DecodeString(token)
	if err != nil {
		return nil, err
	}
	tsStr, fp, found := strings.Cut(string(decoded), cursorSeparator)
	if !found {
		return nil, &cursorError{reason: "missing separator"}
	}
	ts, err := time.Parse(time.RFC3339Nano, tsStr)
	if err != nil {
		return nil, err
	}
	return &service.SeriesCursor{Ts: ts.UTC(), Fp: fp}, nil
}

// cursorError reports a structurally invalid cursor (valid base64 but not a
// "<timestamp>|<fingerprint>" payload).
type cursorError struct {
	reason string
}

// Error returns the bare reason; the handler prefixes "invalid cursor: " when it
// renders the 422, so this must not repeat a "cursor" prefix.
func (e *cursorError) Error() string {
	return e.reason
}
