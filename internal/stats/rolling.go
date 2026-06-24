package stats

import (
	"math"
	"sort"
	"time"
)

// Engine defaults (legacy config.py / api/compare.py).
const (
	DistributionCommitsDefault      = 100
	PairwisePercentThresholdDefault = 5.0
	ZScoreThresholdDefault          = 5.0
	shiftZScoreThreshold            = 5.0
)

// SeriesPoint is one benchmark result within a single history fingerprint's
// series. Leaf B groups by fingerprint and guarantees a single unit per series.
// SVS is the raw single-value summary in the unit's natural scale (see the SVS
// field). The rolling and shift statistics here are direction-agnostic -- they
// measure the magnitude of change -- and the verdict/z-score layer applies the
// unit's direction via lessIsBetter.
type SeriesPoint struct {
	// CommitTimestamp is the primary ordering and windowing key.
	CommitTimestamp time.Time
	// ResultTimestamp is the secondary tie-break for results that share a
	// CommitTimestamp in shift detection (legacy 3-key sort). Populate it from
	// the result's own timestamp; it does not otherwise affect the output.
	ResultTimestamp time.Time
	// SVS is the raw single-value summary in the unit's natural scale: best-of-mode
	// (min when the unit is less-is-better, else max) or the mean. It is NOT
	// sign-normalized -- pass it through unchanged; direction is applied downstream
	// by lessIsBetter in ZScore/PairwiseVerdict.
	SVS float64
	// BeginsDistributionChange marks a manual distribution-change boundary that
	// starts a new segment at this commit rank (closed-right).
	BeginsDistributionChange bool
}

// shiftFlags is the per-point result of trimmed-estimator detection.
type shiftFlags struct {
	isStep    bool
	isOutlier bool
}

// detectShifts ports _detect_shifts_with_trimmed_estimators (history.py:712) for
// one fingerprint's series. Returns flags in INPUT order. distributionCommits is
// the row-count rolling window (legacy Config.DISTRIBUTION_COMMITS).
func detectShifts(points []SeriesPoint, distributionCommits int) []shiftFlags {
	n := len(points)
	out := make([]shiftFlags, n)
	if n == 0 {
		return out
	}
	// Sort indices by (commit_timestamp, result_timestamp), stable.
	order := stableOrder(points, true)
	svs := make([]float64, n)
	for i, idx := range order {
		svs[i] = points[idx].SVS
	}
	// svs_diff = svs.diff() (first NaN)
	diff := make([]float64, n)
	diff[0] = math.NaN()
	for i := 1; i < n; i++ {
		diff[i] = svs[i] - svs[i-1]
	}
	// Clip diffs outside [q05, q95] to NaN.
	q05 := quantileLinear(diff, 0.05)
	q95 := quantileLinear(diff, 0.95)
	clipped := make([]float64, n)
	for i, d := range diff {
		if math.IsNaN(d) || d < q05 || d > q95 {
			clipped[i] = math.NaN()
		} else {
			clipped[i] = d
		}
	}
	rmean := rollingRowCount(clipped, distributionCommits, meanSkipNaN)
	rstd := rollingRowCount(clipped, distributionCommits, sampleStdSkipNaN)
	isShift := make([]bool, n)
	for i := range diff {
		z := (diff[i] - rmean[i]) / rstd[i]
		isShift[i] = !math.IsNaN(z) && math.Abs(z) > shiftZScoreThreshold
	}
	// reverts[i] = isShift[i] && isShift[i+1]; is_step = isShift & ~reverts &
	// ~reverts.shift(1, fill=false); is_outlier = isShift & reverts.
	reverts := make([]bool, n)
	for i := range n {
		reverts[i] = isShift[i] && i+1 < n && isShift[i+1]
	}
	for i := range n {
		prevRevert := i > 0 && reverts[i-1]
		step := isShift[i] && !reverts[i] && !prevRevert
		outlier := isShift[i] && reverts[i]
		out[order[i]] = shiftFlags{isStep: step, isOutlier: outlier}
	}
	return out
}

