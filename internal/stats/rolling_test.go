package stats

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func ptrEq(t *testing.T, exp, got *float64, msg string) {
	t.Helper()
	if exp == nil {
		assert.Nil(t, got, msg)
		return
	}
	require.NotNil(t, got, msg)
	assert.InDelta(t, *exp, *got, 1e-9, msg)
}

func TestRollingStatsFromFormula(t *testing.T) {
	p := func(v float64) *float64 { return &v }
	mk := func(begins []bool, days []int, svs []float64) []SeriesPoint {
		base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
		pts := make([]SeriesPoint, len(svs))
		for i := range svs {
			ct := base.AddDate(0, 0, days[i])
			pts[i] = SeriesPoint{CommitTimestamp: ct, ResultTimestamp: ct, SVS: svs[i], BeginsDistributionChange: begins[i]}
		}
		return pts
	}

	// --- Case 1: three clean monotone points, distinct commits, one segment. ---
	// Commit ranks 1,2,3. excl is closed-LEFT (prior commits only); the first
	// point's empty window is filled with its own svs (combine_first):
	//   excl = [10, mean{10}=10, mean{10,20}=15]; residual = svs-excl = [0,10,15].
	c1 := mk([]bool{false, false, false}, []int{0, 1, 2}, []float64{10, 20, 30})

	excl := RollingStatsForSeries(c1, false, DistributionCommitsDefault)
	require.Len(t, excl, 3)
	for i, e := range []struct {
		seg                           int
		rmeanExcl, rmean, resid, rstd *float64
	}{
		{0, p(10), p(10), p(0), nil},                    // closed-left std over {} -> NaN
		{0, p(10), p(10), p(10), nil},                   // closed-left std over {0} -> NaN
		{0, p(15), p(15), p(15), p(7.0710678118654755)}, // std{0,10}=sqrt(50)
	} {
		assert.Equal(t, e.seg, excl[i].SegmentID, "c1 excl seg %d", i)
		assert.False(t, excl[i].IsStep || excl[i].IsOutlier, "c1 excl flags %d", i)
		ptrEq(t, e.rmeanExcl, excl[i].RollingMeanExcludingThis, "c1 excl rmean_excl")
		ptrEq(t, e.rmean, excl[i].RollingMean, "c1 excl rmean") // exclusive: rmean == rmean_excl
		ptrEq(t, e.resid, excl[i].Residual, "c1 excl residual")
		ptrEq(t, e.rstd, excl[i].RollingStddev, "c1 excl rstd")
	}

	// inclusive rmean is closed-RIGHT: [10, mean{10,20}=15, mean{10,20,30}=20];
	// inclusive rstd over residuals {0,10,15}: [NaN, sqrt(50), sqrt(175/3)].
	incl := RollingStatsForSeries(c1, true, DistributionCommitsDefault)
	for i, e := range []struct{ rmean, rstd *float64 }{
		{p(10), nil},
		{p(15), p(7.0710678118654755)},
		{p(20), p(7.637626158259733)},
	} {
		ptrEq(t, e.rmean, incl[i].RollingMean, "c1 incl rmean")
		ptrEq(t, e.rstd, incl[i].RollingStddev, "c1 incl rstd")
	}

	// --- Case 2: a manual segment boundary resets the rolling mean. ---
	// begins=[F,F,T,F,F] -> segment_id=[0,0,1,1,1]; the segment-1 mean never reaches
	// back into segment 0. combine_first fills each segment's first point with its
	// own svs: excl = [10, 10, 100, 100, mean{100,30}=65]; residual = svs-excl.
	c2 := mk([]bool{false, false, true, false, false}, []int{0, 1, 2, 3, 4}, []float64{10, 20, 100, 30, 40})
	seg := RollingStatsForSeries(c2, false, DistributionCommitsDefault)
	wantSeg := []int{0, 0, 1, 1, 1}
	wantExcl := []*float64{p(10), p(10), p(100), p(100), p(65)}
	wantResid := []*float64{p(0), p(10), p(0), p(-70), p(-25)}
	for i := range c2 {
		assert.Equal(t, wantSeg[i], seg[i].SegmentID, "c2 seg %d", i)
		ptrEq(t, wantExcl[i], seg[i].RollingMeanExcludingThis, "c2 rmean_excl")
		ptrEq(t, wantResid[i], seg[i].Residual, "c2 residual")
	}

	// --- Case 3: a detected outlier is excluded from the rolling stats. ---
	// Spike-then-revert flags index 3 as an outlier (see TestDetectShiftsFromFormula);
	// its columns are nil and it is dropped from the others' windows, so every
	// non-outlier point's excl mean is 1.0.
	c3 := mk(make([]bool, 7), []int{0, 1, 2, 3, 4, 5, 6}, []float64{1, 1, 1, 9, 1, 1, 1})
	out := RollingStatsForSeries(c3, false, DistributionCommitsDefault)
	assert.True(t, out[3].IsOutlier, "c3 index3 outlier")
	ptrEq(t, nil, out[3].RollingMeanExcludingThis, "c3 outlier rmean_excl nil")
	ptrEq(t, nil, out[3].Residual, "c3 outlier residual nil")
	ptrEq(t, nil, out[3].RollingMean, "c3 outlier rmean nil")
	for _, i := range []int{0, 2, 4, 6} {
		assert.False(t, out[i].IsOutlier, "c3 index%d not outlier", i)
		ptrEq(t, p(1), out[i].RollingMeanExcludingThis, "c3 neighbor rmean_excl")
	}
}

