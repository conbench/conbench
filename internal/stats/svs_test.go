package stats

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestIsFailedMatchesPythonGolden pins IsFailed to BenchmarkResult.is_failed:
// a missing unit, missing/empty data, a present error, or any null iteration
// marks the result failed.
func TestIsFailedMatchesPythonGolden(t *testing.T) {
	g := loadAggSvsGolden(t)
	for _, c := range g.SVS {
		got := IsFailed(c.Unit, c.Data, c.HasError)
		assert.Equalf(t, c.IsFailed, got, "IsFailed(%v, %v, %v)", c.Unit, c.Data, c.HasError)
	}
}

// TestMeasurementsMatchesPythonGolden pins Measurements: the dereferenced data
// for a successful result, or an empty slice for a failed one.
func TestMeasurementsMatchesPythonGolden(t *testing.T) {
	g := loadAggSvsGolden(t)
	for _, c := range g.SVS {
		got := Measurements(c.Unit, c.Data, c.HasError)
		if len(got) != len(c.Measurements) {
			assert.Lenf(t, got, len(c.Measurements), "Measurements len (case %v)", c.Data)
			continue
		}
		for i := range got {
			assert.Truef(t, closeEnough(got[i], c.Measurements[i]),
				"Measurements[%d] = %v, want %v", i, got[i], c.Measurements[i])
		}
	}
}

// TestSVSTypeMatchesPythonGolden pins SVSType across both modes, the n/a case
// for a missing unit, and the less_is_better-driven min/max selection.
func TestSVSTypeMatchesPythonGolden(t *testing.T) {
	g := loadAggSvsGolden(t)
	for _, c := range g.SVS {
		got, err := SVSType(c.Unit, c.Mode)
		require.NoErrorf(t, err, "SVSType(%v, %q)", c.Unit, c.Mode)
		assert.Equalf(t, c.SVSType, got, "SVSType(%v, %q)", c.Unit, c.Mode)
	}
}

// TestSingleValueSummaryMatchesPythonGolden pins the summary value: NaN for
// failed/empty results, the mean in mean mode, and min/max by direction in
// best mode.
func TestSingleValueSummaryMatchesPythonGolden(t *testing.T) {
	g := loadAggSvsGolden(t)
	for _, c := range g.SVS {
		measurements := Measurements(c.Unit, c.Data, c.HasError)
		got, err := SingleValueSummary(measurements, c.Unit, c.Mode)
		require.NoErrorf(t, err, "SingleValueSummary(%v, %v, %q)", measurements, c.Unit, c.Mode)
		if c.SVS == nil {
			assert.Truef(t, math.IsNaN(got), "SingleValueSummary(%v) = %v, want NaN", measurements, got)
			continue
		}
		assert.Truef(t, closeEnough(got, *c.SVS),
			"SingleValueSummary(%v, %v, %q) = %v, want %v", measurements, c.Unit, c.Mode, got, *c.SVS)
	}
}

// TestSVSRejectsUnknownMode pins fail-closed behavior for a misconfigured
// SVS_TYPE: an unknown mode is an error, not a silent fall-through to "best".
// Python asserts Config.SVS_TYPE == "best" after the "mean" check.
func TestSVSRejectsUnknownMode(t *testing.T) {
	unit := "s"
	_, err := SVSType(&unit, "bogus")
	require.Error(t, err, "SVSType with unknown mode: want error, got nil")
	// With measurements present, the unknown mode must surface as an error.
	_, err = SingleValueSummary([]float64{1, 2, 3}, &unit, "bogus")
	require.Error(t, err, "SingleValueSummary with unknown mode: want error, got nil")
	// With no measurements, the summary is NaN regardless of mode, matching
	// Python's empty-check-first ordering (the mode assert is never reached).
	got, err := SingleValueSummary(nil, &unit, "bogus")
	require.NoError(t, err, "SingleValueSummary(empty) unexpected error")
	assert.Truef(t, math.IsNaN(got), "SingleValueSummary(empty) = %v, want NaN", got)
}
