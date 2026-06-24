package stats

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestZScoreFromFormula(t *testing.T) {
	p := func(v float64) *float64 { return &v }

	// x=1.5, mean=1.0, stddev=0.25 -> raw z = 2.0.
	got := ZScore(p(1.5), false, p(1.0), p(0.25))
	require.NotNil(t, got)
	assert.InDelta(t, 2.0, *got, 1e-9)

	// lessIsBetter flips the sign: an above-mean (slower) point becomes -2.0.
	got = ZScore(p(1.5), true, p(1.0), p(0.25))
	require.NotNil(t, got)
	assert.InDelta(t, -2.0, *got, 1e-9)

	// Exactly on the mean -> z is 0; the flip is skipped so it stays +0.0, never -0.0.
	// Compare raw bits: +0.0 is 0x0..0, -0.0 is 0x8..0, so this asserts both
	// "is zero" and "is positive zero" without a float-equality operator.
	got = ZScore(p(1.0), true, p(1.0), p(0.25))
	require.NotNil(t, got)
	assert.Equal(t, uint64(0), math.Float64bits(*got), "must be +0.0, not -0.0")

	// Nil inputs and zero stddev -> nil (no division).
	assert.Nil(t, ZScore(nil, false, p(1.0), p(0.25)))
	assert.Nil(t, ZScore(p(1.5), false, nil, p(0.25)))
	assert.Nil(t, ZScore(p(1.5), false, p(1.0), nil))
	assert.Nil(t, ZScore(p(1.5), false, p(1.0), p(0)))
}

type goldenZScore struct {
	DataPoint    *float64 `json:"data_point"`
	LessIsBetter bool     `json:"less_is_better"`
	DistMean     *float64 `json:"dist_mean"`
	DistStddev   *float64 `json:"dist_stddev"`
	ZScore       *float64 `json:"z_score"`
}

func TestZScoreGolden(t *testing.T) {
	b, err := os.ReadFile(filepath.Join("testdata", "zscore_golden.json"))
	require.NoError(t, err)
	var cases []goldenZScore
	require.NoError(t, json.Unmarshal(b, &cases))
	for i, c := range cases {
		got := ZScore(c.DataPoint, c.LessIsBetter, c.DistMean, c.DistStddev)
		if c.ZScore == nil {
			assert.Nil(t, got, "case %d", i)
			continue
		}
		require.NotNil(t, got, "case %d", i)
		assert.InDelta(t, *c.ZScore, *got, 1e-9, "case %d", i)
	}
}

func TestVerdictsFromFormula(t *testing.T) {
	p := func(v float64) *float64 { return &v }

	// pairwise, less_is_better (seconds): +10% contender is a regression.
	pw := PairwiseVerdict(1.0, 1.10, true, PairwisePercentThresholdDefault)
	require.NotNil(t, pw)
	assert.InDelta(t, -10.0, pw.PercentChange, 1e-9)
	assert.True(t, pw.RegressionIndicated)
	assert.False(t, pw.ImprovementIndicated)
	// The result echoes its threshold for the wire layer (Leaf B).
	assert.InDelta(t, PairwisePercentThresholdDefault, pw.PercentThreshold, 1e-9)

	// less_is_better: -10% (faster) contender is an improvement.
	pw = PairwiseVerdict(1.0, 0.90, true, PairwisePercentThresholdDefault)
	require.NotNil(t, pw)
	assert.InDelta(t, 10.0, pw.PercentChange, 1e-9)
	assert.False(t, pw.RegressionIndicated)
	assert.True(t, pw.ImprovementIndicated)

	// Float-clean strict boundary: (17-16)/16*100 == 6.25 exactly, so percent_change
	// == threshold -> NOT indicated (strict >, never >=). A naive "+5%" boundary like
	// (1.05-1.0) is an IEEE754 trap: it equals 0.050000000000000044, which DOES cross
	// a 5.0 threshold, so it would not test the boundary at all.
	pw = PairwiseVerdict(16.0, 17.0, false, 6.25)
	require.NotNil(t, pw)
	assert.InDelta(t, 6.25, pw.PercentChange, 1e-9)
	assert.False(t, pw.RegressionIndicated)
	assert.False(t, pw.ImprovementIndicated)

	// IEEE754 edge (parity with Python float64): (0.95-1.0) == -0.050000000000000044,
	// so after the less_is_better flip percent_change == 5.000000000000004 > 5.0 ->
	// improvement IS indicated. The booleans compare the raw float, not a rounded value.
	pw = PairwiseVerdict(1.0, 0.95, true, PairwisePercentThresholdDefault)
	require.NotNil(t, pw)
	assert.True(t, pw.ImprovementIndicated)
	assert.False(t, pw.RegressionIndicated)

	// higher_is_better (i/s): +10% contender is an improvement, not a regression.
	pw = PairwiseVerdict(1.0, 1.10, false, PairwisePercentThresholdDefault)
	require.NotNil(t, pw)
	assert.False(t, pw.RegressionIndicated)
	assert.True(t, pw.ImprovementIndicated)

	// baseline 0 -> nil (divide-by-zero guard).
	assert.Nil(t, PairwiseVerdict(0.0, 1.0, false, PairwisePercentThresholdDefault))

	// lookback: oriented z, strict > threshold (5). Strongly negative -> regression.
	lb := LookbackZVerdict(p(-7.0), ZScoreThresholdDefault)
	require.NotNil(t, lb)
	assert.True(t, lb.RegressionIndicated)
	assert.False(t, lb.ImprovementIndicated)
	// The result echoes the threshold and the raw input z for the wire layer.
	assert.InDelta(t, ZScoreThresholdDefault, lb.ZThreshold, 1e-9)
	assert.InDelta(t, -7.0, lb.ZScore, 1e-9)

	// Strongly positive -> improvement.
	lb = LookbackZVerdict(p(7.0), ZScoreThresholdDefault)
	require.NotNil(t, lb)
	assert.False(t, lb.RegressionIndicated)
	assert.True(t, lb.ImprovementIndicated)

	// Exactly -5 is NOT indicated (strict >).
	lb = LookbackZVerdict(p(-5.0), ZScoreThresholdDefault)
	require.NotNil(t, lb)
	assert.False(t, lb.RegressionIndicated)
	assert.False(t, lb.ImprovementIndicated)

	// nil / NaN z -> nil.
	assert.Nil(t, LookbackZVerdict(nil, ZScoreThresholdDefault))
	assert.Nil(t, LookbackZVerdict(p(math.NaN()), ZScoreThresholdDefault))
}

