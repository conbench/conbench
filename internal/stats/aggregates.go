// Package stats ports Conbench's per-result statistics: the history fingerprint,
// the sample aggregates (mean/quantiles/stdev), and the single-value summary
// used to orient regressions. Behavior is pinned to the Python/numpy output via
// golden tests under testdata/.
package stats

import (
	"math"
	"sort"
)

// minSamplesForAggregates is the threshold below which the legacy Python
// implementation left quantile/spread aggregates unset and computed only mean.
const minSamplesForAggregates = 3

// Aggregates holds the per-result sample statistics. Mean is always present;
// the remaining fields are nil when there are fewer than three samples, matching
// the Python aggregation.
type Aggregates struct {
	Mean   float64
	Q1     *float64
	Q3     *float64
	Median *float64
	Min    *float64
	Max    *float64
	Stdev  *float64
	Iqr    *float64
}

// Aggregate computes the sample statistics for a successful result's
// measurements, ported from validate_and_aggregate_samples. The mean is always
// computed; quantiles, median, min, max, sample standard deviation (ddof=1), and
// the interquartile range are computed only when there are at least three
// samples. Numerics match numpy: percentiles use linear interpolation and the
// standard deviation divides by n-1.
func Aggregate(samples []float64) Aggregates {
	agg := Aggregates{Mean: mean(samples)}
	if len(samples) < minSamplesForAggregates {
		return agg
	}
	sorted := make([]float64, len(samples))
	copy(sorted, samples)
	sort.Float64s(sorted)

	q1 := percentile(sorted, 25)
	q3 := percentile(sorted, 75)
	median := percentile(sorted, 50)
	smin := sorted[0]
	smax := sorted[len(sorted)-1]
	stdev := stddev(samples, agg.Mean)
	iqr := q3 - q1

	agg.Q1 = &q1
	agg.Q3 = &q3
	agg.Median = &median
	agg.Min = &smin
	agg.Max = &smax
	agg.Stdev = &stdev
	agg.Iqr = &iqr
	return agg
}

func mean(xs []float64) float64 {
	var sum float64
	for _, x := range xs {
		sum += x
	}
	return sum / float64(len(xs))
}

// stddev is the sample standard deviation with ddof=1, matching
// numpy.std(samples, ddof=1).
func stddev(xs []float64, m float64) float64 {
	var ss float64
	for _, x := range xs {
		d := x - m
		ss += d * d
	}
	return math.Sqrt(ss / float64(len(xs)-1))
}

// percentile returns the q-th percentile (0..100) of an already-sorted slice
// using numpy's default "linear" interpolation.
func percentile(sorted []float64, q float64) float64 {
	if len(sorted) == 1 {
		return sorted[0]
	}
	idx := q / 100 * float64(len(sorted)-1)
	lo := math.Floor(idx)
	hi := math.Ceil(idx)
	if lo == hi {
		return sorted[int(idx)]
	}
	frac := idx - lo
	return sorted[int(lo)] + frac*(sorted[int(hi)]-sorted[int(lo)])
}
