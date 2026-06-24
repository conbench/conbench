package service

import (
	"context"
	"errors"
	"fmt"
	"math"

	"github.com/conbench/conbench/internal/stats"
	"github.com/conbench/conbench/internal/storage"
	"github.com/conbench/conbench/internal/units"
)

// ErrNotComparable is returned when two results cannot be compared (a failed
// result, a unit mismatch, or different history fingerprints). The API maps it to
// 422. The wrapped message names the reason.
var ErrNotComparable = errors.New("not comparable")

// CompareSide identifies one side of a comparison.
type CompareSide struct {
	BenchmarkResultID string  `json:"benchmark_result_id"`
	SVS               float64 `json:"single_value_summary"`
	RunID             string  `json:"run_id"`
}

// PairwiseAnalysis is the direct baseline-vs-contender SVS verdict. The blank
// nullable marker makes huma emit the schema as nullable (it is null when the
// baseline SVS is 0); see the Commit type in read.go for the same pattern.
type PairwiseAnalysis struct {
	_                    struct{} `json:"-" nullable:"true"`
	PercentChange        float64  `json:"percent_change"`
	PercentThreshold     float64  `json:"percent_threshold"`
	RegressionIndicated  bool     `json:"regression_indicated"`
	ImprovementIndicated bool     `json:"improvement_indicated"`
}

// LookbackAnalysis is the contender's z-score verdict against its baseline
// window. Null when there is no baseline commit, the window is not single-unit,
// or the z-score is not computable.
type LookbackAnalysis struct {
	_                    struct{} `json:"-" nullable:"true"`
	ZScore               float64  `json:"z_score"`
	ZThreshold           float64  `json:"z_threshold"`
	RegressionIndicated  bool     `json:"regression_indicated"`
	ImprovementIndicated bool     `json:"improvement_indicated"`
}

// CompareAnalysis holds the two verdicts; either may be null.
type CompareAnalysis struct {
	Pairwise       *PairwiseAnalysis `json:"pairwise"`
	LookbackZScore *LookbackAnalysis `json:"lookback_z_score"`
}

// CompareResult is the GET /api/compare/benchmark-results response.
type CompareResult struct {
	Unit         string          `json:"unit"`
	LessIsBetter bool            `json:"less_is_better"`
	Baseline     CompareSide     `json:"baseline"`
	Contender    CompareSide     `json:"contender"`
	Analysis     CompareAnalysis `json:"analysis"`
}

// Compare loads two results, validates they are comparable, and returns the
// pairwise + lookback-z analysis. thresholds default to 5.0 at the API layer.
func (r *Reader) Compare(ctx context.Context, baselineID, contenderID string, threshold, thresholdZ float64) (*CompareResult, error) {
	baseline, err := r.loadCompareResult(ctx, baselineID)
	if err != nil {
		return nil, err
	}
	contender, err := r.loadCompareResult(ctx, contenderID)
	if err != nil {
		return nil, err
	}

	baseSVS, err := comparableSVS(baseline)
	if err != nil {
		return nil, err
	}
	contSVS, err := comparableSVS(contender)
	if err != nil {
		return nil, err
	}

	unit := *contender.Unit
	if *baseline.Unit != unit {
		return nil, fmt.Errorf("%w: units differ (%s vs %s)", ErrNotComparable, *baseline.Unit, unit)
	}
	// comparableSVS already computed both SVS values in best mode, which rejects an
	// unknown unit, so this lookup cannot fail here; the error guard is defensive.
	lessIsBetter, err := units.LessIsBetter(unit)
	if err != nil {
		return nil, fmt.Errorf("%w: unknown unit %q", ErrNotComparable, unit)
	}
	if baseline.HistoryFingerprint != contender.HistoryFingerprint {
		return nil, fmt.Errorf("%w: history fingerprints differ", ErrNotComparable)
	}

	lookback, err := r.lookbackAnalysis(ctx, lookbackInput{
		contender: contender, baseline: baseline, contSVS: contSVS,
		unit: unit, lessIsBetter: lessIsBetter, thresholdZ: thresholdZ,
	})
	if err != nil {
		return nil, err
	}
	out := &CompareResult{
		Unit:         unit,
		LessIsBetter: lessIsBetter,
		Baseline:     CompareSide{BenchmarkResultID: baseline.ID, SVS: baseSVS, RunID: baseline.RunID},
		Contender:    CompareSide{BenchmarkResultID: contender.ID, SVS: contSVS, RunID: contender.RunID},
		Analysis: CompareAnalysis{
			Pairwise:       pairwiseAnalysis(baseSVS, contSVS, lessIsBetter, threshold),
			LookbackZScore: lookback,
		},
	}
	return out, nil
}

