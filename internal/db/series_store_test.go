package db_test

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/storage"
)

// day returns a fixed UTC commit timestamp n days after a base date, used to
// order series members deterministically.
func day(n int) time.Time {
	return time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC).AddDate(0, 0, n)
}

// seriesMember describes one history member to seed: its commit timestamp, the
// single data point, whether it is errored, and whether it sits off the default
// branch (sha != fork_point_sha). Off-branch and errored members must be
// excluded from membership.
type seriesMember struct {
	ts        time.Time
	value     float64
	errored   bool
	offBranch bool
}

// defaultSeriesRepo is the commit repo URL seedSeries uses unless a test needs a
// distinct repository (seedSeriesRepo).
const defaultSeriesRepo = "https://github.com/org/repo"

// seedSeries seeds one benchmark series: a case (name + tags), a hardware, and
// one member per element of members. Distinct (caseName, hwName) yields a
// distinct history_fingerprint, which the test passes explicitly so cursor and
// filter assertions can reference it. Each member gets its own commit so commit
// timestamps drive series ordering.
func seedSeries(
	t *testing.T,
	st *db.Store,
	ctx context.Context,
	fp, caseName, caseTags, hwName string,
	members []seriesMember,
) {
	t.Helper()
	seedSeriesRepo(t, st, ctx, fp, caseName, caseTags, hwName, defaultSeriesRepo, members)
}

// seedSeriesRepo is seedSeries with an explicit commit repo URL, for tests that
// exercise the repository filter.
func seedSeriesRepo(
	t *testing.T,
	st *db.Store,
	ctx context.Context,
	fp, caseName, caseTags, hwName, repo string,
	members []seriesMember,
) {
	t.Helper()
	caseID, err := st.GetOrCreateCase(ctx, caseName, []byte(caseTags))
	mustID(t, caseID, err)
	contextID, err := st.GetOrCreateContext(ctx, []byte(`{}`))
	mustID(t, contextID, err)
	infoID, err := st.GetOrCreateInfo(ctx, []byte(`{}`))
	mustID(t, infoID, err)
	hardwareID, err := st.GetOrCreateHardware(ctx, machineParams(hwName))
	mustID(t, hardwareID, err)

	for i, m := range members {
		mkSha := "sha-" + hwName + "-" + caseName + "-" + sha(i)
		fork := mkSha // default branch: sha == fork_point_sha
		if m.offBranch {
			fork = "other-" + mkSha // off default branch: sha != fork_point_sha
		}
		ts := m.ts
		commitID, err := st.GetOrCreateCommit(ctx, storage.InsertCommitParams{
			Sha: mkSha, Repository: repo, Message: "", AuthorName: "",
			ForkPointSha: new(fork), Timestamp: new(ts),
		})
		mustID(t, commitID, err)
		var errBytes []byte
		if m.errored {
			errBytes = []byte(`{"x":1}`)
		}
		id, err := st.InsertBenchmarkResult(ctx, storage.InsertBenchmarkResultParams{
			CaseID: caseID, ContextID: contextID, InfoID: infoID, HardwareID: hardwareID,
			RunID: "run", RunTags: []byte(`{"name":"b"}`), CommitID: new(commitID),
			CommitRepoUrl: repo, HistoryFingerprint: fp,
			Timestamp: m.ts, Unit: new("s"), Data: []*float64{new(m.value)}, Error: errBytes,
		})
		mustID(t, id, err)
	}
}

// sha renders a small integer as a stable two-digit suffix for commit shas.
func sha(i int) string {
	return string(rune('a'+i/10)) + string(rune('0'+i%10))
}

// indexByCaseName keys a series page by case name for assertion lookups.
func indexByCaseName(page []storage.SeriesPageRow) map[string]storage.SeriesPageRow {
	out := make(map[string]storage.SeriesPageRow, len(page))
	for _, r := range page {
		out[r.CaseName] = r
	}
	return out
}

