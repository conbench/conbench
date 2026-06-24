package stats

import "math"

// ZScore ports _calculate_z_score (history.py:685). Returns nil if any input is
// nil or distStddev == 0. Sign-flips (x-1) only when lessIsBetter AND the score is
// non-zero (the legacy `if z_score and ...` guard, avoiding -0.0).
func ZScore(dataPoint *float64, lessIsBetter bool, distMean, distStddev *float64) *float64 {
	if dataPoint == nil || distMean == nil || distStddev == nil || *distStddev == 0 {
		return nil
	}
	z := (*dataPoint - *distMean) / *distStddev
	if z != 0 && lessIsBetter {
		z = -z
	}
	return &z
}

// PairwiseResult ports pairwise_analysis. PercentChange is full precision (Leaf B
// rounds for the wire); the booleans use the unrounded value and strict >.
type PairwiseResult struct {
	PercentChange        float64
	PercentThreshold     float64
	RegressionIndicated  bool
	ImprovementIndicated bool
}

// PairwiseVerdict returns nil if baselineSVS == 0 (legacy divide-by-zero guard).
func PairwiseVerdict(baselineSVS, contenderSVS float64, lessIsBetter bool, percentThreshold float64) *PairwiseResult {
	if baselineSVS == 0 {
		return nil
	}
	rel := (contenderSVS - baselineSVS) / math.Abs(baselineSVS)
	if lessIsBetter {
		rel = -rel
	}
	pct := rel * 100.0
	return &PairwiseResult{
		PercentChange:        pct,
		PercentThreshold:     percentThreshold,
		RegressionIndicated:  -pct > percentThreshold,
		ImprovementIndicated: pct > percentThreshold,
	}
}

// LookbackResult ports lookback_z_score_analysis.
type LookbackResult struct {
	ZThreshold           float64
	ZScore               float64
	RegressionIndicated  bool
	ImprovementIndicated bool
}

// LookbackZVerdict returns nil if zscore is nil or NaN. Strict > (compare.py:273).
func LookbackZVerdict(zscore *float64, thresholdZ float64) *LookbackResult {
	if zscore == nil || math.IsNaN(*zscore) {
		return nil
	}
	z := *zscore
	return &LookbackResult{
		ZThreshold:           thresholdZ,
		ZScore:               z,
		RegressionIndicated:  -z > thresholdZ,
		ImprovementIndicated: z > thresholdZ,
	}
}
