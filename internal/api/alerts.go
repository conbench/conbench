package api

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"net/http"
	"strings"
	"time"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/stats"
	"github.com/conbench/conbench/internal/storage"
)

type AlertRuleStore interface {
	CreateAlertRule(ctx context.Context, p storage.InsertAlertRuleParams) (storage.AlertRule, error)
	ListAlertRulesByUser(ctx context.Context, userID string) ([]storage.AlertRule, error)
	GetAlertRule(ctx context.Context, id string) (storage.AlertRule, error)
	UpdateAlertRule(ctx context.Context, p storage.UpdateAlertRuleParams) (storage.AlertRule, error)
	DeleteAlertRule(ctx context.Context, id, userID string) error
	ListAlertEventsByRule(ctx context.Context, p storage.ListAlertEventsParams) ([]storage.AlertEvent, error)
}

type AlertHandler struct {
	store AlertRuleStore
	auth  *auth.Authenticator
}

func NewAlertHandler(store AlertRuleStore, authn *auth.Authenticator) *AlertHandler {
	return &AlertHandler{store: store, auth: authn}
}

func (h *AlertHandler) Register(api huma.API) {
	huma.Register(api, huma.Operation{
		OperationID: "create-alert-rule", Summary: "Create an alert rule",
		Method: http.MethodPost, Path: "/api/alert-rules", DefaultStatus: http.StatusCreated,
	}, h.create)
	huma.Register(api, huma.Operation{
		OperationID: "list-alert-rules", Summary: "List the caller's alert rules",
		Method: http.MethodGet, Path: "/api/alert-rules",
	}, h.list)
	huma.Register(api, huma.Operation{
		OperationID: "get-alert-rule", Summary: "Get one alert rule",
		Method: http.MethodGet, Path: "/api/alert-rules/{id}",
	}, h.get)
	huma.Register(api, huma.Operation{
		OperationID: "update-alert-rule", Summary: "Update one alert rule",
		Method: http.MethodPut, Path: "/api/alert-rules/{id}",
	}, h.update)
	huma.Register(api, huma.Operation{
		OperationID: "delete-alert-rule", Summary: "Delete one alert rule",
		Method: http.MethodDelete, Path: "/api/alert-rules/{id}", DefaultStatus: http.StatusNoContent,
	}, h.delete)
	huma.Register(api, huma.Operation{
		OperationID: "list-alert-events", Summary: "List alert events for one rule",
		Method: http.MethodGet, Path: "/api/alert-rules/{id}/events",
	}, h.events)
}

func (h *AlertHandler) principal(ctx context.Context, authHeader, session string) (auth.Principal, error) {
	p, err := h.auth.ResolvePrincipal(ctx, authHeader, session)
	if err != nil {
		return auth.Principal{}, huma.Error401Unauthorized("authentication required")
	}
	if !p.IsUser() {
		return auth.Principal{}, huma.Error403Forbidden("user-attributed authentication required")
	}
	return p, nil
}

type alertRuleView struct {
	ID              string     `json:"id"`
	UserID          string     `json:"user_id"`
	Name            string     `json:"name"`
	Repository      string     `json:"repository"`
	Baseline        string     `json:"baseline"`
	Threshold       float64    `json:"threshold"`
	ThresholdZ      float64    `json:"threshold_z"`
	RunReason       *string    `json:"run_reason,omitempty"`
	Enabled         bool       `json:"enabled"`
	State           string     `json:"state"`
	CreatedAt       time.Time  `json:"created_at"`
	UpdatedAt       time.Time  `json:"updated_at"`
	LastEvaluatedAt *time.Time `json:"last_evaluated_at,omitempty"`
}

type alertEventView struct {
	ID           string          `json:"id"`
	RuleID       string          `json:"rule_id"`
	Kind         string          `json:"kind"`
	Status       string          `json:"status"`
	StatusReason string          `json:"status_reason"`
	RunID        *string         `json:"run_id,omitempty"`
	CommitSHA    *string         `json:"commit_sha,omitempty"`
	Repository   string          `json:"repository"`
	ReportURL    string          `json:"report_url"`
	Summary      json.RawMessage `json:"summary"`
	CreatedAt    time.Time       `json:"created_at"`
}

type alertRuleBody struct {
	Name       string   `json:"name"`
	Repository string   `json:"repository"`
	Baseline   string   `json:"baseline,omitempty"`
	Threshold  *float64 `json:"threshold,omitempty"`
	ThresholdZ *float64 `json:"threshold_z,omitempty"`
	RunReason  *string  `json:"run_reason,omitempty"`
	Enabled    *bool    `json:"enabled,omitempty"`
}

type createAlertRuleInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
	Body          alertRuleBody
}

type alertRuleOutput struct {
	Body alertRuleView
}