// TestSelectSeriesPage covers the series-list query: one row per fingerprint,
// the newest-commit member as latest, point_count over members only, identity
// columns, DESC ordering by latest commit timestamp, and all filters.
func TestSelectSeriesPage(t *testing.T) {
	st, _, ctx := newTestStore(t)

	// Series A: case "tpch-q1" on hw "m5", three default-branch members; the
	// day(2) member is newest. Tags carry a searchable value ("scale":"sf10").
	seedSeries(t, st, ctx, "fp-a", "tpch-q1", `{"scale":"sf10"}`, "m5", []seriesMember{
		{ts: day(0), value: 1.0},
		{ts: day(1), value: 1.1},
		{ts: day(2), value: 1.2},
	})
	// Series B: case "read-pq" on hw "m5", one member on day(1).
	seedSeries(t, st, ctx, "fp-b", "read-pq", `{}`, "m5", []seriesMember{
		{ts: day(1), value: 0.4},
	})

	page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{PageSize: 50})
	require.NoError(t, err)
	require.Len(t, page, 2, "one row per fingerprint")

	byName := indexByCaseName(page)
	a := byName["tpch-q1"]
	assert.Equal(t, int64(3), a.PointCount, "point_count counts all members")
	assert.Equal(t, "m5", a.HardwareName)
	assert.Equal(t, "fp-a", a.HistoryFingerprint)
	require.NotNil(t, a.LatestUnit)
	assert.Equal(t, "s", *a.LatestUnit)
	require.Len(t, a.LatestData, 1)
	assert.InDelta(t, 1.2, a.LatestData[0], 1e-9, "latest is the newest-commit member")
	assert.True(t, a.LatestCommitTimestamp.Equal(day(2)), "latest commit timestamp is day(2)")
	assert.Equal(t, "https://github.com/org/repo", a.CommitRepoUrl)
	assert.JSONEq(t, `{"scale":"sf10"}`, string(a.CaseTags))

	b := byName["read-pq"]
	assert.Equal(t, int64(1), b.PointCount)
	assert.True(t, b.LatestCommitTimestamp.Equal(day(1)))

	// Ordering: A's latest (day 2) is newer than B's latest (day 1), so A first.
	assert.Equal(t, "tpch-q1", page[0].CaseName, "ordered by latest commit timestamp DESC")
	assert.Equal(t, "read-pq", page[1].CaseName)
}

// TestSelectSeriesPageMembershipExclusions asserts an errored member and a
// non-default-branch member neither count toward point_count nor become latest.
func TestSelectSeriesPageMembershipExclusions(t *testing.T) {
	st, _, ctx := newTestStore(t)

	// A later errored member (day 3) and a later off-branch member (day 4) must
	// be excluded; the newest valid member is day(2), and point_count is 2.
	seedSeries(t, st, ctx, "fp-x", "case-x", `{}`, "m5", []seriesMember{
		{ts: day(1), value: 1.0},
		{ts: day(2), value: 2.0},
		{ts: day(3), value: 9.0, errored: true},
		{ts: day(4), value: 9.0, offBranch: true},
	})

	page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{PageSize: 50})
	require.NoError(t, err)
	require.Len(t, page, 1)
	row := page[0]
	assert.Equal(t, int64(2), row.PointCount, "errored/off-branch excluded from count")
	assert.True(t, row.LatestCommitTimestamp.Equal(day(2)),
		"latest must be the newest valid member, not the later errored/off-branch ones")
	require.Len(t, row.LatestData, 1)
	assert.InDelta(t, 2.0, row.LatestData[0], 1e-9)
}

// TestSelectSeriesPageQFilter asserts q matches case NAME and case TAGS text,
// case-insensitively.
func TestSelectSeriesPageQFilter(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-name", "tpch-scale-q1", `{"k":"v"}`, "m5", []seriesMember{{ts: day(0), value: 1}})
	seedSeries(t, st, ctx, "fp-tag", "read-parquet", `{"scale":"sf100"}`, "m5", []seriesMember{{ts: day(0), value: 1}})
	seedSeries(t, st, ctx, "fp-none", "write-csv", `{"k":"v"}`, "m5", []seriesMember{{ts: day(0), value: 1}})

	// "scale" matches "tpch-scale-q1" by name and "read-parquet" by tag value.
	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Q: new("scale"), PageSize: 50})
	require.NoError(t, err)
	names := map[string]bool{}
	for _, r := range got {
		names[r.CaseName] = true
	}
	assert.Equal(t, map[string]bool{"tpch-scale-q1": true, "read-parquet": true}, names,
		"q matches case name and case tags text")

	// Case-insensitive: "SCALE" matches the same two.
	gotUpper, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Q: new("SCALE"), PageSize: 50})
	require.NoError(t, err)
	assert.Len(t, gotUpper, 2, "q is case-insensitive")

	// "sf100" appears only as a tag VALUE (no case name or tag key contains it),
	// proving the params text search reaches values, not just keys.
	byValue, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Q: new("sf100"), PageSize: 50})
	require.NoError(t, err)
	require.Len(t, byValue, 1, "tag value matches exactly one series")
	assert.Equal(t, "read-parquet", byValue[0].CaseName)
}

func TestSelectSeriesPageSparseLatestCommitsFillsRequestedPage(t *testing.T) {
	st, _, ctx := newTestStore(t)

	for i := range 40 {
		seedSeries(t, st, ctx,
			"fp-sparse-"+sha(i),
			"sparse-"+sha(i),
			`{}`,
			"m5",
			[]seriesMember{{ts: day(i), value: float64(i + 1)}},
		)
	}

	page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{PageSize: 35})

	require.NoError(t, err)
	require.Len(t, page, 35)
	assert.Equal(t, "sparse-d9", page[0].CaseName)
	assert.Equal(t, "sparse-a5", page[34].CaseName)
}

