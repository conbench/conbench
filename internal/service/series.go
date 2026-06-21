package service

import (
	"context"
	"fmt"
	"time"

	"github.com/conbench/conbench/internal/stats"
	"github.com/conbench/conbench/internal/storage"
)

// SeriesStatus values. error-no-data is reserved (not emitted by v1) and
// deliberately absent from the wire enum; Phase 5 extends the enum when the
// expected-set surface lands, and clients regenerate with it. Keep these in
// sync with the enum tag on SeriesListItem.Status.
const (
	statusRegressed    = "regressed"
	statusImproved     = "improved"
	statusStable       = "stable"
	statusInsufficient = "insufficient"
)

// seriesSparklineLen is the number of trailing single value summaries kept on a
// series row for the dashboard sparkline.
const seriesSparklineLen = 20

// SeriesListItem is one row of GET /api/series.
type SeriesListItem struct {
	HistoryFingerprint    string         `json:"history_fingerprint"`
	Name                  string         `json:"name"`
	Tags                  map[string]any `json:"tags"`
	Context               map[string]any `json:"context"`
	Hardware              Hardware       `json:"hardware"`
	Repository            string         `json:"repository"`
	Unit                  *string        `json:"unit"`
	LessIsBetter          *bool          `json:"less_is_better"`
	Status                string         `json:"status" enum:"regressed,improved,stable,insufficient"`
	LatestResultID        string         `json:"latest_result_id"`
	LatestSVS             *float64       `json:"latest_single_value_summary"`
	LatestSVSType         *string        `json:"latest_single_value_summary_type"`
	LatestCommitSha       string         `json:"latest_commit_sha"`
	LatestCommitTimestamp time.Time      `json:"latest_commit_timestamp"`
	LatestResultTimestamp time.Time      `json:"latest_result_timestamp"`
	PointCount            int64          `json:"point_count"`
	Sparkline             []float64      `json:"sparkline"`
}

// SeriesQuery is the parsed, structured list input. CursorTs/CursorFp are the
// structured cursor fields; the API layer owns the opaque string encoding, so the
// service never parses or emits an encoded cursor.
type SeriesQuery struct {
	Q           *string
	Hardware    *string
	Repository  *string
	Fingerprint *string
	ActiveSince *time.Time
	ActiveUntil *time.Time
	CursorTs    *time.Time
	CursorFp    *string
	PageSize    int
}

// SeriesCursor is the structured pagination cursor (the last row's ordering key).
type SeriesCursor struct {
	Ts time.Time
	Fp string
}

// SeriesResult is what ListSeries returns: the page items plus the structured next
// cursor, non-nil only when the page was full.
type SeriesResult struct {
	Series     []SeriesListItem
	NextCursor *SeriesCursor
}

// seriesIdentityUnit derives the series' unit and orientation together. The unit
// must be shared by every member and recognized by the units registry; otherwise
// both are null (and status reads insufficient) — a raw, unvalidated unit is
// never surfaced as series identity.
func seriesIdentityUnit(members []storage.HistoryRow) (*string, *bool) {
	unit := seriesUnit(members)
	lessIsBetter := lessIsBetterPtr(unit)
	if lessIsBetter == nil {
		return nil, nil
	}
	return unit, lessIsBetter
}

// seriesUnit returns the single unit shared by all members, or nil when the
// series spans multiple units (or is empty). Mirrors History()'s single-unit rule.
func seriesUnit(members []storage.HistoryRow) *string {
	if len(members) == 0 {
		return nil
	}
	first := members[0].Unit
	for _, m := range members {
		if !sameUnitPtr(first, m.Unit) {
			return nil
		}
	}
	return first
}

// seriesStatus derives the four-value status by scoring the latest member against
// the distribution of the PRECEDING members — the same lookback computation the
// compare endpoint performs (BaselineDistribution -> ZScore -> LookbackZVerdict).
// Excluding the latest from its own baseline is essential: a worsening latest point
// is itself a distribution step, so scoring it against a window that includes it
// would null its residual and miss the regression. A mixed/unknown unit, a
// too-short or zero-variance baseline, or an uncomputable z yields "insufficient".
func seriesStatus(members []storage.HistoryRow, unit *string, lessIsBetter *bool) string {
	if unit == nil || lessIsBetter == nil || len(members) < 2 {
		return statusInsufficient
	}
	latest := members[len(members)-1]
	latestSVS, _, err := historySVS(latest.Unit, latest.Data)
	if err != nil {
		return statusInsufficient
	}
	points := make([]stats.SeriesPoint, 0, len(members)-1)
	for _, m := range members[:len(members)-1] { // baseline = members before the latest
		svs, _, err := historySVS(m.Unit, m.Data)
		if err != nil {
			return statusInsufficient
		}
		p, err := seriesPointFromRow(m, svs)
		if err != nil {
			return statusInsufficient
		}
		points = append(points, p)
	}
	mean, stddev := stats.BaselineDistribution(points, stats.DistributionCommitsDefault)
	z := stats.ZScore(&latestSVS, *lessIsBetter, mean, stddev)
	v := stats.LookbackZVerdict(z, stats.ZScoreThresholdDefault)
	switch {
	case v == nil:
		return statusInsufficient
	case v.RegressionIndicated:
		return statusRegressed
	case v.ImprovementIndicated:
		return statusImproved
	default:
		return statusStable
	}
}

