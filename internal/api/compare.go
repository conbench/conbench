package api

import (
	"context"
	"math"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/service"
)

// CompareInput is the compare query: two explicit result ids and the two
// thresholds (defaulting to 5.0). A read, so GET with query params.
type CompareInput struct {
	BaselineResultID  string  `query:"baseline_result_id" required:"true" doc:"Baseline benchmark result id."`
	ContenderResultID string  `query:"contender_result_id" required:"true" doc:"Contender benchmark result id."`
	Threshold         float64 `query:"threshold" default:"5" doc:"Pairwise percent-change threshold."`
	ThresholdZ        float64 `query:"threshold_z" default:"5" doc:"Lookback z-score threshold."`
}

// CompareOutput carries a compare result body.
type CompareOutput struct {
	Body service.CompareResult
}

func (h *ReadHandler) getCompare(ctx context.Context, in *CompareInput) (*CompareOutput, error) {
	if err := validatePositiveCompareFloat(in.Threshold, "threshold"); err != nil {
		return nil, err
	}
	if err := validatePositiveCompareFloat(in.ThresholdZ, "threshold_z"); err != nil {
		return nil, err
	}
	result, err := h.reader.Compare(ctx, in.BaselineResultID, in.ContenderResultID, in.Threshold, in.ThresholdZ)
	if err != nil {
		return nil, mapReadError(err)
	}
	return &CompareOutput{Body: *result}, nil
}

func validatePositiveCompareFloat(v float64, field string) error {
	if math.IsNaN(v) || math.IsInf(v, 0) || v <= 0 {
		return huma.Error422UnprocessableEntity("invalid " + field + ": must be a finite number greater than zero")
	}
	return nil
}