func TestSelectSeriesPageRepeatedRecentFingerprintDoesNotHideOlderSeries(t *testing.T) {
	st, _, ctx := newTestStore(t)

	repeatedMembers := make([]seriesMember, 40)
	for i := range repeatedMembers {
		repeatedMembers[i] = seriesMember{ts: day(10 + i), value: float64(i + 1)}
	}
	seedSeries(t, st, ctx, "fp-active", "active-series", `{}`, "m5", repeatedMembers)
	seedSeries(t, st, ctx, "fp-older", "older-series", `{}`, "m5", []seriesMember{
		{ts: day(0), value: 1},
	})

	page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{PageSize: 2})

	require.NoError(t, err)
	require.Len(t, page, 2, "older distinct series must not be hidden by repeated recent commits for one fingerprint")
	assert.Equal(t, "active-series", page[0].CaseName)
	assert.Equal(t, "older-series", page[1].CaseName)
}

func TestSelectSeriesPageQFilterFindsOlderSeriesOutsideRecentWindow(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-needle", "needle-benchmark", `{"kind":"needle"}`, "m5",
		[]seriesMember{{ts: day(0), value: 1}})
	for i := range 40 {
		seedSeries(t, st, ctx,
			"fp-haystack-"+sha(i),
			"haystack-"+sha(i),
			`{"kind":"haystack"}`,
			"m5",
			[]seriesMember{{ts: day(10 + i), value: float64(i + 1)}},
		)
	}

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Q: new("needle"), PageSize: 50})

	require.NoError(t, err)
	require.Len(t, got, 1)
	assert.Equal(t, "fp-needle", got[0].HistoryFingerprint)
}

func TestSelectSeriesPageQFilterCursorWalk(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-1", "needle-1", `{"kind":"needle"}`, "m5", []seriesMember{{ts: day(1), value: 1}})
	seedSeries(t, st, ctx, "fp-2", "needle-2", `{"kind":"needle"}`, "m5", []seriesMember{{ts: day(2), value: 1}})
	seedSeries(t, st, ctx, "fp-3", "needle-3", `{"kind":"needle"}`, "m5", []seriesMember{{ts: day(2), value: 1}})
	seedSeries(t, st, ctx, "fp-4", "needle-4", `{"kind":"needle"}`, "m5", []seriesMember{
		{ts: day(0), value: 1},
		{ts: day(3), value: 2},
	})
	seedSeries(t, st, ctx, "fp-other", "other", `{"kind":"other"}`, "m5", []seriesMember{{ts: day(4), value: 1}})

	full, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Q: new("needle"), PageSize: 50})
	require.NoError(t, err)
	require.Len(t, full, 4)
	wantOrder := make([]string, len(full))
	for i, r := range full {
		wantOrder[i] = r.HistoryFingerprint
	}

	var gotOrder []string
	var cursorTs *time.Time
	var cursorFp *string
	for range full {
		page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
			Q: new("needle"), CursorTs: cursorTs, CursorFp: cursorFp, PageSize: 1,
		})
		require.NoError(t, err)
		require.Len(t, page, 1)
		row := page[0]
		gotOrder = append(gotOrder, row.HistoryFingerprint)
		ts := row.LatestCommitTimestamp
		cursorTs = &ts
		cursorFp = new(row.HistoryFingerprint)
	}

	assert.Equal(t, wantOrder, gotOrder)
	assert.ElementsMatch(t, []string{"fp-1", "fp-2", "fp-3", "fp-4"}, gotOrder)
	assert.NotEqual(t, gotOrder[0], gotOrder[1], "cursor must not re-emit a multi-member series through its older member")

	last := full[len(full)-1]
	lastTs := last.LatestCommitTimestamp
	empty, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		Q: new("needle"), CursorTs: &lastTs, CursorFp: new(last.HistoryFingerprint), PageSize: 1,
	})
	require.NoError(t, err)
	assert.Empty(t, empty)
}

func TestSelectSeriesPageQBroadCursorDoesNotReemitOlderMember(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-repeat", "needle-repeat", `{"kind":"needle"}`, "m5", []seriesMember{
		{ts: day(-1), value: 1},
		{ts: day(100), value: 2},
	})
	for i := range 65 {
		seedSeries(t, st, ctx,
			"fp-broad-"+sha(i),
			"needle-broad-"+sha(i),
			`{"kind":"needle"}`,
			"m5",
			[]seriesMember{{ts: day(i), value: float64(i + 1)}},
		)
	}

	page1, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Q: new("needle"), PageSize: 1})
	require.NoError(t, err)
	require.Len(t, page1, 1)
	assert.Equal(t, "fp-repeat", page1[0].HistoryFingerprint)

	seen := map[string]bool{"fp-repeat": true}
	cursorTs := page1[0].LatestCommitTimestamp
	cursorFp := page1[0].HistoryFingerprint
	for {
		page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
			Q: new("needle"), CursorTs: &cursorTs, CursorFp: &cursorFp, PageSize: 1,
		})
		require.NoError(t, err)
		if len(page) == 0 {
			break
		}
		assert.False(t, seen[page[0].HistoryFingerprint], "cursor re-emitted %s", page[0].HistoryFingerprint)
		seen[page[0].HistoryFingerprint] = true
		cursorTs = page[0].LatestCommitTimestamp
		cursorFp = page[0].HistoryFingerprint
	}
	assert.Len(t, seen, 66)
}

