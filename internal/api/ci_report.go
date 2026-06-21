package api

import (
	"context"
	"errors"
	"math"
	"net/http"
	"reflect"
	"strings"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/stats"
)

// CIReportHandler serves the PR/CI report endpoint. It is a read-only API
// surface over the CI report service.
type CIReportHandler struct {
	reporter *service.CIReporter
}

// NewCIReportHandler builds a CIReportHandler over the report service.
func NewCIReportHandler(reporter *service.CIReporter) *CIReportHandler {
	return &CIReportHandler{reporter: reporter}
}

// Register wires the CI report operation onto a huma API.
func (h *CIReportHandler) Register(api huma.API) {
	huma.Register(api, huma.Operation{
		OperationID: "get-ci-report",
		Summary:     "Get a PR/CI benchmark report",
		Method:      http.MethodGet,
		Path:        "/api/ci/report",
	}, h.getReport)
}

// CIReportInput is the report selector. repository+commit_sha select all runs
// for a commit; run_ids can narrow the selector or stand alone.
type CIReportInput struct {
	Repository     string             `query:"repository" doc:"Repository URL."`
	CommitSHA      string             `query:"commit_sha" doc:"Commit SHA."`
	RunIDs         string             `query:"run_ids" doc:"Comma-separated contender run IDs."`
	BaselineRunIDs string             `query:"baseline_run_ids" doc:"Comma-separated explicit baseline run IDs, paired by position with run_ids."`
	Baseline       string             `query:"baseline" enum:"fork_point,parent,latest_default" doc:"Automatic baseline selector."`
	Threshold      optionalFloatParam `query:"threshold" doc:"Pairwise percent-change threshold. Defaults to 5."`
	ThresholdZ     optionalFloatParam `query:"threshold_z" doc:"Lookback z-score threshold. Defaults to 5."`
}

type optionalFloatParam struct {
	Value float64
	IsSet bool
}

func (p optionalFloatParam) Schema(r huma.Registry) *huma.Schema {
	return huma.SchemaFromType(r, reflect.TypeFor[float64]())
}

func (p *optionalFloatParam) Receiver() reflect.Value {
	return reflect.ValueOf(p).Elem().FieldByName("Value")
}

func (p *optionalFloatParam) OnParamSet(isSet bool, _ any) {
	p.IsSet = isSet
}

// CIReportOutput carries a CI report body.
type CIReportOutput struct {
	Body service.CIReport
}

func (h *CIReportHandler) getReport(ctx context.Context, in *CIReportInput) (*CIReportOutput, error) {
	threshold, err := parsePositiveReportFloat(in.Threshold, stats.PairwisePercentThresholdDefault, "threshold")
	if err != nil {
		return nil, err
	}
	thresholdZ, err := parsePositiveReportFloat(in.ThresholdZ, stats.ZScoreThresholdDefault, "threshold_z")
	if err != nil {
		return nil, err
	}
	report, err := h.reporter.Report(ctx, service.CIReportQuery{
		Repository:     in.Repository,
		CommitSHA:      in.CommitSHA,
		RunIDs:         parseRunIDs(in.RunIDs),
		BaselineRunIDs: parseRunIDs(in.BaselineRunIDs),
		Baseline:       service.CIReportBaseline(in.Baseline),
		Threshold:      threshold,
		ThresholdZ:     thresholdZ,
	})
	if err != nil {
		return nil, mapCIReportError(err)
	}
	return &CIReportOutput{Body: *report}, nil
}

func parseRunIDs(raw string) []string {
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		if id := strings.TrimSpace(part); id != "" {
			out = append(out, id)
		}
	}
	return out
}

func parsePositiveReportFloat(raw optionalFloatParam, fallback float64, field string) (float64, error) {
	if !raw.IsSet {
		return fallback, nil
	}
	v := raw.Value
	if math.IsNaN(v) || math.IsInf(v, 0) || v <= 0 {
		return 0, huma.Error422UnprocessableEntity("invalid " + field + ": must be a finite number greater than zero")
	}
	return v, nil
}

func mapCIReportError(err error) error {
	var ve *service.ValidationError
	if errors.As(err, &ve) {
		return huma.Error422UnprocessableEntity(ve.Message)
	}
	if errors.Is(err, service.ErrNotFound) {
		return huma.Error404NotFound("not found")
	}
	return err
}
