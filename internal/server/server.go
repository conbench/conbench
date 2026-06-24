// Package server wires the data layer, services, and API handlers into the HTTP
// handler served by `conbench serve`, plus the dev schema bootstrap. It keeps
// the runtime entrypoint thin and testable.
package server

import (
	"context"
	"fmt"
	"io/fs"
	"net/http"

	"github.com/danielgtaylor/huma/v2"
	"github.com/danielgtaylor/huma/v2/adapters/humago"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/web"
)

// New builds the HTTP handler: a huma API over net/http with the write, read,
// and health endpoints registered, using the given commit provider for
// ingestion (GitHub-backed in production when GITHUB_API_TOKEN is set,
// LocalProvider otherwise).
func New(store *db.Store, authn *auth.Authenticator, provider commit.Provider, authHandler *api.AuthHandler, publicBaseURL ...string) http.Handler {
	return newHandler(store, authn, provider, authHandler, web.DistFS(), publicBaseURL...)
}

// newHandler builds the mux with the huma API plus the SPA catch-all at "/".
// huma's exact patterns (/api/..., /docs, /openapi.*) win by ServeMux
// precedence; everything else falls to the SPA. The asset FS is a parameter so
// tests inject a fixture instead of the embedded build.
//
// A wrong-method request to a known API path (e.g. GET /api/results when only
// POST is registered) is caught by the catch-all and returns a plain 404 rather
// than huma's 405/Allow, because the catch-all matches every method. Restoring
// 405 would mean nested muxes that hard-code huma's doc routes; the single mux
// is the deliberate trade-off. The catch-all never serves HTML for /api paths.
func newHandler(store *db.Store, authn *auth.Authenticator, provider commit.Provider, authHandler *api.AuthHandler, assets fs.FS, publicBaseURL ...string) http.Handler {
	mux := http.NewServeMux()
	register(humago.New(mux, humaConfig()), store, authn, provider, authHandler, firstString(publicBaseURL))
	metrics := newMetricsRecorder(provider)
	mux.HandleFunc("/metrics", metrics.serveMetrics)
	mux.Handle("/", spaHandler(assets))
	return instrumentHTTP(mux, metrics)
}

// specAPI builds the throwaway huma API used for spec emission: the same
// operations as New, registered against a throwaway mux with no database, so the
// document derives purely from the huma Go structs (the source of truth) and the
// registered handlers never touch the store during schema reflection.
func specAPI() huma.API {
	humaAPI := humago.New(http.NewServeMux(), humaConfig())
	authHandler := api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
	register(humaAPI, nil, auth.New("", true, nil, nil), commit.LocalProvider{}, authHandler, "")
	return humaAPI
}

// OpenAPISpec emits the canonical OpenAPI 3.1 document as YAML. It is the
// deterministic generator for the checked-in api/openapi.yaml artifact.
func OpenAPISpec() ([]byte, error) {
	doc := specAPI().OpenAPI()
	pinGeneratedClientExtensions(doc)
	spec, err := doc.YAML()
	if err != nil {
		return nil, fmt.Errorf("emit OpenAPI YAML: %w", err)
	}
	return spec, nil
}

// OpenAPISpec30 emits the OpenAPI 3.0 downgrade as YAML, a compatibility
// artifact (api/openapi-3.0.yaml) for generators that do not support 3.1 —
// notably oapi-codegen, which the Go client is generated with. The canonical
// contract remains the 3.1 document; this is derived from it.
func OpenAPISpec30() ([]byte, error) {
	doc := specAPI().OpenAPI()
	pinGeneratedClientExtensions(doc)
	pinGoClientExtensions(doc)
	spec, err := doc.DowngradeYAML()
	if err != nil {
		return nil, fmt.Errorf("emit OpenAPI 3.0 YAML: %w", err)
	}
	return spec, nil
}

func pinGeneratedClientExtensions(doc *huma.OpenAPI) {
	if doc.Components == nil || doc.Components.Schemas == nil {
		return
	}
	series := doc.Components.Schemas.Map()["SeriesListItem"]
	if series == nil || series.Properties == nil {
		return
	}
	status := series.Properties["status"]
	if status == nil {
		return
	}
	if status.Extensions == nil {
		status.Extensions = map[string]any{}
	}
	status.Extensions["x-enum-varnames"] = []string{"Regressed", "Improved", "Stable", "Insufficient"}
}

func pinGoClientExtensions(doc *huma.OpenAPI) {
	if doc.Components == nil || doc.Components.Schemas == nil {
		return
	}
	ciReportComparison := doc.Components.Schemas.Map()["CIReportComparison"]
	if ciReportComparison == nil || ciReportComparison.Properties == nil {
		return
	}
	ciReportStatus := ciReportComparison.Properties["status"]
	if ciReportStatus == nil {
		return
	}
	if ciReportStatus.Extensions == nil {
		ciReportStatus.Extensions = map[string]any{}
	}
	ciReportStatus.Extensions["x-enum-varnames"] = []string{
		"CIReportComparisonStatusRegressed",
		"CIReportComparisonStatusImproved",
		"CIReportComparisonStatusStable",
		"CIReportComparisonStatusInsufficient",
		"CIReportComparisonStatusErrored",
		"CIReportComparisonStatusMissingBaseline",
		"CIReportComparisonStatusNotComparable",
	}
}

func humaConfig() huma.Config {
	return huma.DefaultConfig("Conbench", "0.1.0")
}

// register wires the write, read, and health operations onto a huma API. New
// and OpenAPISpec share it so the served routes and the emitted spec cannot
// drift.
func register(humaAPI huma.API, store *db.Store, authn *auth.Authenticator, provider commit.Provider, authHandler *api.AuthHandler, publicBaseURL string) {
	reader := service.NewReader(store)
	api.NewHandler(service.NewIngester(store, provider), reader, authn).Register(humaAPI)
	api.NewReadHandler(reader).Register(humaAPI)
	api.NewCIReportHandler(service.NewCIReporter(store, publicBaseURL)).Register(humaAPI)
	api.RegisterHealth(humaAPI)
	authHandler.Register(humaAPI)
	api.NewTokenHandler(store, authn).Register(humaAPI)
	api.NewAlertHandler(store, authn).Register(humaAPI)
}

func firstString(values []string) string {
	if len(values) == 0 {
		return ""
	}
	return values[0]
}

// EnsureSchema applies the embedded schema when the database has no
// benchmark_result table yet, and is a no-op otherwise, so `make dev` can run
// repeatedly against a persistent volume. It is a development convenience;
// production schema changes go through Alembic (scripts/gen_schema.sh), of which
// the embedded schema.sql is the committed, drift-checked output.
func EnsureSchema(ctx context.Context, pool *pgxpool.Pool) error {
	var reg *string
	if err := pool.QueryRow(ctx, "SELECT to_regclass('public.benchmark_result')::text").Scan(&reg); err != nil {
		return fmt.Errorf("check schema: %w", err)
	}
	if reg != nil {
		return nil
	}
	if _, err := pool.Exec(ctx, db.SchemaSQL); err != nil {
		return fmt.Errorf("apply schema: %w", err)
	}
	return nil
}