func TestSelectSeriesPageDefaultCursorDoesNotReemitOlderMember(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-repeat", "repeat-default", `{}`, "m5", []seriesMember{
		{ts: day(-1), value: 1},
		{ts: day(100), value: 2},
	})
	for i := range 65 {
		seedSeries(t, st, ctx,
			"fp-default-"+sha(i),
			"default-"+sha(i),
			`{}`,
			"m5",
			[]seriesMember{{ts: day(i), value: float64(i + 1)}},
		)
	}

	page1, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{PageSize: 1})
	require.NoError(t, err)
	require.Len(t, page1, 1)
	assert.Equal(t, "fp-repeat", page1[0].HistoryFingerprint)

	seen := map[string]bool{"fp-repeat": true}
	cursorTs := page1[0].LatestCommitTimestamp
	cursorFp := page1[0].HistoryFingerprint
	for {
		page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
			CursorTs: &cursorTs, CursorFp: &cursorFp, PageSize: 10,
		})
		require.NoError(t, err)
		if len(page) == 0 {
			break
		}
		for _, row := range page {
			assert.False(t, seen[row.HistoryFingerprint], "cursor re-emitted %s", row.HistoryFingerprint)
			seen[row.HistoryFingerprint] = true
		}
		last := page[len(page)-1]
		cursorTs = last.LatestCommitTimestamp
		cursorFp = last.HistoryFingerprint
	}
	assert.Len(t, seen, 66)
}

func TestSelectSeriesPageDefaultCursorSkipsPassedFingerprintNoise(t *testing.T) {
	st, _, ctx := newTestStore(t)

	repeatedMembers := make([]seriesMember, 0, 92)
	for i := range 91 {
		repeatedMembers = append(repeatedMembers, seriesMember{ts: day(10 + i), value: float64(i + 1)})
	}
	repeatedMembers = append(repeatedMembers, seriesMember{ts: day(200), value: 200})
	seedSeries(t, st, ctx, "fp-repeat-noise", "repeat-noise", `{}`, "m5", repeatedMembers)
	seedSeries(t, st, ctx, "fp-unseen-older", "unseen-older", `{}`, "m5", []seriesMember{
		{ts: day(0), value: 1},
	})

	page1, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{PageSize: 1})
	require.NoError(t, err)
	require.Len(t, page1, 1)
	require.Equal(t, "fp-repeat-noise", page1[0].HistoryFingerprint)

	cursorTs := page1[0].LatestCommitTimestamp
	cursorFp := page1[0].HistoryFingerprint
	page2, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		CursorTs: &cursorTs, CursorFp: &cursorFp, PageSize: 1,
	})

	require.NoError(t, err)
	require.Len(t, page2, 1, "older members from the already-emitted fingerprint must not exhaust the bounded cursor scan")
	assert.Equal(t, "fp-unseen-older", page2[0].HistoryFingerprint)
}

func TestSelectSeriesPageDefaultCursorActiveUntilIgnoresFutureMembers(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-cursor", "cursor-series", `{}`, "m5", []seriesMember{
		{ts: day(10), value: 10},
	})
	seedSeries(t, st, ctx, "fp-visible-before-cutoff", "visible-before-cutoff", `{}`, "m5", []seriesMember{
		{ts: day(5), value: 5},
		{ts: day(200), value: 200},
	})
	until := day(10)

	page1, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{ActiveUntil: &until, PageSize: 1})
	require.NoError(t, err)
	require.Len(t, page1, 1)
	require.Equal(t, "fp-cursor", page1[0].HistoryFingerprint)

	cursorTs := page1[0].LatestCommitTimestamp
	cursorFp := page1[0].HistoryFingerprint
	page2, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		ActiveUntil: &until, CursorTs: &cursorTs, CursorFp: &cursorFp, PageSize: 1,
	})

	require.NoError(t, err)
	require.Len(t, page2, 1, "members after active_until must not suppress a visible older member while cursoring")
	assert.Equal(t, "fp-visible-before-cutoff", page2[0].HistoryFingerprint)
}