func (h *AlertHandler) create(ctx context.Context, in *createAlertRuleInput) (*alertRuleOutput, error) {
	p, err := h.principal(ctx, in.Authorization, in.Session)
	if err != nil {
		return nil, err
	}
	body, err := validateAlertRuleBody(in.Body)
	if err != nil {
		return nil, err
	}
	now := time.Now().UTC()
	rule, err := h.store.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: p.UserID, Name: body.Name, Repository: body.Repository, Baseline: body.Baseline,
		Threshold: body.Threshold, ThresholdZ: body.ThresholdZ, RunReason: body.RunReason,
		Enabled: body.Enabled, CreatedAt: now,
	})
	if err != nil {
		return nil, err
	}
	return &alertRuleOutput{Body: alertRuleViewOf(rule)}, nil
}

type listAlertRulesInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
}

type listAlertRulesOutput struct {
	Body struct {
		Rules []alertRuleView `json:"rules"`
	}
}

func (h *AlertHandler) list(ctx context.Context, in *listAlertRulesInput) (*listAlertRulesOutput, error) {
	p, err := h.principal(ctx, in.Authorization, in.Session)
	if err != nil {
		return nil, err
	}
	rows, err := h.store.ListAlertRulesByUser(ctx, p.UserID)
	if err != nil {
		return nil, err
	}
	out := &listAlertRulesOutput{}
	out.Body.Rules = make([]alertRuleView, 0, len(rows))
	for _, row := range rows {
		out.Body.Rules = append(out.Body.Rules, alertRuleViewOf(row))
	}
	return out, nil
}

type alertRuleIDInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
	ID            string `path:"id"`
}

func (h *AlertHandler) get(ctx context.Context, in *alertRuleIDInput) (*alertRuleOutput, error) {
	rule, err := h.ownedRule(ctx, in.Authorization, in.Session, in.ID)
	if err != nil {
		return nil, err
	}
	return &alertRuleOutput{Body: alertRuleViewOf(rule)}, nil
}

type updateAlertRuleInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
	ID            string `path:"id"`
	Body          alertRuleBody
}

func (h *AlertHandler) update(ctx context.Context, in *updateAlertRuleInput) (*alertRuleOutput, error) {
	p, err := h.principal(ctx, in.Authorization, in.Session)
	if err != nil {
		return nil, err
	}
	existing, err := h.ownedRuleForPrincipal(ctx, p, in.ID)
	if err != nil {
		return nil, err
	}
	body, err := validateAlertRuleBody(in.Body)
	if err != nil {
		return nil, err
	}
	rule, err := h.store.UpdateAlertRule(ctx, storage.UpdateAlertRuleParams{
		ID: in.ID, UserID: p.UserID, Name: body.Name, Repository: body.Repository,
		Baseline: body.Baseline, Threshold: body.Threshold, ThresholdZ: body.ThresholdZ,
		RunReason: body.RunReason, Enabled: body.Enabled, UpdatedAt: time.Now().UTC(),
		ResetEvaluation: alertRuleEvaluationConfigChanged(existing, body),
	})
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return nil, huma.Error404NotFound("alert rule not found")
		}
		return nil, err
	}
	return &alertRuleOutput{Body: alertRuleViewOf(rule)}, nil
}

func (h *AlertHandler) delete(ctx context.Context, in *alertRuleIDInput) (*struct{}, error) {
	p, err := h.principal(ctx, in.Authorization, in.Session)
	if err != nil {
		return nil, err
	}
	if err := h.store.DeleteAlertRule(ctx, in.ID, p.UserID); err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return nil, huma.Error404NotFound("alert rule not found")
		}
		return nil, err
	}
	return nil, nil
}

type listAlertEventsInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
	ID            string `path:"id"`
	Limit         int32  `query:"limit" default:"50" doc:"Maximum events to return."`
}

type listAlertEventsOutput struct {
	Body struct {
		Events []alertEventView `json:"events"`
	}
}

func (h *AlertHandler) events(ctx context.Context, in *listAlertEventsInput) (*listAlertEventsOutput, error) {
	if in.Limit <= 0 || in.Limit > 500 {
		return nil, huma.Error422UnprocessableEntity("limit must be between 1 and 500")
	}
	if _, err := h.ownedRule(ctx, in.Authorization, in.Session, in.ID); err != nil {
		return nil, err
	}
	rows, err := h.store.ListAlertEventsByRule(ctx, storage.ListAlertEventsParams{RuleID: in.ID, Limit: in.Limit})
	if err != nil {
		return nil, err
	}
	out := &listAlertEventsOutput{}
	out.Body.Events = make([]alertEventView, 0, len(rows))
	for _, row := range rows {
		out.Body.Events = append(out.Body.Events, alertEventViewOf(row))
	}
	return out, nil
}