// TestRollingStatsSegmentTiedBegins pins the dense commit-rank closed-right
// segment_id: when begins_distribution_change is on the SECOND of two rows sharing
// a commit timestamp, BOTH tied rows (and everything after) belong to the new
// segment. A row-by-row cumsum would wrongly leave the first tied row in segment 0
// and corrupt its rolling mean (legacy _CommitIndexer closed-right, history.py:615).
func TestRollingStatsSegmentTiedBegins(t *testing.T) {
	base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	day := func(d int) time.Time { return base.AddDate(0, 0, d) }
	// Two rows at commit-day 1; the begins flag is on the second (input index 2).
	pts := []SeriesPoint{
		{CommitTimestamp: day(0), ResultTimestamp: day(0), SVS: 10},
		{CommitTimestamp: day(1), ResultTimestamp: day(1), SVS: 20},
		{CommitTimestamp: day(1), ResultTimestamp: day(1), SVS: 30, BeginsDistributionChange: true},
		{CommitTimestamp: day(2), ResultTimestamp: day(2), SVS: 40},
	}
	got := RollingStatsForSeries(pts, true, DistributionCommitsDefault)
	require.Len(t, got, 4)
	// Boundary at rank 2 -> both tied rows + day2 in segment 1 (NOT [0,0,1,1]).
	assert.Equal(t, []int{0, 1, 1, 1},
		[]int{got[0].SegmentID, got[1].SegmentID, got[2].SegmentID, got[3].SegmentID})
	// The two tied rows share the rank-2 inclusive window {20,30} -> mean 25 each.
	p := func(v float64) *float64 { return &v }
	ptrEq(t, p(10), got[0].RollingMean, "tied seg0 mean")
	ptrEq(t, p(25), got[1].RollingMean, "tied row1 mean")
	ptrEq(t, p(25), got[2].RollingMean, "tied row2 mean")
	ptrEq(t, p(30), got[3].RollingMean, "tied day2 mean")
}