func TestSelectSeriesPageQBroadCursorAdvancesPastCommitWindow(t *testing.T) {
	st, _, ctx := newTestStore(t)

	const total = 330
	for i := range total {
		seedSeries(t, st, ctx,
			"fp-window-"+sha(i),
			"needle-window-"+sha(i),
			`{"kind":"needle"}`,
			"m5",
			[]seriesMember{{ts: day(i), value: float64(i + 1)}},
		)
	}

	seen := map[string]bool{}
	var cursorTs *time.Time
	var cursorFp *string
	for {
		page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
			Q: new("needle"), CursorTs: cursorTs, CursorFp: cursorFp, PageSize: 10,
		})
		require.NoError(t, err)
		if len(page) == 0 {
			break
		}
		for _, row := range page {
			assert.False(t, seen[row.HistoryFingerprint], "cursor re-emitted %s", row.HistoryFingerprint)
			seen[row.HistoryFingerprint] = true
		}
		last := page[len(page)-1]
		cursorTs = &last.LatestCommitTimestamp
		cursorFp = new(last.HistoryFingerprint)
	}

	assert.Len(t, seen, total, "cursor must continue beyond the first broad-search commit window")
}

func TestSelectSeriesPageQBroadCursorAdvancesThroughSameTimestampWindow(t *testing.T) {
	st, _, ctx := newTestStore(t)

	const tied = 330
	ts := day(10)
	for i := range tied {
		suffix := fmt.Sprintf("%03d", i)
		seedSeries(t, st, ctx,
			"fp-tie-"+suffix,
			"needle-tie-"+suffix,
			`{"kind":"needle"}`,
			"m5",
			[]seriesMember{{ts: ts, value: float64(i + 1)}},
		)
	}
	const older = 20
	for i := range older {
		suffix := fmt.Sprintf("%03d", i)
		seedSeries(t, st, ctx,
			"fp-older-"+suffix,
			"needle-tie-older-"+suffix,
			`{"kind":"needle"}`,
			"m5",
			[]seriesMember{{ts: day(9), value: float64(i + 1)}},
		)
	}

	seen := map[string]bool{}
	var cursorTs *time.Time
	var cursorFp *string
	for {
		page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
			Q: new("needle-tie"), CursorTs: cursorTs, CursorFp: cursorFp, PageSize: 10,
		})
		require.NoError(t, err)
		if len(page) == 0 {
			break
		}
		for _, row := range page {
			assert.False(t, seen[row.HistoryFingerprint], "cursor re-emitted %s", row.HistoryFingerprint)
			seen[row.HistoryFingerprint] = true
		}
		last := page[len(page)-1]
		cursorTs = &last.LatestCommitTimestamp
		cursorFp = new(last.HistoryFingerprint)
	}

	assert.Len(t, seen, tied+older, "cursor must continue through timestamp ties larger than the commit window")
}

func TestSelectSeriesPageQFilterComposesWithHardwareAndRepository(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeriesRepo(t, st, ctx, "fp-a", "needle-bench", `{"kind":"needle"}`, "m5", "https://github.com/org/repo-a",
		[]seriesMember{{ts: day(1), value: 1}})
	seedSeriesRepo(t, st, ctx, "fp-b", "needle-bench", `{"kind":"needle"}`, "c6", "https://github.com/org/repo-b",
		[]seriesMember{{ts: day(2), value: 1}})
	seedSeriesRepo(t, st, ctx, "fp-hardware-only", "needle-bench", `{"kind":"needle"}`, "c6", "https://github.com/org/repo-a",
		[]seriesMember{{ts: day(3), value: 1}})
	seedSeriesRepo(t, st, ctx, "fp-repo-only", "needle-bench", `{"kind":"needle"}`, "m5", "https://github.com/org/repo-b",
		[]seriesMember{{ts: day(4), value: 1}})

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		Q: new("needle"), Hardware: new("c6"), Repository: new("https://github.com/org/repo-b"), PageSize: 50,
	})

	require.NoError(t, err)
	require.Len(t, got, 1)
	assert.Equal(t, "fp-b", got[0].HistoryFingerprint)
}

func TestSelectSeriesPageQBroadRepositoryFilterFindsOlderSparseMatch(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeriesRepo(t, st, ctx, "fp-target", "needle-target", `{"kind":"needle"}`, "m5", "https://github.com/org/repo-b",
		[]seriesMember{{ts: day(1), value: 1}})
	for i := range 330 {
		seedSeriesRepo(t, st, ctx,
			"fp-recent-"+sha(i),
			"needle-recent-"+sha(i),
			`{"kind":"needle"}`,
			"m5",
			"https://github.com/org/repo-a",
			[]seriesMember{{ts: day(10 + i), value: float64(i + 1)}},
		)
	}

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		Q: new("needle"), Repository: new("https://github.com/org/repo-b"), PageSize: 10,
	})

	require.NoError(t, err)
	require.Len(t, got, 1)
	assert.Equal(t, "fp-target", got[0].HistoryFingerprint)
}