func (h *AlertHandler) ownedRule(ctx context.Context, authHeader, session, id string) (storage.AlertRule, error) {
	p, err := h.principal(ctx, authHeader, session)
	if err != nil {
		return storage.AlertRule{}, err
	}
	return h.ownedRuleForPrincipal(ctx, p, id)
}

func (h *AlertHandler) ownedRuleForPrincipal(ctx context.Context, p auth.Principal, id string) (storage.AlertRule, error) {
	rule, err := h.store.GetAlertRule(ctx, id)
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return storage.AlertRule{}, huma.Error404NotFound("alert rule not found")
		}
		return storage.AlertRule{}, err
	}
	if rule.UserID != p.UserID {
		return storage.AlertRule{}, huma.Error404NotFound("alert rule not found")
	}
	return rule, nil
}

type normalizedAlertRuleBody struct {
	Name       string
	Repository string
	Baseline   string
	Threshold  float64
	ThresholdZ float64
	RunReason  *string
	Enabled    bool
}

func validateAlertRuleBody(in alertRuleBody) (normalizedAlertRuleBody, error) {
	name := strings.TrimSpace(in.Name)
	if name == "" {
		return normalizedAlertRuleBody{}, huma.Error422UnprocessableEntity("name is required")
	}
	repository := strings.TrimSpace(in.Repository)
	if repository == "" {
		return normalizedAlertRuleBody{}, huma.Error422UnprocessableEntity("repository is required")
	}
	repository = commit.NormalizeRepoURL(repository)
	baseline := in.Baseline
	if baseline == "" {
		baseline = string(service.CIReportBaselineForkPoint)
	}
	if !validAlertBaseline(baseline) {
		return normalizedAlertRuleBody{}, huma.Error422UnprocessableEntity("invalid baseline")
	}
	threshold := stats.PairwisePercentThresholdDefault
	if in.Threshold != nil {
		threshold = *in.Threshold
	}
	if math.IsNaN(threshold) || math.IsInf(threshold, 0) || threshold <= 0 {
		return normalizedAlertRuleBody{}, huma.Error422UnprocessableEntity("threshold must be greater than zero")
	}
	thresholdZ := stats.ZScoreThresholdDefault
	if in.ThresholdZ != nil {
		thresholdZ = *in.ThresholdZ
	}
	if math.IsNaN(thresholdZ) || math.IsInf(thresholdZ, 0) || thresholdZ <= 0 {
		return normalizedAlertRuleBody{}, huma.Error422UnprocessableEntity("threshold_z must be greater than zero")
	}
	enabled := true
	if in.Enabled != nil {
		enabled = *in.Enabled
	}
	var runReason *string
	if in.RunReason != nil {
		trimmed := strings.TrimSpace(*in.RunReason)
		if trimmed != "" {
			runReason = &trimmed
		}
	}
	return normalizedAlertRuleBody{
		Name: name, Repository: repository, Baseline: baseline, Threshold: threshold,
		ThresholdZ: thresholdZ, RunReason: runReason, Enabled: enabled,
	}, nil
}

func validAlertBaseline(v string) bool {
	return v == string(service.CIReportBaselineForkPoint) ||
		v == string(service.CIReportBaselineParent) ||
		v == string(service.CIReportBaselineLatestDefault)
}

func alertRuleEvaluationConfigChanged(rule storage.AlertRule, body normalizedAlertRuleBody) bool {
	return rule.Repository != body.Repository ||
		rule.Baseline != body.Baseline ||
		rule.Threshold != body.Threshold ||
		rule.ThresholdZ != body.ThresholdZ ||
		!sameStringPtr(rule.RunReason, body.RunReason)
}

func sameStringPtr(a, b *string) bool {
	switch {
	case a == nil && b == nil:
		return true
	case a == nil || b == nil:
		return false
	default:
		return *a == *b
	}
}

func alertRuleViewOf(r storage.AlertRule) alertRuleView {
	return alertRuleView{
		ID: r.ID, UserID: r.UserID, Name: r.Name, Repository: r.Repository,
		Baseline: r.Baseline, Threshold: r.Threshold, ThresholdZ: r.ThresholdZ,
		RunReason: r.RunReason, Enabled: r.Enabled, State: r.State,
		CreatedAt: r.CreatedAt, UpdatedAt: r.UpdatedAt, LastEvaluatedAt: r.LastEvaluatedAt,
	}
}

func alertEventViewOf(r storage.AlertEvent) alertEventView {
	return alertEventView{
		ID: r.ID, RuleID: r.RuleID, Kind: r.Kind, Status: r.Status, StatusReason: r.StatusReason,
		RunID: r.RunID, CommitSHA: r.CommitSHA, Repository: r.Repository,
		ReportURL: r.ReportURL, Summary: json.RawMessage(r.Summary),
		CreatedAt: r.CreatedAt,
	}
}
