package api_test

import (
	"encoding/json"
	"net/http"
	"testing"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/service"
)

// seriesPage is the GET /api/series wire body, decoded for assertions. It mirrors
// api.SeriesPage but lives in the test package so the test reads the JSON contract
// (series array + opaque cursor) the SPA consumes.
type seriesPage struct {
	Series         []service.SeriesListItem `json:"series"`
	NextPageCursor *string                  `json:"next_page_cursor"`
}

// listSeries GETs the series list and asserts a 200, returning the decoded page.
func listSeries(t *testing.T, tapi humatest.TestAPI, query string) seriesPage {
	t.Helper()
	resp := tapi.Get("/api/series" + query)
	require.Equal(t, http.StatusOK, resp.Code, "list series: %s", resp.Body.String())
	var page seriesPage
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &page))
	return page
}

// noisyBaseline is the verified in-band baseline from the service fixtures: seven
// noisy points around 1.0 whose preceding-member distribution scores a within-band
// latest as "stable" and a 1.20 latest as "regressed" (unit "s", less-is-better).
var noisyBaseline = []float64{1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.01}

// seedSeriesWithLatest seeds one series (case = name) with the noisy baseline at
// days 0..6 followed by a single latest measurement at day(latestDay). It returns
// the latest member's result id so identity assertions can pin latest_result_id.
func seedSeriesWithLatest(t *testing.T, tapi humatest.TestAPI, name string, latest float64, latestDay int) string {
	t.Helper()
	for i, v := range noisyBaseline {
		seedResult(t, tapi, seedOpts{name: name, sha: name + shaN(i), ts: day(i), data: []float64{v}})
	}
	return seedResult(t, tapi,
		seedOpts{name: name, sha: name + shaN(latestDay), ts: day(latestDay), data: []float64{latest}})
}

// findSeries returns the page row for the given case name, failing if absent.
func findSeries(t *testing.T, page seriesPage, name string) service.SeriesListItem {
	t.Helper()
	for _, s := range page.Series {
		if s.Name == name {
			return s
		}
	}
	require.FailNowf(t, "series not found", "no series named %q in %d rows", name, len(page.Series))
	return service.SeriesListItem{}
}

// TestListSeriesStatusAndIdentity seeds a regressed series, a stable series, and a
// single-point insufficient series and asserts the derived status plus the identity
// fields on the wire row. The latest commit days are staggered so DESC ordering is
// deterministic, and the page is non-full so next_page_cursor is null.
func TestListSeriesStatusAndIdentity(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	regressedID := seedSeriesWithLatest(t, tapi, "regressed-bench", 1.20, 7)
	seedSeriesWithLatest(t, tapi, "stable-bench", 1.005, 7)
	// A single-point series has no baseline, so its status is "insufficient".
	soloID := seedResult(t, tapi, seedOpts{name: "solo-bench", sha: "solo1", ts: day(1), data: []float64{5}})

	page := listSeries(t, tapi, "")
	require.Len(t, page.Series, 3)
	assert.Nil(t, page.NextPageCursor, "non-full page has no next cursor")

	regressed := findSeries(t, page, "regressed-bench")
	assert.Equal(t, "regressed", regressed.Status)
	stable := findSeries(t, page, "stable-bench")
	assert.Equal(t, "stable", stable.Status)
	solo := findSeries(t, page, "solo-bench")
	assert.Equal(t, "insufficient", solo.Status)
	assert.Equal(t, soloID, solo.LatestResultID, "single-point latest result id")

	// Identity fields on the regressed series.
	assert.Equal(t, "regressed-bench", regressed.Name)
	assert.Equal(t, "regressed-bench", regressed.Tags["name"], "case name folded into tags")
	assert.Equal(t, "test", regressed.Tags["source"], "permutation tag preserved")
	assert.Equal(t, "gcc", regressed.Context["compiler"])
	assert.Equal(t, "m1", regressed.Hardware.Name)
	assert.Equal(t, defaultRepo, regressed.Repository)
	require.NotNil(t, regressed.Unit)
	assert.Equal(t, "s", *regressed.Unit)
	require.NotNil(t, regressed.LessIsBetter)
	assert.True(t, *regressed.LessIsBetter, "seconds: less is better")
	assert.Equal(t, regressedID, regressed.LatestResultID)
	assert.Equal(t, "regressed-bench"+shaN(7), regressed.LatestCommitSha)
	assert.Equal(t, int64(8), regressed.PointCount, "seven baseline points plus the latest")
	require.NotNil(t, regressed.LatestSVS)
	assert.InDelta(t, 1.20, *regressed.LatestSVS, 1e-9)
	require.NotNil(t, regressed.LatestSVSType)
	assert.Equal(t, "min", *regressed.LatestSVSType, "seconds: best-mode SVS is the min")
	assert.True(t, regressed.LatestResultTimestamp.Equal(day(7)), "latest result timestamp")
}