// TestRollingStatsForSeriesGolden is the SECONDARY parity check across the fuller
// case set. got[i] and exp[i] are both in INPUT order: the oracle re-sorts its
// output by _input_idx before emitting, and RollingStatsForSeries returns one row
// per input point in input order (sorting internally for the windowed computation,
// then mapping each result back to its input position). The shuffled_input case
// (non-ascending input) enforces that contract; same_timestamp_tie / exact_tie
// validate stable tie handling; small_window exercises the threaded window.
func TestRollingStatsForSeriesGolden(t *testing.T) {
	for name, c := range loadRollingGolden(t) {
		pts := pointsFromGolden(t, c.Points)
		for _, mode := range []struct {
			key            string
			includeCurrent bool
		}{{"exclusive", false}, {"inclusive", true}} {
			exp := c.Expected[mode.key]
			got := RollingStatsForSeries(pts, mode.includeCurrent, c.DistributionCommits)
			require.Len(t, got, len(exp), "%s/%s", name, mode.key)
			for i := range exp {
				p := name + "/" + mode.key
				assert.Equal(t, exp[i].SegmentID, got[i].SegmentID, "%s[%d] segment_id", p, i)
				assert.Equal(t, exp[i].BeginsDistributionChange, got[i].BeginsDistributionChange, "%s[%d] begins", p, i)
				assert.Equal(t, exp[i].IsStep, got[i].IsStep, "%s[%d] is_step", p, i)
				assert.Equal(t, exp[i].IsOutlier, got[i].IsOutlier, "%s[%d] is_outlier", p, i)
				ptrEq(t, exp[i].RollingMeanExcludingThis, got[i].RollingMeanExcludingThis, p+" rmean_excl")
				ptrEq(t, exp[i].RollingMean, got[i].RollingMean, p+" rolling_mean")
				ptrEq(t, exp[i].Residual, got[i].Residual, p+" residual")
				ptrEq(t, exp[i].RollingStddev, got[i].RollingStddev, p+" rolling_stddev")
			}
		}
	}
}

func TestBaselineDistributionFromFormula(t *testing.T) {
	mk := func(days []int, svs []float64) []SeriesPoint {
		base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
		pts := make([]SeriesPoint, len(svs))
		for i := range svs {
			ct := base.AddDate(0, 0, days[i])
			pts[i] = SeriesPoint{CommitTimestamp: ct, ResultTimestamp: ct, SVS: svs[i]}
		}
		return pts
	}

	// Latest point's inclusive stats. [10,20,30] at distinct commits:
	// rolling_mean = mean{10,20,30} = 20; residuals = [0,10,15];
	// rolling_stddev = sample std{0,10,15} = sqrt(175/3).
	mean, sd := BaselineDistribution(mk([]int{0, 1, 2}, []float64{10, 20, 30}), DistributionCommitsDefault)
	require.NotNil(t, mean)
	require.NotNil(t, sd)
	assert.InDelta(t, 20.0, *mean, 1e-9)
	assert.InDelta(t, 7.637626158259733, *sd, 1e-9) // sqrt(175/3)

	// Tied latest: two points share the max commit timestamp (same segment), so they
	// share a window and the reduction is well-defined. Inclusive over {10,20,30,40}
	// -> mean 25; residuals {0,10,15,25} -> std sqrt(325/3).
	mean, sd = BaselineDistribution(mk([]int{0, 1, 2, 2}, []float64{10, 20, 30, 40}), DistributionCommitsDefault)
	require.NotNil(t, mean)
	require.NotNil(t, sd)
	assert.InDelta(t, 25.0, *mean, 1e-9)
	assert.InDelta(t, 10.408329997330663, *sd, 1e-9) // sqrt(325/3)

	// Tied-latest OUTLIER (verified against the legacy oracle): a spike (9.9) and its
	// revert (1.0) both sit at the max commit timestamp. The spike is the first
	// input-order row there and is flagged is_outlier, so its rolling stats are nil.
	// Legacy's reduction (sort_values("timestamp", desc) + drop_duplicates) keeps that
	// same first row, yielding (None, None); maxIdx (first input index at the max
	// timestamp) lands on the outlier too, so BaselineDistribution returns (nil, nil),
	// matching legacy. Not order-invariant (the tied rows differ), so this is a
	// first-principles case only -- never a parity fixture pinned to pandas' sort.
	b := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	at := func(d, sec int) time.Time { return b.AddDate(0, 0, d).Add(time.Duration(sec) * time.Second) }
	spikeRevert := []SeriesPoint{
		{CommitTimestamp: at(0, 0), ResultTimestamp: at(0, 0), SVS: 1.0},
		{CommitTimestamp: at(1, 0), ResultTimestamp: at(1, 0), SVS: 1.0},
		{CommitTimestamp: at(2, 0), ResultTimestamp: at(2, 0), SVS: 1.0},
		{CommitTimestamp: at(3, 0), ResultTimestamp: at(3, 0), SVS: 9.9},
		{CommitTimestamp: at(3, 0), ResultTimestamp: at(3, 5), SVS: 1.0},
	}
	mo, so := BaselineDistribution(spikeRevert, DistributionCommitsDefault)
	assert.Nil(t, mo, "outlier latest row -> nil mean, matching legacy")
	assert.Nil(t, so, "outlier latest row -> nil stddev, matching legacy")

	// Empty series -> (nil, nil).
	m2, s2 := BaselineDistribution(nil, DistributionCommitsDefault)
	assert.Nil(t, m2)
	assert.Nil(t, s2)
}

