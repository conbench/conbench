package stats

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMeanSkipNaN(t *testing.T) {
	assert.InDelta(t, 2.0, meanSkipNaN([]float64{1, math.NaN(), 3}), 1e-12)
	assert.True(t, math.IsNaN(meanSkipNaN([]float64{math.NaN()})))
}

func TestSampleStdSkipNaN(t *testing.T) {
	// sample stddev (ddof=1) of [2,4,4,4,5,5,7,9] = 2.138089935...
	got := sampleStdSkipNaN([]float64{2, 4, 4, 4, 5, 5, 7, 9})
	assert.InDelta(t, 2.13808993529939, got, 1e-12)
	assert.True(t, math.IsNaN(sampleStdSkipNaN([]float64{5})), "n=1 -> NaN")
	assert.InDelta(t, 0.0, sampleStdSkipNaN([]float64{3, 3, 3}), 1e-12)
}

func TestQuantileLinear(t *testing.T) {
	// numpy/pandas linear quantile of [1,2,3,4]: q=0.05 -> 1.15, q=0.95 -> 3.85
	assert.InDelta(t, 1.15, quantileLinear([]float64{1, 2, 3, 4}, 0.05), 1e-12)
	assert.InDelta(t, 3.85, quantileLinear([]float64{1, 2, 3, 4}, 0.95), 1e-12)
	// NaN entries are skipped
	assert.InDelta(t, 2.0, quantileLinear([]float64{math.NaN(), 2}, 0.5), 1e-12)
}

func TestDenseRank(t *testing.T) {
	assert.Equal(t, []int{1, 2, 2, 3}, denseRank([]int64{10, 20, 20, 30}))
}

func TestRollingRowCountMean(t *testing.T) {
	// window=2, min_periods=1, skip NaN. Input [NaN,1,3,5].
	// per-row windows: [NaN]->NaN-skip->NaN(no value); [NaN,1]->1; [1,3]->2; [3,5]->4
	got := rollingRowCount([]float64{math.NaN(), 1, 3, 5}, 2, meanSkipNaN)
	assert.True(t, math.IsNaN(got[0]))
	assert.InDelta(t, 1.0, got[1], 1e-12)
	assert.InDelta(t, 2.0, got[2], 1e-12)
	assert.InDelta(t, 4.0, got[3], 1e-12)
}

func TestRollingCommitRankMean(t *testing.T) {
	// timestamps (ranks 1,2,2,3), window=2 distinct commits.
	vals := []float64{1, 2, 4, 8}
	tsv := []int64{10, 20, 20, 30}
	// closed-right (inclusive): rank r window = ranks (r-2, r].
	// i0 r1: ranks(−1,1]={1} -> mean(1)=1
	// i1 r2: ranks(0,2]={1,2,4} -> mean=2.333...
	// i2 r2: same window -> 2.333...
	// i3 r3: ranks(1,3]={2,4,8} -> mean=4.666...
	got := rollingCommitRank(vals, tsv, 2, true, meanSkipNaN)
	assert.InDelta(t, 1.0, got[0], 1e-12)
	assert.InDelta(t, 7.0/3.0, got[1], 1e-12)
	assert.InDelta(t, 7.0/3.0, got[2], 1e-12)
	assert.InDelta(t, 14.0/3.0, got[3], 1e-12)
}

func TestRollingCommitRankMeanClosedLeft(t *testing.T) {
	// Same input; closed-LEFT excludes the current rank: rank r window = ranks [r-2, r).
	vals := []float64{1, 2, 4, 8}
	tsv := []int64{10, 20, 20, 30}
	// i0 r1: ranks[-1,1) = {}        -> NaN (empty window, min_periods=1)
	// i1 r2: ranks[0,2)  = {1}       -> 1
	// i2 r2: same window             -> 1
	// i3 r3: ranks[1,3)  = {1,2,4}   -> 7/3
	got := rollingCommitRank(vals, tsv, 2, false, meanSkipNaN)
	assert.True(t, math.IsNaN(got[0]))
	assert.InDelta(t, 1.0, got[1], 1e-12)
	assert.InDelta(t, 1.0, got[2], 1e-12)
	assert.InDelta(t, 7.0/3.0, got[3], 1e-12)
}