// loadCompareResult fetches one result's compare fields, mapping not-found.
func (r *Reader) loadCompareResult(ctx context.Context, id string) (storage.CompareResultRow, error) {
	row, err := r.store.GetResultForCompare(ctx, id)
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return storage.CompareResultRow{}, ErrNotFound
		}
		return storage.CompareResultRow{}, fmt.Errorf("load result for compare: %w", err)
	}
	return row, nil
}

// comparableSVS returns the result's single value summary, or ErrNotComparable
// when the result failed (error set, or no usable measurement).
func comparableSVS(row storage.CompareResultRow) (float64, error) {
	if row.Error != nil || row.Unit == nil || len(row.Data) == 0 {
		return 0, fmt.Errorf("%w: result %s failed or has no measurement", ErrNotComparable, row.ID)
	}
	data := nonNullFloats(row.Data)
	if data == nil {
		return 0, fmt.Errorf("%w: result %s failed or has no measurement", ErrNotComparable, row.ID)
	}
	svs, err := stats.SingleValueSummary(data, row.Unit, defaultSVSMode)
	if err != nil {
		return 0, fmt.Errorf("%w: %v", ErrNotComparable, err)
	}
	if math.IsNaN(svs) {
		return 0, fmt.Errorf("%w: result %s has no single value summary", ErrNotComparable, row.ID)
	}
	return svs, nil
}

// pairwiseAnalysis maps the engine verdict to the wire type, rounding the display
// percent for the wire while keeping the engine's raw-float booleans.
func pairwiseAnalysis(baseSVS, contSVS float64, lessIsBetter bool, threshold float64) *PairwiseAnalysis {
	v := stats.PairwiseVerdict(baseSVS, contSVS, lessIsBetter, threshold)
	if v == nil {
		return nil
	}
	return &PairwiseAnalysis{
		PercentChange:        round4SigFigs(v.PercentChange),
		PercentThreshold:     v.PercentThreshold,
		RegressionIndicated:  v.RegressionIndicated,
		ImprovementIndicated: v.ImprovementIndicated,
	}
}

// lookbackInput carries the contender's z-score inputs for the baseline window.
type lookbackInput struct {
	contender    storage.CompareResultRow
	baseline     storage.CompareResultRow
	contSVS      float64
	unit         string
	lessIsBetter bool
	thresholdZ   float64
}

// lookbackAnalysis scores the contender against its default-branch baseline
// window (commit.timestamp <= baseline commit). Returns (nil, nil) for the
// legitimately-absent cases: no baseline commit, an empty window, a mixed-unit
// window, or an uncomputable z-score. A query failure or data-integrity fault
// propagates as an error so the caller can surface it as a 500, matching
// History().
func (r *Reader) lookbackAnalysis(ctx context.Context, in lookbackInput) (*LookbackAnalysis, error) {
	if in.baseline.CommitID == nil || in.baseline.CommitTimestamp == nil {
		return nil, nil
	}
	rows, err := r.store.SelectHistoryForFingerprintAsOf(ctx, in.contender.HistoryFingerprint, *in.baseline.CommitTimestamp)
	if err != nil {
		return nil, fmt.Errorf("lookback window: %w", err)
	}
	if len(rows) == 0 {
		return nil, nil
	}
	points := make([]stats.SeriesPoint, 0, len(rows))
	for _, row := range rows {
		if !sameUnitPtr(row.Unit, &in.unit) { // mixed-unit window: no distribution across scales
			return nil, nil
		}
		svs, _, err := historySVS(row.Unit, row.Data)
		if err != nil {
			return nil, err
		}
		point, err := seriesPointFromRow(row, svs)
		if err != nil {
			return nil, err
		}
		points = append(points, point)
	}
	mean, stddev := stats.BaselineDistribution(points, stats.DistributionCommitsDefault)
	z := stats.ZScore(&in.contSVS, in.lessIsBetter, mean, stddev)
	v := stats.LookbackZVerdict(z, in.thresholdZ)
	if v == nil {
		return nil, nil // z not computable (nil/zero-stddev/NaN) — a legitimate absent lookback
	}
	return &LookbackAnalysis{
		ZScore:               round4SigFigs(v.ZScore),
		ZThreshold:           v.ZThreshold,
		RegressionIndicated:  v.RegressionIndicated,
		ImprovementIndicated: v.ImprovementIndicated,
	}, nil
}

// round4SigFigs rounds x to 4 significant figures for display only. Verdict
// booleans never use this value; only the wire number is rounded.
func round4SigFigs(x float64) float64 {
	if x == 0 || math.IsNaN(x) || math.IsInf(x, 0) {
		return x
	}
	power := 4 - int(math.Ceil(math.Log10(math.Abs(x))))
	mag := math.Pow(10, float64(power))
	return math.Round(x*mag) / mag
}