func TestSelectSeriesPageQFilterActiveWindow(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-old", "needle-old", `{"kind":"needle"}`, "m5", []seriesMember{{ts: day(1), value: 1}})
	seedSeries(t, st, ctx, "fp-new", "needle-new", `{"kind":"needle"}`, "m5", []seriesMember{{ts: day(5), value: 1}})

	since := day(3)
	bySince, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		Q: new("needle"), ActiveSince: &since, PageSize: 50,
	})
	require.NoError(t, err)
	require.Len(t, bySince, 1)
	assert.Equal(t, "fp-new", bySince[0].HistoryFingerprint)

	until := day(3)
	byUntil, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		Q: new("needle"), ActiveUntil: &until, PageSize: 50,
	})
	require.NoError(t, err)
	require.Len(t, byUntil, 1)
	assert.Equal(t, "fp-old", byUntil[0].HistoryFingerprint)
}

func TestSelectSeriesPageQFilterKeepsMultipleFingerprintsForSameCase(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-m5", "needle-shared-case", `{"kind":"needle"}`, "m5",
		[]seriesMember{{ts: day(1), value: 1}})
	seedSeries(t, st, ctx, "fp-c6", "needle-shared-case", `{"kind":"needle"}`, "c6",
		[]seriesMember{{ts: day(2), value: 1}})

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Q: new("needle-shared"), PageSize: 50})

	require.NoError(t, err)
	require.Len(t, got, 2)
	assert.ElementsMatch(t, []string{"fp-m5", "fp-c6"}, []string{got[0].HistoryFingerprint, got[1].HistoryFingerprint})
}

func TestSelectSeriesPageFingerprintTakesPrecedenceOverQ(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-a", "needle-a", `{"kind":"needle"}`, "m5", []seriesMember{{ts: day(1), value: 1}})
	seedSeries(t, st, ctx, "fp-b", "needle-b", `{"kind":"needle"}`, "m5", []seriesMember{{ts: day(2), value: 1}})

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		Q: new("needle"), Fingerprint: new("fp-a"), PageSize: 50,
	})

	require.NoError(t, err)
	require.Len(t, got, 1)
	assert.Equal(t, "fp-a", got[0].HistoryFingerprint)
}

func TestSelectSeriesMembersReturnsRecentBoundedTail(t *testing.T) {
	st, _, ctx := newTestStore(t)

	members := make([]seriesMember, 300)
	for i := range members {
		members[i] = seriesMember{ts: day(i), value: float64(i)}
	}
	seedSeries(t, st, ctx, "fp-long", "long-history", `{}`, "m5", members)

	got, err := st.SelectSeriesMembers(ctx, []string{"fp-long"})

	require.NoError(t, err)
	require.Len(t, got, 256)
	require.NotNil(t, got[0].CommitTimestamp)
	require.NotNil(t, got[len(got)-1].CommitTimestamp)
	assert.Equal(t, day(44), *got[0].CommitTimestamp)
	assert.Equal(t, day(299), *got[len(got)-1].CommitTimestamp)
}

// TestSelectSeriesPageRepositoryFilter asserts the repository filter matches the
// series' commit repo URL exactly.
func TestSelectSeriesPageRepositoryFilter(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-main", "case-a", `{}`, "m5", []seriesMember{{ts: day(0), value: 1}})
	seedSeriesRepo(t, st, ctx, "fp-fork", "case-b", `{}`, "m5", "https://github.com/org/fork",
		[]seriesMember{{ts: day(0), value: 1}})

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		Repository: new("https://github.com/org/fork"), PageSize: 50,
	})
	require.NoError(t, err)
	require.Len(t, got, 1)
	assert.Equal(t, "fp-fork", got[0].HistoryFingerprint)
	assert.Equal(t, "https://github.com/org/fork", got[0].CommitRepoUrl)
}

// TestSelectSeriesPageFilters asserts the hardware, fingerprint, and
// active-window filters on the latest commit timestamp.
func TestSelectSeriesPageFilters(t *testing.T) {
	st, _, ctx := newTestStore(t)

	seedSeries(t, st, ctx, "fp-m5", "case-a", `{}`, "m5", []seriesMember{{ts: day(1), value: 1}})
	seedSeries(t, st, ctx, "fp-c6", "case-b", `{}`, "c6", []seriesMember{{ts: day(5), value: 1}})

	byHW, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Hardware: new("c6"), PageSize: 50})
	require.NoError(t, err)
	require.Len(t, byHW, 1)
	assert.Equal(t, "case-b", byHW[0].CaseName)

	byFP, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Fingerprint: new("fp-m5"), PageSize: 50})
	require.NoError(t, err)
	require.Len(t, byFP, 1)
	assert.Equal(t, "fp-m5", byFP[0].HistoryFingerprint)

	// active_since filters on latest commit timestamp: only the c6 series
	// (day 5) is at or after day 3.
	since := day(3)
	bySince, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{ActiveSince: &since, PageSize: 50})
	require.NoError(t, err)
	require.Len(t, bySince, 1)
	assert.Equal(t, "fp-c6", bySince[0].HistoryFingerprint)

	// active_until: only the m5 series (day 1) is at or before day 3.
	until := day(3)
	byUntil, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{ActiveUntil: &until, PageSize: 50})
	require.NoError(t, err)
	require.Len(t, byUntil, 1)
	assert.Equal(t, "fp-m5", byUntil[0].HistoryFingerprint)
}