// TestListSeriesSparklineOldestFirst asserts the sparkline carries the per-member
// single value summaries in oldest-to-newest order (the storage layer orders
// members by commit timestamp ascending, and the service preserves that).
func TestListSeriesSparklineOldestFirst(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	// Strictly increasing values so an out-of-order sparkline is detectable.
	values := []float64{1, 2, 3, 4}
	for i, v := range values {
		seedResult(t, tapi, seedOpts{name: "spark", sha: shaN(i), ts: day(i), data: []float64{v}})
	}
	page := listSeries(t, tapi, "")
	s := findSeries(t, page, "spark")
	require.Len(t, s.Sparkline, len(values))
	for i, want := range values {
		assert.InDeltaf(t, want, s.Sparkline[i], 1e-9, "sparkline[%d] oldest-first", i)
	}
}

// TestListSeriesMixedUnit asserts a series whose members span two units returns a
// null unit, null less_is_better, and an "insufficient" status (no single unit to
// score against), matching the service fixture rule.
func TestListSeriesMixedUnit(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	// One fingerprint (constant case/hardware/repo), members split across units.
	for i, v := range noisyBaseline {
		seedResult(t, tapi, seedOpts{sha: shaN(i), ts: day(i), unit: "s", data: []float64{v}})
	}
	// A later member in a different unit makes the series mixed-unit.
	seedResult(t, tapi, seedOpts{sha: shaN(7), ts: day(7), unit: "ns", data: []float64{1.2}})

	page := listSeries(t, tapi, "")
	require.Len(t, page.Series, 1)
	s := page.Series[0]
	assert.Nil(t, s.Unit, "mixed unit -> null unit")
	assert.Nil(t, s.LessIsBetter, "mixed unit -> null less_is_better")
	assert.Equal(t, "insufficient", s.Status, "mixed unit -> insufficient")
}

// TestListSeriesCursorRoundTrip walks every page one row at a time via the opaque
// next_page_cursor and asserts every series is visited exactly once (no dupes, no
// gaps). With page_size=1 the last data row fills its page, so the cursor convention
// (a full page always yields a cursor) emits one trailing empty page whose cursor is
// null; the walk stops on that empty page.
func TestListSeriesCursorRoundTrip(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	// Three single-point series at distinct latest days so ordering is total.
	names := []string{"alpha", "beta", "gamma"}
	for i, name := range names {
		seedResult(t, tapi, seedOpts{name: name, sha: name + "1", ts: day(i + 1), data: []float64{float64(i + 1)}})
	}

	// Reference order from a single large page.
	full := listSeries(t, tapi, "?page_size=50")
	require.Len(t, full.Series, 3)
	want := []string{full.Series[0].Name, full.Series[1].Name, full.Series[2].Name}

	var got []string
	cursor := ""
	for step := 0; step <= len(names); step++ { // at most one extra (empty) page
		query := "?page_size=1"
		if cursor != "" {
			query += "&cursor=" + cursor
		}
		p := listSeries(t, tapi, query)
		if len(p.Series) == 0 {
			assert.Nil(t, p.NextPageCursor, "trailing empty page has a null cursor")
			break
		}
		require.Len(t, p.Series, 1, "non-empty page yields exactly one row")
		got = append(got, p.Series[0].Name)
		require.NotNil(t, p.NextPageCursor, "a full page returns a cursor")
		cursor = *p.NextPageCursor
	}
	assert.Equal(t, want, got, "cursor walk reproduces single-page order")
	assert.ElementsMatch(t, names, got, "every series visited exactly once")
}

