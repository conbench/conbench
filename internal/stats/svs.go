package stats

import (
	"fmt"
	"math"

	"github.com/conbench/conbench/internal/units"
)

// SVS mode names, mirroring the legacy SVS_TYPE config value: "best" is the
// default.
const (
	SVSModeBest = "best"
	SVSModeMean = "mean"
)

// IsFailed reports whether a result should be treated as failed, ported from
// BenchmarkResult.is_failed. A result is failed when it has no unit, no data, a
// recorded error, or any null/empty iteration (do_iteration_samples_look_like_error).
func IsFailed(unit *string, data []*float64, hasError bool) bool {
	if unit == nil || data == nil || hasError {
		return true
	}
	if len(data) == 0 {
		return true
	}
	for _, d := range data {
		if d == nil {
			return true
		}
	}
	return false
}

// Measurements returns the non-null iteration values for a successful result,
// or an empty slice for a failed one, ported from BenchmarkResult.measurements.
func Measurements(unit *string, data []*float64, hasError bool) []float64 {
	if IsFailed(unit, data, hasError) {
		return []float64{}
	}
	out := make([]float64, len(data))
	for i, d := range data {
		out[i] = *d
	}
	return out
}

// SVSType returns the label describing how the single value summary is derived,
// ported from BenchmarkResult.svs_type: "mean" in mean mode, "n/a" when the unit
// is missing, otherwise "min" or "max" by the unit's less_is_better direction.
// An unknown mode is an error (Python asserts Config.SVS_TYPE == "best").
func SVSType(unit *string, mode string) (string, error) {
	switch mode {
	case SVSModeMean:
		return "mean", nil
	case SVSModeBest:
		if unit == nil {
			return "n/a", nil
		}
		lessIsBetter, err := units.LessIsBetter(*unit)
		if err != nil {
			return "", err
		}
		if lessIsBetter {
			return "min", nil
		}
		return "max", nil
	default:
		return "", unknownModeError(mode)
	}
}

// SingleValueSummary computes the single value that represents a result, ported
// from BenchmarkResult._single_value_summary. It returns NaN when there are no
// measurements (matching Python's math.nan). In mean mode it returns the mean;
// in best mode it returns the minimum when lower is better for the unit, else
// the maximum. An unknown mode is an error, but — matching Python's ordering —
// only after the empty-measurements check, which short-circuits to NaN first.
func SingleValueSummary(measurements []float64, unit *string, mode string) (float64, error) {
	if len(measurements) == 0 {
		return math.NaN(), nil
	}
	switch mode {
	case SVSModeMean:
		return mean(measurements), nil
	case SVSModeBest:
		if unit == nil {
			return 0, fmt.Errorf("best-mode summary requires a unit")
		}
		lessIsBetter, err := units.LessIsBetter(*unit)
		if err != nil {
			return 0, err
		}
		if lessIsBetter {
			return minOf(measurements), nil
		}
		return maxOf(measurements), nil
	default:
		return 0, unknownModeError(mode)
	}
}

func unknownModeError(mode string) error {
	return fmt.Errorf("unknown SVS mode %q (want %q or %q)", mode, SVSModeMean, SVSModeBest)
}

func minOf(xs []float64) float64 {
	m := xs[0]
	for _, x := range xs[1:] {
		if x < m {
			m = x
		}
	}
	return m
}

func maxOf(xs []float64) float64 {
	m := xs[0]
	for _, x := range xs[1:] {
		if x > m {
			m = x
		}
	}
	return m
}