func TestSelectSeriesPageHardwareFilterUsesResultBearingHardwareWindow(t *testing.T) {
	st, _, ctx := newTestStore(t)

	for i := range 530 {
		seedSeries(t, st, ctx,
			"fp-recent-m5-"+sha(i),
			"recent-m5-"+sha(i),
			`{}`,
			"m5",
			[]seriesMember{{ts: day(10 + i), value: float64(i + 1)}},
		)
	}
	seedSeries(t, st, ctx, "fp-older-c6", "older-c6", `{}`, "c6", []seriesMember{
		{ts: day(0), value: 1},
	})

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Hardware: new("c6"), PageSize: 1})

	require.NoError(t, err)
	require.Len(t, got, 1, "hardware-filtered browse must not be starved by recent results on other hardware")
	assert.Equal(t, "fp-older-c6", got[0].HistoryFingerprint)
}

func TestSelectSeriesPageHardwareFilterFirstPageSkipsRepeatedFingerprintNoise(t *testing.T) {
	st, _, ctx := newTestStore(t)

	repeatedMembers := make([]seriesMember, 170)
	for i := range repeatedMembers {
		repeatedMembers[i] = seriesMember{ts: day(10 + i), value: float64(i + 1)}
	}
	seedSeries(t, st, ctx, "fp-c6-repeat", "c6-repeat", `{}`, "c6", repeatedMembers)
	seedSeries(t, st, ctx, "fp-c6-older", "c6-older", `{}`, "c6", []seriesMember{
		{ts: day(0), value: 1},
	})

	got, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{Hardware: new("c6"), PageSize: 2})

	require.NoError(t, err)
	require.Len(t, got, 2, "repeated commits for one matching hardware fingerprint must not hide older matching fingerprints")
	assert.Equal(t, "fp-c6-repeat", got[0].HistoryFingerprint)
	assert.Equal(t, "fp-c6-older", got[1].HistoryFingerprint)
}

// TestSelectSeriesPageCursorWalk walks the full list one row at a time via the
// composite (commit timestamp, fingerprint) cursor and asserts every series is
// visited exactly once, including the equal-timestamp tiebreak between two
// series whose latest members share a commit timestamp.
func TestSelectSeriesPageCursorWalk(t *testing.T) {
	st, _, ctx := newTestStore(t)

	// Four series across three distinct latest timestamps; two share day(2).
	seedSeries(t, st, ctx, "fp-1", "case-1", `{}`, "m5", []seriesMember{{ts: day(1), value: 1}})
	seedSeries(t, st, ctx, "fp-2", "case-2", `{}`, "m5", []seriesMember{{ts: day(2), value: 1}})
	seedSeries(t, st, ctx, "fp-3", "case-3", `{}`, "m5", []seriesMember{{ts: day(2), value: 1}})
	seedSeries(t, st, ctx, "fp-4", "case-4", `{}`, "m5", []seriesMember{{ts: day(3), value: 1}})

	// Reference: a single large page gives the canonical total order.
	full, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{PageSize: 50})
	require.NoError(t, err)
	require.Len(t, full, 4)
	wantOrder := make([]string, len(full))
	for i, r := range full {
		wantOrder[i] = r.HistoryFingerprint
	}

	var gotOrder []string
	var cursorTs *time.Time
	var cursorFp *string
	for range full {
		page, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
			CursorTs: cursorTs, CursorFp: cursorFp, PageSize: 1,
		})
		require.NoError(t, err)
		require.Len(t, page, 1, "each single-row page yields exactly one series")
		row := page[0]
		gotOrder = append(gotOrder, row.HistoryFingerprint)
		ts := row.LatestCommitTimestamp
		cursorTs = &ts
		cursorFp = new(row.HistoryFingerprint)
	}

	// Walking by cursor reproduces the canonical order with no dupes or gaps.
	assert.Equal(t, wantOrder, gotOrder, "cursor walk matches single-page order")
	assert.ElementsMatch(t, []string{"fp-1", "fp-2", "fp-3", "fp-4"}, gotOrder,
		"every series visited exactly once, including the day(2) tie")

	// The page after the last row is empty (no gaps past the end).
	last := full[len(full)-1]
	lastTs := last.LatestCommitTimestamp
	empty, err := st.SelectSeriesPage(ctx, storage.SeriesListParams{
		CursorTs: &lastTs, CursorFp: new(last.HistoryFingerprint), PageSize: 1,
	})
	require.NoError(t, err)
	assert.Empty(t, empty, "cursor past the final row returns no rows")
}