type goldenVerdict struct {
	LessIsBetter bool     `json:"less_is_better"`
	BaselineSVS  float64  `json:"baseline_svs"`
	ContenderSVS float64  `json:"contender_svs"`
	ZScore       *float64 `json:"z_score"`
	Pairwise     *struct {
		PercentChange        float64 `json:"percent_change"`
		PercentThreshold     float64 `json:"percent_threshold"`
		RegressionIndicated  bool    `json:"regression_indicated"`
		ImprovementIndicated bool    `json:"improvement_indicated"`
	} `json:"pairwise"`
	Lookback *struct {
		ZThreshold           float64 `json:"z_threshold"`
		ZScore               float64 `json:"z_score"`
		RegressionIndicated  bool    `json:"regression_indicated"`
		ImprovementIndicated bool    `json:"improvement_indicated"`
	} `json:"lookback"`
}

func TestVerdictGolden(t *testing.T) {
	b, err := os.ReadFile(filepath.Join("testdata", "verdict_golden.json"))
	require.NoError(t, err)
	var cases []goldenVerdict
	require.NoError(t, json.Unmarshal(b, &cases))
	for i, c := range cases {
		// Thread the per-case thresholds from the snapshot. Most cases carry the 5.0
		// defaults, but the strict-boundary case pins percent_threshold 6.25; using
		// the default here would flip its verdict and break parity.
		pwThreshold := PairwisePercentThresholdDefault
		if c.Pairwise != nil {
			pwThreshold = c.Pairwise.PercentThreshold
		}
		pw := PairwiseVerdict(c.BaselineSVS, c.ContenderSVS, c.LessIsBetter, pwThreshold)
		if c.Pairwise == nil {
			assert.Nil(t, pw, "pairwise case %d", i)
		} else {
			require.NotNil(t, pw, "pairwise case %d", i)
			// legacy rounds percent_change to 4 sigfigs; allow that tolerance. Only the
			// display value is rounded -- the indicators are computed from the raw float
			// on both sides, so they are asserted exactly.
			assert.InDelta(t, c.Pairwise.PercentChange, pw.PercentChange, 1e-2, "pairwise pct %d", i)
			assert.Equal(t, c.Pairwise.RegressionIndicated, pw.RegressionIndicated, "pairwise reg %d", i)
			assert.Equal(t, c.Pairwise.ImprovementIndicated, pw.ImprovementIndicated, "pairwise imp %d", i)
			assert.InDelta(t, pwThreshold, pw.PercentThreshold, 1e-9, "pairwise threshold echo %d", i)
		}
		zThreshold := ZScoreThresholdDefault
		if c.Lookback != nil {
			zThreshold = c.Lookback.ZThreshold
		}
		lb := LookbackZVerdict(c.ZScore, zThreshold)
		if c.Lookback == nil {
			assert.Nil(t, lb, "lookback case %d", i)
		} else {
			require.NotNil(t, lb, "lookback case %d", i)
			assert.Equal(t, c.Lookback.RegressionIndicated, lb.RegressionIndicated, "lookback reg %d", i)
			assert.Equal(t, c.Lookback.ImprovementIndicated, lb.ImprovementIndicated, "lookback imp %d", i)
			assert.InDelta(t, zThreshold, lb.ZThreshold, 1e-9, "lookback threshold echo %d", i)
			assert.InDelta(t, *c.ZScore, lb.ZScore, 1e-9, "lookback z echo %d", i)
		}
	}
}