// TestListSeriesMalformedCursorIs422 asserts every malformed cursor 422s rather
// than 500s: a non-base64 token, a base64 blob without the "<ts>|<fp>" separator,
// and a base64 blob that has the separator but an unparseable timestamp.
func TestListSeriesMalformedCursorIs422(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	cases := []struct {
		cursor   string
		wantBody string
	}{
		{"not-a-cursor", "invalid cursor"},                        // not base64
		{"bm9zZXBhcmF0b3I=", "invalid cursor: missing separator"}, // base64("noseparator")
		{"bm90YXRpbWV8ZGVhZGJlZWY=", "invalid cursor"},            // base64("notatime|deadbeef")
	}
	for _, c := range cases {
		resp := tapi.Get("/api/series?cursor=" + c.cursor)
		require.Equalf(t, http.StatusUnprocessableEntity, resp.Code,
			"cursor %q must 422; body %s", c.cursor, resp.Body.String())
		assert.Contains(t, resp.Body.String(), c.wantBody)
		assert.NotContains(t, resp.Body.String(), "malformed cursor:",
			"the doubled prefix must not reappear")
	}
}

// TestListSeriesBadActiveSinceIs422 asserts a non-RFC3339 active_since 422s.
func TestListSeriesBadActiveSinceIs422(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	resp := tapi.Get("/api/series?active_since=not-a-date")
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())
}

// TestListSeriesActiveSinceUTCNormalized asserts active_since with a non-UTC offset
// is normalized to UTC before bounding the latest commit timestamp, mirroring the
// list endpoint. The series' latest commit is day(0) == 2026-01-01T00:00:00Z; an
// offset bound resolving to before that instant must include it.
func TestListSeriesActiveSinceUTCNormalized(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	seedResult(t, tapi, seedOpts{name: "since-bench", sha: "since1", ts: day(0), data: []float64{10}})
	// 2026-01-01T04:00:00+05:00 == 2025-12-31T23:00:00Z, before the day(0) commit, so
	// the series is active since that instant. A naive wall-clock 04:00 would exclude it.
	page := listSeries(t, tapi, "?active_since=2026-01-01T04:00:00%2B05:00")
	require.Len(t, page.Series, 1, "UTC-normalized lower bound must include the series")
	assert.Equal(t, "since-bench", page.Series[0].Name)
}

// TestListSeriesFingerprintFilter asserts the fingerprint filter returns exactly the
// one matching series.
func TestListSeriesFingerprintFilter(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	wantID := seedResult(t, tapi, seedOpts{name: "fp-a", sha: "fpa1", ts: day(1), data: []float64{1}})
	seedResult(t, tapi, seedOpts{name: "fp-b", sha: "fpb1", ts: day(2), data: []float64{2}})
	fp := fpForResult(t, tapi, wantID)

	page := listSeries(t, tapi, "?fingerprint="+fp)
	require.Len(t, page.Series, 1)
	assert.Equal(t, "fp-a", page.Series[0].Name)
	assert.Equal(t, fp, page.Series[0].HistoryFingerprint)
}

// TestListSeriesEmptyResult asserts a filter matching nothing returns 200 with an
// empty (non-null) JSON array and a null cursor.
func TestListSeriesEmptyResult(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	seedResult(t, tapi, seedOpts{name: "present", sha: "p1", ts: day(1), data: []float64{1}})

	resp := tapi.Get("/api/series?fingerprint=does-not-exist")
	require.Equal(t, http.StatusOK, resp.Code, "body %s", resp.Body.String())
	// The body must serialize "series" as [] (a JSON array), never null.
	assert.Contains(t, resp.Body.String(), `"series":[]`, "empty page is an array, not null")

	page := listSeries(t, tapi, "?fingerprint=does-not-exist")
	assert.Empty(t, page.Series)
	assert.Nil(t, page.NextPageCursor)
}

// TestListSeriesPaginationCursorContinues seeds more than one page of series and
// asserts page 2 (via the cursor) continues where page 1 stopped with no overlap.
func TestListSeriesPaginationCursorContinues(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	const total = 5
	for i := range total {
		name := "series-" + shaN(i)
		seedResult(t, tapi, seedOpts{name: name, sha: name + "1", ts: day(i + 1), data: []float64{float64(i + 1)}})
	}

	page1 := listSeries(t, tapi, "?page_size=3")
	require.Len(t, page1.Series, 3)
	require.NotNil(t, page1.NextPageCursor, "full page returns a cursor")

	page2 := listSeries(t, tapi, "?page_size=3&cursor="+*page1.NextPageCursor)
	require.Len(t, page2.Series, total-3)
	assert.Nil(t, page2.NextPageCursor, "final partial page has no cursor")

	// No overlap and full coverage across the two pages.
	seen := map[string]bool{}
	for _, s := range append(page1.Series, page2.Series...) {
		require.Falsef(t, seen[s.Name], "series %q appears on both pages", s.Name)
		seen[s.Name] = true
	}
	assert.Len(t, seen, total, "every series covered across the two pages")
}
