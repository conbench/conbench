package stats

import (
	"math"
	"slices"
	"sort"
)

// meanSkipNaN returns the mean of the non-NaN values, or NaN if there are none
// (pandas mean skips NaN).
func meanSkipNaN(xs []float64) float64 {
	sum, n := 0.0, 0
	for _, x := range xs {
		if !math.IsNaN(x) {
			sum += x
			n++
		}
	}
	if n == 0 {
		return math.NaN()
	}
	return sum / float64(n)
}

// sampleStdSkipNaN returns the sample standard deviation (ddof=1) of the non-NaN
// values, or NaN if fewer than two (pandas std default, skipping NaN).
func sampleStdSkipNaN(xs []float64) float64 {
	clean := make([]float64, 0, len(xs))
	for _, x := range xs {
		if !math.IsNaN(x) {
			clean = append(clean, x)
		}
	}
	if len(clean) < 2 {
		return math.NaN()
	}
	m := meanSkipNaN(clean)
	ss := 0.0
	for _, x := range clean {
		d := x - m
		ss += d * d
	}
	return math.Sqrt(ss / float64(len(clean)-1))
}

// quantileLinear returns the q-quantile (0<=q<=1) of the non-NaN values using
// numpy/pandas "linear" interpolation. Returns NaN if there are no values.
func quantileLinear(xs []float64, q float64) float64 {
	clean := make([]float64, 0, len(xs))
	for _, x := range xs {
		if !math.IsNaN(x) {
			clean = append(clean, x)
		}
	}
	if len(clean) == 0 {
		return math.NaN()
	}
	sort.Float64s(clean)
	if len(clean) == 1 {
		return clean[0]
	}
	pos := q * float64(len(clean)-1)
	lo := int(math.Floor(pos))
	hi := int(math.Ceil(pos))
	if lo == hi {
		return clean[lo]
	}
	frac := pos - float64(lo)
	return clean[lo] + (clean[hi]-clean[lo])*frac
}

// denseRank returns the 1-based dense rank of each value (equal values share a
// rank). Matches pandas Series.rank(method="dense").
func denseRank(xs []int64) []int {
	uniq := append([]int64(nil), xs...)
	slices.Sort(uniq)
	rankOf := make(map[int64]int, len(uniq))
	r := 0
	for i, v := range uniq {
		if i == 0 || v != uniq[i-1] {
			r++
			rankOf[v] = r
		}
	}
	out := make([]int, len(xs))
	for i, v := range xs {
		out[i] = rankOf[v]
	}
	return out
}

// rollingRowCount applies reduce over a trailing row-count window of size
// `window` (min_periods=1: the first window-1 rows reduce over the rows seen so
// far). Matches pandas .rolling(window, min_periods=1).<reduce>().
func rollingRowCount(xs []float64, window int, reduce func([]float64) float64) []float64 {
	out := make([]float64, len(xs))
	for i := range xs {
		lo := max(i-window+1, 0)
		out[i] = reduce(xs[lo : i+1])
	}
	return out
}

// rollingCommitRank applies reduce over a window of the last `window` distinct
// commits (dense rank of timestamps), per the legacy _CommitIndexer. When
// closedRight the current rank is included; otherwise it is excluded. `vals` and
// `timestamps` are aligned and sorted ascending by timestamp. min_periods=1.
func rollingCommitRank(vals []float64, timestamps []int64, window int, closedRight bool, reduce func([]float64) float64) []float64 {
	ranks := denseRank(timestamps)
	out := make([]float64, len(vals))
	for i := range vals {
		// Window = elements whose rank is in the half-open interval determined by
		// `closed`. closedRight: (rank-window, rank]; closedLeft: [rank-window, rank).
		var lo, hi int // [lo, hi) over the sorted slice
		if closedRight {
			hi = upperCount(ranks, ranks[i])        // first idx with rank > rank[i]
			lo = upperCount(ranks, ranks[i]-window) // first idx with rank > rank[i]-window
		} else {
			hi = lowerCount(ranks, ranks[i])        // first idx with rank >= rank[i]
			lo = lowerCount(ranks, ranks[i]-window) // first idx with rank >= rank[i]-window
		}
		if lo >= hi {
			out[i] = math.NaN() // empty window (min_periods=1 yields NaN with no rows)
			continue
		}
		out[i] = reduce(vals[lo:hi])
	}
	return out
}

// lowerCount returns the number of leading elements of the ascending slice with
// value < v (i.e. searchsorted side="left").
func lowerCount(ranks []int, v int) int {
	return sort.Search(len(ranks), func(i int) bool { return ranks[i] >= v })
}

// upperCount returns the number of leading elements of the ascending slice with
// value <= v (i.e. searchsorted side="right").
func upperCount(ranks []int, v int) int {
	return sort.Search(len(ranks), func(i int) bool { return ranks[i] > v })
}