// TestSelectSeriesMembers asserts the batched membership read returns the
// recent series tail per fingerprint, grouped by fingerprint and ordered oldest
// commit first within each returned tail, with the HistoryRow fields the
// status/sparkline derivation needs. Membership matches SelectHistoryForFingerprint
// (non-errored, default-branch, commit-joined with a non-null commit timestamp).
func TestSelectSeriesMembers(t *testing.T) {
	st, _, ctx := newTestStore(t)

	// Series A: two valid members (day 0, day 1) plus a later errored member and
	// a later off-branch member that membership must exclude.
	seedSeries(t, st, ctx, "fp-a", "case-a", `{}`, "m5", []seriesMember{
		{ts: day(0), value: 1.0},
		{ts: day(1), value: 2.0},
		{ts: day(2), value: 9.0, errored: true},
		{ts: day(3), value: 9.0, offBranch: true},
	})
	// Series B: a single valid member.
	seedSeries(t, st, ctx, "fp-b", "case-b", `{}`, "m5", []seriesMember{
		{ts: day(0), value: 9.0},
	})

	rows, err := st.SelectSeriesMembers(ctx, []string{"fp-a", "fp-b"})
	require.NoError(t, err)
	require.Len(t, rows, 3, "two valid members of A plus one of B; errored/off-branch excluded")

	// Grouped by fingerprint: each fingerprint's rows are contiguous.
	groups := contiguousFingerprintGroups(rows)
	assert.Equal(t, map[string]int{"fp-a": 1, "fp-b": 1}, groups,
		"each fingerprint appears in exactly one contiguous run")

	byFP := membersByFingerprint(rows)
	a := byFP["fp-a"]
	require.Len(t, a, 2)
	// Within a fingerprint, ordered by commit timestamp ascending (oldest first).
	assert.True(t, a[0].CommitTimestamp.Equal(day(0)), "A ordered oldest commit first")
	assert.True(t, a[1].CommitTimestamp.Equal(day(1)))

	// Representative HistoryRow fields the downstream status/sparkline needs.
	assert.Equal(t, "fp-a", a[0].HistoryFingerprint)
	require.NotNil(t, a[0].Unit)
	assert.Equal(t, "s", *a[0].Unit)
	require.Len(t, a[0].Data, 1)
	assert.InDelta(t, 1.0, a[0].Data[0], 1e-9)
	assert.Equal(t, "machinehash-m5", a[0].HardwareHash)
	assert.Equal(t, "sha-m5-case-a-a0", a[0].CommitSha)
	assert.Equal(t, "https://github.com/org/repo", a[0].CommitRepository)

	b := byFP["fp-b"]
	require.Len(t, b, 1)
	assert.True(t, b[0].CommitTimestamp.Equal(day(0)))
	assert.InDelta(t, 9.0, b[0].Data[0], 1e-9)
}

// TestSelectSeriesMembersEmptyAndMissing asserts an empty fingerprint list
// returns no rows (no error) and that a fingerprint with no members simply
// contributes nothing while present fingerprints still return their members.
func TestSelectSeriesMembersEmptyAndMissing(t *testing.T) {
	st, _, ctx := newTestStore(t)
	seedSeries(t, st, ctx, "fp-present", "case-present", `{}`, "m5", []seriesMember{
		{ts: day(0), value: 1.0},
	})

	empty, err := st.SelectSeriesMembers(ctx, []string{})
	require.NoError(t, err)
	assert.Empty(t, empty, "empty fingerprint list returns no rows")

	// A fingerprint that has no members contributes nothing; the present one still
	// returns its single member.
	rows, err := st.SelectSeriesMembers(ctx, []string{"fp-present", "fp-absent"})
	require.NoError(t, err)
	require.Len(t, rows, 1, "absent fingerprint contributes no rows")
	assert.Equal(t, "fp-present", rows[0].HistoryFingerprint)
}

// membersByFingerprint groups member rows by fingerprint, preserving order.
func membersByFingerprint(rows []storage.HistoryRow) map[string][]storage.HistoryRow {
	out := map[string][]storage.HistoryRow{}
	for _, r := range rows {
		out[r.HistoryFingerprint] = append(out[r.HistoryFingerprint], r)
	}
	return out
}

// contiguousFingerprintGroups counts, per fingerprint, the number of distinct
// contiguous runs in the row order. A grouped result has exactly one run per
// fingerprint; an interleaved result would report more.
func contiguousFingerprintGroups(rows []storage.HistoryRow) map[string]int {
	out := map[string]int{}
	prev := ""
	for i, r := range rows {
		if i == 0 || r.HistoryFingerprint != prev {
			out[r.HistoryFingerprint]++
		}
		prev = r.HistoryFingerprint
	}
	return out
}
