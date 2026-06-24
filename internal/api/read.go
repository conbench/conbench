package api

import (
	"context"
	"errors"
	"net/http"
	"strings"

	"github.com/danielgtaylor/huma/v2"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/conbench/conbench/internal/service"
)

// ReadHandler serves the result-detail and history read endpoints over the read
// service. These are unauthenticated in the walking skeleton; the SPA and CLI
// consume them directly. Like the write handler, it owns no business logic.
type ReadHandler struct {
	reader *service.Reader
}

// NewReadHandler builds a ReadHandler over the read service.
func NewReadHandler(reader *service.Reader) *ReadHandler {
	return &ReadHandler{reader: reader}
}

// Register wires the read operations onto a huma API.
func (h *ReadHandler) Register(api huma.API) {
	huma.Register(api, huma.Operation{
		OperationID: "get-benchmark-result",
		Summary:     "Get a benchmark result",
		Method:      http.MethodGet,
		Path:        "/api/benchmark-results/{id}",
	}, h.getResult)

	huma.Register(api, huma.Operation{
		OperationID: "get-history-for-result",
		Summary:     "Get the history series for a benchmark result",
		Method:      http.MethodGet,
		Path:        "/api/history/{benchmark_result_id}",
	}, h.getHistoryForResult)

	huma.Register(api, huma.Operation{
		OperationID: "get-history",
		Summary:     "Get a history series by fingerprint",
		Method:      http.MethodGet,
		Path:        "/api/history",
	}, h.getHistory)

	huma.Register(api, huma.Operation{
		OperationID: "compare-benchmark-results",
		Summary:     "Compare two benchmark results",
		Method:      http.MethodGet,
		Path:        "/api/compare/benchmark-results",
	}, h.getCompare)

	huma.Register(api, huma.Operation{
		OperationID: "list-benchmark-results",
		Summary:     "List and search benchmark results",
		Method:      http.MethodGet,
		Path:        "/api/benchmark-results",
	}, h.getResults)

	huma.Register(api, huma.Operation{
		OperationID: "list-recent-runs",
		Summary:     "List recent benchmark runs",
		Method:      http.MethodGet,
		Path:        "/api/runs/recent",
	}, h.getRecentRuns)

	huma.Register(api, huma.Operation{
		OperationID: "list-series",
		Summary:     "List and search benchmark series",
		Method:      http.MethodGet,
		Path:        "/api/series",
	}, h.getSeries)
}

// ResultPathInput is the {id} path parameter for result detail.
type ResultPathInput struct {
	ID string `path:"id" doc:"Benchmark result id."`
}

// HistoryResultPathInput is the {benchmark_result_id} path parameter; the result
// supplies the fingerprint whose history is returned.
type HistoryResultPathInput struct {
	ID string `path:"benchmark_result_id" doc:"Benchmark result id whose history to load."`
}

// HistoryQueryInput is the convenience query path: the fingerprint directly.
type HistoryQueryInput struct {
	Fingerprint string `query:"fingerprint" required:"true" doc:"History fingerprint."`
}

// ResultDetailOutput carries a result detail body.
type ResultDetailOutput struct {
	Body service.ResultDetail
}

// HistoryOutput carries a history series body.
type HistoryOutput struct {
	Body service.HistorySeries
}

func (h *ReadHandler) getResult(ctx context.Context, in *ResultPathInput) (*ResultDetailOutput, error) {
	d, err := h.reader.ResultDetail(ctx, in.ID)
	if err != nil {
		return nil, mapReadError(err)
	}
	return &ResultDetailOutput{Body: *d}, nil
}

func (h *ReadHandler) getHistoryForResult(ctx context.Context, in *HistoryResultPathInput) (*HistoryOutput, error) {
	series, err := h.reader.HistoryForResult(ctx, in.ID)
	if err != nil {
		return nil, mapReadError(err)
	}
	return &HistoryOutput{Body: *series}, nil
}

func (h *ReadHandler) getHistory(ctx context.Context, in *HistoryQueryInput) (*HistoryOutput, error) {
	series, err := h.reader.History(ctx, in.Fingerprint)
	if err != nil {
		return nil, mapReadError(err)
	}
	return &HistoryOutput{Body: *series}, nil
}

// mapReadError maps expected read errors to actionable responses, and leaves
// everything else for huma to render as a 500.
func mapReadError(err error) error {
	if errors.Is(err, service.ErrNotFound) {
		return huma.Error404NotFound("not found")
	}
	if errors.Is(err, service.ErrNotComparable) {
		return huma.Error422UnprocessableEntity(err.Error())
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "57014" && strings.Contains(pgErr.Message, "statement timeout") {
		return huma.Error422UnprocessableEntity(
			"read query timed out; narrow the request, reduce page size, add filters, or retry a more specific lookup",
		)
	}
	return err
}