// seriesSparkline returns the single value summaries of the last
// seriesSparklineLen members, oldest of that window first. Members whose SVS is
// uncomputable (empty data or unknown unit) are skipped so a single bad row never
// drops the whole sparkline; this is a display-only aid, not the status input.
func seriesSparkline(members []storage.HistoryRow) []float64 {
	start := 0
	if len(members) > seriesSparklineLen {
		start = len(members) - seriesSparklineLen
	}
	tail := members[start:]
	out := make([]float64, 0, len(tail))
	for _, m := range tail {
		svs, _, err := historySVS(m.Unit, m.Data)
		if err != nil {
			continue
		}
		out = append(out, svs)
	}
	return out
}

// ListSeries returns one filtered, cursor-paginated page of series. For each page
// row it derives the unit/orientation/status from the row's recent member tail,
// the latest single value summary from the row's latest measurement, and the
// sparkline from the trailing members. The next cursor is set only when the page
// is full; the service performs no cursor string encoding (the API layer owns
// that).
func (r *Reader) ListSeries(ctx context.Context, q SeriesQuery) (*SeriesResult, error) {
	pageSize := q.PageSize
	if pageSize <= 0 {
		pageSize = listPageSizeDefault
	}
	if pageSize > listPageSizeMax {
		pageSize = listPageSizeMax
	}

	rows, err := r.store.SelectSeriesPage(ctx, storage.SeriesListParams{
		Q:           q.Q,
		Hardware:    q.Hardware,
		Repository:  q.Repository,
		Fingerprint: q.Fingerprint,
		ActiveSince: q.ActiveSince,
		ActiveUntil: q.ActiveUntil,
		CursorTs:    q.CursorTs,
		CursorFp:    q.CursorFp,
		PageSize:    int32(pageSize),
	})
	if err != nil {
		return nil, fmt.Errorf("list series: %w", err)
	}

	fingerprints := make([]string, len(rows))
	for i, row := range rows {
		fingerprints[i] = row.HistoryFingerprint
	}
	members, err := r.store.SelectSeriesMembers(ctx, fingerprints)
	if err != nil {
		return nil, fmt.Errorf("list series members: %w", err)
	}
	byFingerprint := groupMembersByFingerprint(members)

	items := make([]SeriesListItem, 0, len(rows))
	for _, row := range rows {
		item, err := seriesListItem(row, byFingerprint[row.HistoryFingerprint])
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}

	result := &SeriesResult{Series: items}
	if len(items) == pageSize {
		last := rows[len(rows)-1]
		result.NextCursor = &SeriesCursor{Ts: last.LatestCommitTimestamp, Fp: last.HistoryFingerprint}
	}
	return result, nil
}

// groupMembersByFingerprint partitions members by fingerprint in a single pass.
// SelectSeriesMembers orders rows by (fingerprint, commit timestamp ascending),
// so each fingerprint's returned member tail is contiguous and stays in
// oldest-commit-first order.
func groupMembersByFingerprint(members []storage.HistoryRow) map[string][]storage.HistoryRow {
	out := make(map[string][]storage.HistoryRow)
	for _, m := range members {
		out[m.HistoryFingerprint] = append(out[m.HistoryFingerprint], m)
	}
	return out
}

// seriesListItem assembles one list row from its page row and its ordered members.
func seriesListItem(row storage.SeriesPageRow, members []storage.HistoryRow) (SeriesListItem, error) {
	unit, lessIsBetter := seriesIdentityUnit(members)

	tags, err := jsonObject(row.CaseTags)
	if err != nil {
		return SeriesListItem{}, err
	}
	if tags == nil {
		tags = map[string]any{}
	}
	tags["name"] = row.CaseName // legacy folds the case name back into tags

	contextTags, err := jsonObject(row.ContextTags)
	if err != nil {
		return SeriesListItem{}, err
	}

	latestSVS, latestSVSType := latestSeriesSVS(row.LatestUnit, row.LatestData)

	return SeriesListItem{
		HistoryFingerprint: row.HistoryFingerprint,
		Name:               row.CaseName,
		Tags:               tags,
		Context:            contextTags,
		Hardware: Hardware{
			ID:   row.HardwareID,
			Type: row.HardwareType,
			Name: row.HardwareName,
			Hash: row.HardwareHash,
		},
		Repository:            row.CommitRepoUrl,
		Unit:                  unit,
		LessIsBetter:          lessIsBetter,
		Status:                seriesStatus(members, unit, lessIsBetter),
		LatestResultID:        row.LatestResultID,
		LatestSVS:             latestSVS,
		LatestSVSType:         latestSVSType,
		LatestCommitSha:       row.LatestCommitSha,
		LatestCommitTimestamp: row.LatestCommitTimestamp,
		LatestResultTimestamp: row.LatestResultTimestamp,
		PointCount:            row.PointCount,
		Sparkline:             seriesSparkline(members),
	}, nil
}

// latestSeriesSVS computes the latest measurement's single value summary and its
// type, or nils when it is not computable (empty data or an unknown unit). The
// latest member is non-errored with data, so this is normally present; the nil
// path guards a series whose latest unit the registry does not recognize.
func latestSeriesSVS(unit *string, data []float64) (*float64, *string) {
	if unit == nil || len(data) == 0 {
		return nil, nil
	}
	v, svsType, err := historySVS(unit, data)
	if err != nil {
		return nil, nil
	}
	return &v, &svsType
}