type goldenBaselineCase struct {
	DistributionCommits int           `json:"distribution_commits"`
	Points              []goldenPoint `json:"points"`
	Mean                *float64      `json:"mean"`
	Stddev              *float64      `json:"stddev"`
}

// TestBaselineDistributionGolden is the SECONDARY parity check, including the
// tied_latest snapshot that pins the descending-sort + drop_duplicates reduction.
func TestBaselineDistributionGolden(t *testing.T) {
	b, err := os.ReadFile(filepath.Join("testdata", "baseline_golden.json"))
	require.NoError(t, err)
	var cases map[string]goldenBaselineCase
	require.NoError(t, json.Unmarshal(b, &cases))
	require.Contains(t, cases, "tied_latest")

	for name, c := range cases {
		pts := pointsFromGolden(t, c.Points)
		mean, stddev := BaselineDistribution(pts, c.DistributionCommits)
		ptrEq(t, c.Mean, mean, name+" mean")
		ptrEq(t, c.Stddev, stddev, name+" stddev")
	}
}

func TestDetectShiftsFromFormula(t *testing.T) {
	mk := func(svs ...float64) []SeriesPoint {
		base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
		pts := make([]SeriesPoint, len(svs))
		for i, v := range svs {
			ct := base.AddDate(0, 0, i)
			pts[i] = SeriesPoint{CommitTimestamp: ct, ResultTimestamp: ct, SVS: v}
		}
		return pts
	}
	flags := func(pts []SeriesPoint) (step, out []bool) {
		for _, f := range detectShifts(pts, DistributionCommitsDefault) {
			step = append(step, f.isStep)
			out = append(out, f.isOutlier)
		}
		return step, out
	}

	// Flat series: svs.diff() is all zero, so nothing trips the trimmed z-score.
	s, o := flags(mk(5, 5, 5, 5))
	assert.Equal(t, []bool{false, false, false, false}, s, "flat is_step")
	assert.Equal(t, []bool{false, false, false, false}, o, "flat is_outlier")

	// Clean upward step at index 4: the +4 jump is clipped out of its own baseline
	// (q95 < 4), leaving constant-0 clipped diffs -> rolling std 0 -> z = 4/0 = +Inf
	// -> is_step at index 4 only; no adjacent shift -> no outlier.
	s, o = flags(mk(1, 1, 1, 1, 5, 5, 5, 5))
	assert.Equal(t, []bool{false, false, false, false, true, false, false, false}, s, "step is_step")
	assert.Equal(t, make([]bool, 8), o, "step is_outlier")

	// Spike up then back (revert pair) at index 3: +8 then -8 are both clipped out
	// and both flagged as shifts; reverts[3] = shift[3] && shift[4] = true -> index 3
	// is an OUTLIER (not a step), and index 4 is suppressed by the preceding revert.
	s, o = flags(mk(1, 1, 1, 9, 1, 1, 1))
	assert.Equal(t, make([]bool, 7), s, "spike is_step")
	assert.Equal(t, []bool{false, false, false, true, false, false, false}, o, "spike is_outlier")
}

// goldenPoint is one input point (the case's "points" array).
type goldenPoint struct {
	CommitTimestamp          string  `json:"commit_timestamp"`
	ResultTimestamp          string  `json:"result_timestamp"`
	SVS                      float64 `json:"svs"`
	BeginsDistributionChange bool    `json:"begins_distribution_change"`
}

