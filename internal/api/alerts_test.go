package api_test

import (
	"net/http"
	"testing"
	"time"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

func TestAlertRuleAPIUserOwnedCRUDAndEvents(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	sessions := auth.NewSessionSigner("sek")
	_, tapi := humatest.New(t)
	api.NewAlertHandler(store, auth.New("static-op", false, store, sessions)).Register(tapi)

	u1 := dbtest.SeedUser(t, ctx, pool)
	u2 := dbtest.SeedUser(t, ctx, pool)
	s1 := "Cookie: conbench_session=" + sessions.Sign(u1, time.Now().UTC().Add(time.Hour))
	s2 := "Cookie: conbench_session=" + sessions.Sign(u2, time.Now().UTC().Add(time.Hour))

	resp := tapi.Post("/api/alert-rules", s1, map[string]any{
		"name":        "Arrow PR",
		"repository":  "git@github.com:apache/arrow/",
		"baseline":    "parent",
		"threshold":   4,
		"threshold_z": 6,
		"run_reason":  "pull request",
	})
	require.Equal(t, http.StatusCreated, resp.Code, resp.Body.String())
	var created struct {
		ID         string
		UserID     string `json:"user_id"`
		Name       string
		Repository string
		Baseline   string
		Threshold  float64
		ThresholdZ float64 `json:"threshold_z"`
		RunReason  *string `json:"run_reason"`
		Enabled    bool
		State      string
	}
	decode(t, resp.Body.Bytes(), &created)
	require.NotEmpty(t, created.ID)
	assert.Equal(t, u1, created.UserID)
	assert.Equal(t, "https://github.com/apache/arrow", created.Repository)
	assert.Equal(t, "parent", created.Baseline)
	assert.InDelta(t, 4.0, created.Threshold, 1e-9)
	assert.InDelta(t, 6.0, created.ThresholdZ, 1e-9)
	require.NotNil(t, created.RunReason)
	assert.Equal(t, "pull request", *created.RunReason)
	assert.True(t, created.Enabled)
	assert.Equal(t, storage.AlertRuleStateInactive, created.State)

	_, err := store.CreateAlertEvent(ctx, storage.InsertAlertEventParams{
		RuleID: created.ID, Kind: storage.AlertEventKindOpened,
		Status: string(service.CIReportStatusFailure), StatusReason: "regressions detected",
		RunID: new("run-1"), CommitSHA: new("sha-1"), ReportURL: "/ci/report?run_ids=run-1",
		Summary: []byte(`{"regressions":1}`), CreatedAt: time.Now().UTC(),
	})
	require.NoError(t, err)

	resp = tapi.Get("/api/alert-rules", s1)
	require.Equal(t, http.StatusOK, resp.Code)
	assert.Contains(t, resp.Body.String(), created.ID)
	resp = tapi.Get("/api/alert-rules", s2)
	require.Equal(t, http.StatusOK, resp.Code)
	assert.NotContains(t, resp.Body.String(), created.ID)

	resp = tapi.Get("/api/alert-rules/"+created.ID+"/events", s1)
	require.Equal(t, http.StatusOK, resp.Code)
	assert.Contains(t, resp.Body.String(), "regressions detected")
	var events struct {
		Events []struct {
			Summary struct {
				Regressions int `json:"regressions"`
			} `json:"summary"`
		} `json:"events"`
	}
	decode(t, resp.Body.Bytes(), &events)
	require.Len(t, events.Events, 1)
	assert.Equal(t, 1, events.Events[0].Summary.Regressions)
	resp = tapi.Get("/api/alert-rules/"+created.ID+"/events", s2)
	assert.Equal(t, http.StatusNotFound, resp.Code)

	_, err = store.UpdateAlertRuleEvaluation(ctx, storage.UpdateAlertRuleEvaluationParams{
		ID: created.ID, State: storage.AlertRuleStateOpen, EvaluatedAt: time.Now().UTC(),
	})
	require.NoError(t, err)
	resp = tapi.Put("/api/alert-rules/"+created.ID, s1, map[string]any{
		"name":       "Arrow nightly",
		"repository": "https://github.com/apache/arrow",
		"baseline":   "fork_point",
		"enabled":    false,
	})
	require.Equal(t, http.StatusOK, resp.Code, resp.Body.String())
	assert.Contains(t, resp.Body.String(), "Arrow nightly")
	assert.Contains(t, resp.Body.String(), `"enabled":false`)
	assert.Contains(t, resp.Body.String(), `"threshold":5`)
	assert.Contains(t, resp.Body.String(), `"threshold_z":5`)
	var updated struct {
		State           string
		LastEvaluatedAt *time.Time `json:"last_evaluated_at"`
	}
	decode(t, resp.Body.Bytes(), &updated)
	assert.Equal(t, storage.AlertRuleStateInactive, updated.State)
	assert.Nil(t, updated.LastEvaluatedAt)

	resp = tapi.Put("/api/alert-rules/"+created.ID, s2, map[string]any{
		"name": "steal", "repository": "https://github.com/apache/arrow",
	})
	assert.Equal(t, http.StatusNotFound, resp.Code)
	resp = tapi.Delete("/api/alert-rules/"+created.ID, s2)
	assert.Equal(t, http.StatusNotFound, resp.Code)
	resp = tapi.Delete("/api/alert-rules/"+created.ID, s1)
	assert.Equal(t, http.StatusNoContent, resp.Code)
}

func TestAlertRuleAPIRequiresUserPrincipalAndValidInput(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	sessions := auth.NewSessionSigner("sek")
	_, tapi := humatest.New(t)
	api.NewAlertHandler(store, auth.New("static-op", false, store, sessions)).Register(tapi)

	u := dbtest.SeedUser(t, ctx, pool)
	s := "Cookie: conbench_session=" + sessions.Sign(u, time.Now().UTC().Add(time.Hour))

	resp := tapi.Post("/api/alert-rules", map[string]any{"name": "x", "repository": "https://github.com/org/repo"})
	assert.Equal(t, http.StatusUnauthorized, resp.Code)
	resp = tapi.Post("/api/alert-rules", "Authorization: Bearer static-op", map[string]any{"name": "x", "repository": "https://github.com/org/repo"})
	assert.Equal(t, http.StatusForbidden, resp.Code)

	for _, body := range []map[string]any{
		{"name": "", "repository": "https://github.com/org/repo"},
		{"name": "x", "repository": ""},
		{"name": "x", "repository": "https://github.com/org/repo", "baseline": "bogus"},
		{"name": "x", "repository": "https://github.com/org/repo", "threshold": 0},
		{"name": "x", "repository": "https://github.com/org/repo", "threshold_z": -1},
	} {
		resp = tapi.Post("/api/alert-rules", s, body)
		assert.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %#v", body)
	}
}