// stableOrder returns indices of `points` sorted by commit timestamp (and, when
// withResultTie, by result timestamp) using a stable sort — input order for
// exact-key ties, no other tiebreaker.
func stableOrder(points []SeriesPoint, withResultTie bool) []int {
	idx := make([]int, len(points))
	for i := range idx {
		idx[i] = i
	}
	sort.SliceStable(idx, func(a, b int) bool {
		ta, tb := points[idx[a]].CommitTimestamp, points[idx[b]].CommitTimestamp
		if !ta.Equal(tb) {
			return ta.Before(tb)
		}
		if withResultTie {
			return points[idx[a]].ResultTimestamp.Before(points[idx[b]].ResultTimestamp)
		}
		return false
	})
	return idx
}

// RollingStats is the per-point block (legacy HistorySampleZscoreStats). Nullable
// fields are nil where pandas yields NaN (outlier rows, insufficient data); Leaf B
// applies the legacy wire mapping per consumer.
type RollingStats struct {
	BeginsDistributionChange bool
	SegmentID                int
	RollingMeanExcludingThis *float64
	RollingMean              *float64
	Residual                 *float64
	RollingStddev            *float64
	IsStep                   bool
	IsOutlier                bool
}

// RollingStatsForSeries ports _add_rolling_stats_columns_to_df + detectShifts for
// one fingerprint's series. Returns one RollingStats per input point in INPUT
// order (it sorts internally by commit timestamp for the windowed computation,
// then maps each result back to its input position).
func RollingStatsForSeries(points []SeriesPoint, includeCurrent bool, distributionCommits int) []RollingStats {
	n := len(points)
	if n == 0 {
		return nil
	}
	flags := detectShifts(points, distributionCommits) // input order

	// Sort by commit timestamp (stable), carrying flags + begins.
	order := stableOrder(points, false)
	svs := make([]float64, n)
	tsv := make([]int64, n)
	begins := make([]bool, n)
	isOutlier := make([]bool, n)
	isStep := make([]bool, n)
	for i, idx := range order {
		svs[i] = points[idx].SVS
		tsv[i] = points[idx].CommitTimestamp.UnixNano()
		begins[i] = points[idx].BeginsDistributionChange
		isOutlier[i] = flags[idx].isOutlier
		isStep[i] = flags[idx].isStep
	}

	// segment_id = dense commit-rank closed-right cumulative sum of
	// begins_distribution_change (legacy _CommitIndexer(window=len+1), closed="right"
	// at history.py:615-625). Every row sharing a commit timestamp gets the SAME
	// segment_id, counting all begins flags at ranks <= theirs. A row-by-row cumsum
	// would split tied-timestamp rows whenever a boundary flag is not on the first of
	// them, misassigning a row to the prior segment and corrupting its rolling mean.
	ranks := denseRank(tsv)
	maxRank := ranks[n-1]
	rankCum := make([]int, maxRank+1) // rankCum[r] = total begins at ranks 1..r
	for i := range n {
		if begins[i] {
			rankCum[ranks[i]]++
		}
	}
	for r := 1; r <= maxRank; r++ {
		rankCum[r] += rankCum[r-1]
	}
	segment := make([]int, n)
	for i := range n {
		segment[i] = rankCum[ranks[i]]
	}

	// rolling_mean_excluding_this_commit: rolling mean of svs over (segment),
	// window=distributionCommits distinct commits, closed-left, NON-OUTLIER rows
	// only; segment-start NaN filled with own svs.
	rmeanExcl := groupedCommitRollingMean(svs, tsv, segment, isOutlier, distributionCommits, false)
	for i := range n {
		if !isOutlier[i] && math.IsNaN(rmeanExcl[i]) {
			rmeanExcl[i] = svs[i] // combine_first
		}
	}

	// rolling_mean: closed-right variant when includeCurrent, else == rmeanExcl.
	rmean := make([]float64, n)
	if includeCurrent {
		rmean = groupedCommitRollingMean(svs, tsv, segment, isOutlier, distributionCommits, true)
	} else {
		copy(rmean, rmeanExcl)
	}

	// residual = svs - rmeanExcl
	residual := make([]float64, n)
	for i := range n {
		residual[i] = svs[i] - rmeanExcl[i]
	}

	// rolling_stddev: sample std of residuals over the FINGERPRINT (not segment),
	// window=distributionCommits, closed per includeCurrent, NON-OUTLIER rows only.
	rstd := fingerprintCommitRollingStd(residual, tsv, isOutlier, distributionCommits, includeCurrent)

	// Assemble in INPUT order: sorted position i holds the stats for input index
	// order[i], so write each row back to out[order[i]].
	out := make([]RollingStats, n)
	for i := range n {
		out[order[i]] = RollingStats{
			BeginsDistributionChange: begins[i],
			SegmentID:                segment[i],
			RollingMeanExcludingThis: nilIfNaN(rmeanExcl[i]),
			RollingMean:              nilIfNaN(rmean[i]),
			Residual:                 nilIfNaN(residual[i]),
			RollingStddev:            nilIfNaN(rstd[i]),
			IsStep:                   isStep[i],
			IsOutlier:                isOutlier[i],
		}
	}
	return out
}

