// Package api exposes the HTTP surface as thin huma handlers over the service
// layer. Handlers authenticate, decode, delegate to the service, and map service
// errors to status codes; all ingestion behavior lives in internal/service.
package api

import (
	"context"
	"errors"
	"net/http"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/service"
)

// Handler serves the result write endpoints. It holds the ingestion service, the
// reader (PUT responds with the updated result detail), and the authenticator; it
// owns no business logic of its own.
type Handler struct {
	ingester *service.Ingester
	reader   *service.Reader
	auth     *auth.Authenticator
}

// NewHandler builds a Handler over the ingestion service, the reader (PUT
// responds with the updated result detail), and the authenticator.
func NewHandler(ingester *service.Ingester, reader *service.Reader, authn *auth.Authenticator) *Handler {
	return &Handler{ingester: ingester, reader: reader, auth: authn}
}

// Register wires the handler's operations onto a huma API, so the same
// registration is used by the server and by humatest.
func (h *Handler) Register(api huma.API) {
	huma.Register(api, huma.Operation{
		OperationID:   "submit-result",
		Summary:       "Submit a benchmark result",
		Method:        http.MethodPost,
		Path:          "/api/results",
		DefaultStatus: http.StatusCreated,
	}, h.submit)

	huma.Register(api, huma.Operation{
		OperationID: "update-result",
		Summary:     "Update a benchmark result's change_annotations",
		Method:      http.MethodPut,
		Path:        "/api/benchmark-results/{id}",
	}, h.update)

	huma.Register(api, huma.Operation{
		OperationID:   "delete-result",
		Summary:       "Delete a benchmark result",
		Method:        http.MethodDelete,
		Path:          "/api/benchmark-results/{id}",
		DefaultStatus: http.StatusNoContent,
	}, h.delete)
}

// SubmitInput is the POST /api/results request: the bearer token header and the
// result body. Authorization is optional in the schema so a missing token is
// rejected by the authenticator (401) rather than by schema validation (422).
type SubmitInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token, e.g. 'Bearer <token>'."`
	// Session cookie; an alternative to the bearer token for browser writes.
	Session string `cookie:"conbench_session"`
	Body    service.SubmitRequest
}

// SubmitOutput is the 201 response carrying the created result's id and the
// fingerprint of the history series it joined.
type SubmitOutput struct {
	Body struct {
		ID                 string `json:"id"`
		HistoryFingerprint string `json:"history_fingerprint"`
	}
}

func (h *Handler) submit(ctx context.Context, in *SubmitInput) (*SubmitOutput, error) {
	if err := h.auth.Authenticate(ctx, in.Authorization, in.Session); err != nil {
		return nil, huma.Error401Unauthorized("authentication required")
	}

	res, err := h.ingester.Submit(ctx, in.Body)
	if err != nil {
		var ve *service.ValidationError
		if errors.As(err, &ve) {
			return nil, huma.Error422UnprocessableEntity(ve.Message)
		}
		return nil, err // unexpected: huma maps to 500
	}

	out := &SubmitOutput{}
	out.Body.ID = res.ID
	out.Body.HistoryFingerprint = res.HistoryFingerprint
	return out, nil
}

// UpdateResultInput is the PUT /api/benchmark-results/{id} request. Only
// change_annotations is updatable: new keys merge over stored ones and a null
// value deletes the key (legacy parity). An explicit null for the whole field
// is a no-op merge, so the schema advertises it as nullable.
type UpdateResultInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token, e.g. 'Bearer <token>'."`
	// Session cookie; an alternative to the bearer token for browser writes.
	Session string `cookie:"conbench_session"`
	ID      string `path:"id"`
	Body    struct {
		ChangeAnnotations map[string]any `json:"change_annotations,omitempty" nullable:"true"`
	}
}

// UpdateResultOutput is the 200 response: the updated result detail.
type UpdateResultOutput struct {
	Body service.ResultDetail
}

func (h *Handler) update(ctx context.Context, in *UpdateResultInput) (*UpdateResultOutput, error) {
	if err := h.auth.Authenticate(ctx, in.Authorization, in.Session); err != nil {
		return nil, huma.Error401Unauthorized("authentication required")
	}
	if err := h.ingester.UpdateChangeAnnotations(ctx, in.ID, in.Body.ChangeAnnotations); err != nil {
		if errors.Is(err, service.ErrNotFound) {
			return nil, huma.Error404NotFound("benchmark result not found")
		}
		return nil, err
	}
	// Update-then-read is not transactional: the echoed detail reflects the row
	// as of this read, not a snapshot of this PUT (same shape as legacy). A row
	// deleted in that window is still a 404, not a 500.
	detail, err := h.reader.ResultDetail(ctx, in.ID)
	if err != nil {
		if errors.Is(err, service.ErrNotFound) {
			return nil, huma.Error404NotFound("benchmark result not found")
		}
		return nil, err
	}
	return &UpdateResultOutput{Body: *detail}, nil
}

// DeleteResultInput is the DELETE /api/benchmark-results/{id} request.
type DeleteResultInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token, e.g. 'Bearer <token>'."`
	// Session cookie; an alternative to the bearer token for browser writes.
	Session string `cookie:"conbench_session"`
	ID      string `path:"id"`
}

func (h *Handler) delete(ctx context.Context, in *DeleteResultInput) (*struct{}, error) {
	if err := h.auth.Authenticate(ctx, in.Authorization, in.Session); err != nil {
		return nil, huma.Error401Unauthorized("authentication required")
	}
	if err := h.ingester.DeleteResult(ctx, in.ID); err != nil {
		if errors.Is(err, service.ErrNotFound) {
			return nil, huma.Error404NotFound("benchmark result not found")
		}
		return nil, err
	}
	return nil, nil
}