// goldenStats is one expected output row (the case's "expected" arrays). The
// oracle emits these in INPUT order, so expected[i] corresponds to points[i].
type goldenStats struct {
	SegmentID                int      `json:"segment_id"`
	BeginsDistributionChange bool     `json:"begins_distribution_change"`
	RollingMeanExcludingThis *float64 `json:"rolling_mean_excluding_this_commit"`
	RollingMean              *float64 `json:"rolling_mean"`
	Residual                 *float64 `json:"residual"`
	RollingStddev            *float64 `json:"rolling_stddev"`
	IsStep                   bool     `json:"is_step"`
	IsOutlier                bool     `json:"is_outlier"`
}

type goldenRollingCase struct {
	DistributionCommits int                      `json:"distribution_commits"`
	Points              []goldenPoint            `json:"points"`
	Expected            map[string][]goldenStats `json:"expected"` // "exclusive" / "inclusive"
}

func loadRollingGolden(t *testing.T) map[string]goldenRollingCase {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("testdata", "rolling_golden.json"))
	require.NoError(t, err)
	var cases map[string]goldenRollingCase
	require.NoError(t, json.Unmarshal(b, &cases))
	return cases
}

// pointsFromGolden parses the input points. Parse errors FAIL the test: the
// oracle emits Z-suffixed RFC3339, so a failure means a fixture/format bug, never
// a silently-zeroed time.
func pointsFromGolden(t *testing.T, gps []goldenPoint) []SeriesPoint {
	t.Helper()
	out := make([]SeriesPoint, len(gps))
	for i, gp := range gps {
		ct, err := time.Parse(time.RFC3339, gp.CommitTimestamp)
		require.NoError(t, err, "commit_timestamp[%d]=%q", i, gp.CommitTimestamp)
		rt, err := time.Parse(time.RFC3339, gp.ResultTimestamp)
		require.NoError(t, err, "result_timestamp[%d]=%q", i, gp.ResultTimestamp)
		out[i] = SeriesPoint{
			CommitTimestamp:          ct,
			ResultTimestamp:          rt,
			SVS:                      gp.SVS,
			BeginsDistributionChange: gp.BeginsDistributionChange,
		}
	}
	return out
}

// TestDetectShiftsWindowSensitive proves distributionCommits is threaded into
// detection (not hardcoded): the early +/-3 diffs inflate the long-window rolling
// std, but the recent tight +1 diffs leave a dc=3 window std ~0, so the final +10
// jump is z=+Inf with dc=3 (a step) yet sub-threshold with dc=100. A regression
// that ignored the window argument would report identical flags for both windows.
func TestDetectShiftsWindowSensitive(t *testing.T) {
	base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	svs := []float64{0, 3, 0, 3, 0, 3, 0, 1, 2, 3, 13}
	pts := make([]SeriesPoint, len(svs))
	for i, v := range svs {
		ct := base.AddDate(0, 0, i)
		pts[i] = SeriesPoint{CommitTimestamp: ct, ResultTimestamp: ct, SVS: v}
	}
	step := func(dc int) bool { return detectShifts(pts, dc)[10].isStep }
	assert.True(t, step(3), "small window detects the final jump")
	assert.False(t, step(100), "default window std is inflated -> no step")
}

// TestDetectShiftsGolden is the SECONDARY parity check: it confirms the
// formula-derived detector agrees with the committed Python snapshot across the
// fuller case set. A parity-only failure is a real semantic gap — re-derive and
// fix the Go, never edit the snapshot to match unverified Go.
func TestDetectShiftsGolden(t *testing.T) {
	for name, c := range loadRollingGolden(t) {
		// is_step/is_outlier are mode-independent; use the inclusive expectation.
		exp := c.Expected["inclusive"]
		pts := pointsFromGolden(t, c.Points)
		got := detectShifts(pts, c.DistributionCommits)
		require.Len(t, got, len(exp), name)
		for i := range exp {
			assert.Equal(t, exp[i].IsStep, got[i].isStep, "%s[%d] is_step", name, i)
			assert.Equal(t, exp[i].IsOutlier, got[i].isOutlier, "%s[%d] is_outlier", name, i)
		}
	}
}