// BaselineDistribution returns the (rolling_mean, rolling_stddev) of the latest
// point by commit timestamp, computed with includeCurrent=true. Ports the reduction
// in _query_and_calculate_distribution_stats (history.py:408): sort by timestamp
// descending + drop_duplicates keeps one row per fingerprint at the max commit
// timestamp. We replicate it by selecting the first input index achieving the max
// timestamp (maxIdx).
//
// Among rows tied at the max timestamp the choice is immaterial when their stats
// match: tied rows share a dense commit-rank window AND (via the closed-right
// segment_id) the same segment even when a begins_distribution_change flag falls
// among them, so their rolling stats are identical. They differ only when one tied
// row is a detected outlier (nil stats); then maxIdx picks the first input-order
// tied row, which the oracle confirms is the row legacy's reduction keeps -- so the
// port matches legacy, returning (nil, nil) when that row is the outlier. pandas'
// tie order is not guaranteed by its API, so this case is pinned by a first-
// principles test, not a parity fixture. Returns (nil, nil) for an empty series.
func BaselineDistribution(points []SeriesPoint, distributionCommits int) (mean, stddev *float64) {
	if len(points) == 0 {
		return nil, nil
	}
	rs := RollingStatsForSeries(points, true, distributionCommits) // input order
	maxIdx := 0
	for i := 1; i < len(points); i++ {
		if points[i].CommitTimestamp.After(points[maxIdx].CommitTimestamp) {
			maxIdx = i
		}
	}
	return rs[maxIdx].RollingMean, rs[maxIdx].RollingStddev
}

// groupedCommitRollingMean computes the commit-rank rolling mean of svs within
// each segment, over non-outlier rows only; outlier rows get NaN. Rows are already
// sorted ascending by timestamp.
func groupedCommitRollingMean(svs []float64, tsv []int64, segment []int, isOutlier []bool, window int, closedRight bool) []float64 {
	out := make([]float64, len(svs))
	for i := range out {
		out[i] = math.NaN()
	}
	// group by segment over the non-outlier subset
	type sub struct{ idx []int }
	groups := map[int]*sub{}
	for i := range svs {
		if isOutlier[i] {
			continue
		}
		g, ok := groups[segment[i]]
		if !ok {
			g = &sub{}
			groups[segment[i]] = g
		}
		g.idx = append(g.idx, i)
	}
	for _, g := range groups {
		vals := make([]float64, len(g.idx))
		ts := make([]int64, len(g.idx))
		for k, i := range g.idx {
			vals[k] = svs[i]
			ts[k] = tsv[i]
		}
		res := rollingCommitRank(vals, ts, window, closedRight, meanSkipNaN)
		for k, i := range g.idx {
			out[i] = res[k]
		}
	}
	return out
}

// fingerprintCommitRollingStd computes the commit-rank rolling sample std of the
// residuals over the whole series (not segment), non-outlier rows only.
func fingerprintCommitRollingStd(residual []float64, tsv []int64, isOutlier []bool, window int, closedRight bool) []float64 {
	out := make([]float64, len(residual))
	for i := range out {
		out[i] = math.NaN()
	}
	var idx []int
	for i := range residual {
		if !isOutlier[i] {
			idx = append(idx, i)
		}
	}
	vals := make([]float64, len(idx))
	ts := make([]int64, len(idx))
	for k, i := range idx {
		vals[k] = residual[i]
		ts[k] = tsv[i]
	}
	res := rollingCommitRank(vals, ts, window, closedRight, sampleStdSkipNaN)
	for k, i := range idx {
		out[i] = res[k]
	}
	return out
}

func nilIfNaN(x float64) *float64 {
	if math.IsNaN(x) {
		return nil
	}
	v := x
	return &v
}
