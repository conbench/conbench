package api

import (
	"context"
	"net/http"

	"github.com/danielgtaylor/huma/v2"
)

// HealthOutput is the /api/ping response.
type HealthOutput struct {
	Body struct {
		Status string `json:"status"`
	}
}

// RegisterHealth wires an unauthenticated liveness endpoint used by `make dev`
// and container health checks. It does not touch the database.
func RegisterHealth(api huma.API) {
	huma.Register(api, huma.Operation{
		OperationID: "ping",
		Summary:     "Liveness check",
		Method:      http.MethodGet,
		Path:        "/api/ping",
	}, func(_ context.Context, _ *struct{}) (*HealthOutput, error) {
		out := &HealthOutput{}
		out.Body.Status = "ok"
		return out, nil
	})
}
