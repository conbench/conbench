package service_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

func TestAlertEvaluatorOpensOnceAndResolvesOnSuccess(t *testing.T) {
	ctx := context.Background()
	store := newFakeAlertStore(storage.AlertRule{
		ID: "rule-1", UserID: "user-1", Name: "repo health", Repository: "https://github.com/org/repo",
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, State: storage.AlertRuleStateInactive,
	})
	reporter := &fakeAlertReporter{}
	evaluator := service.NewAlertEvaluator(store, reporter, fixedAlertNow)

	reporter.next = &service.CIReport{
		Status: service.CIReportStatusFailure, StatusReason: "regressions detected",
		ReportURL: "/ci/report?run_ids=run-1",
		Summary:   service.CIReportSummary{Regressions: 2, Compared: 4},
	}
	summary, err := evaluator.Evaluate(ctx, service.AlertEvaluationOptions{})
	require.NoError(t, err)
	assert.Equal(t, 1, summary.Rules)
	assert.Equal(t, 1, summary.Evaluated)
	assert.Equal(t, 1, summary.Opened)
	require.Len(t, reporter.calls, 1)
	assert.Equal(t, "https://github.com/org/repo", reporter.calls[0].Repository)
	assert.Equal(t, "sha-1", reporter.calls[0].CommitSHA)
	assert.Equal(t, []string{"run-1"}, reporter.calls[0].RunIDs)
	require.Len(t, store.events, 1)
	assert.Equal(t, storage.AlertEventKindOpened, store.events[0].Kind)
	assert.Equal(t, string(service.CIReportStatusFailure), store.events[0].Status)
	assert.JSONEq(t, `{"runs":0,"missing_runs":0,"contender_results":0,"compared":4,"analyzed":0,"regressions":2,"improvements":0,"benchmark_errors":0,"missing_baseline":0,"not_comparable":0}`, string(store.events[0].Summary))
	assert.Equal(t, storage.AlertRuleStateOpen, store.rules["rule-1"].State)

	reporter.next = &service.CIReport{
		Status: service.CIReportStatusFailure, StatusReason: "still regressed",
		ReportURL: "/ci/report?run_ids=run-1",
		Summary:   service.CIReportSummary{Regressions: 1, Compared: 4},
	}
	summary, err = evaluator.Evaluate(ctx, service.AlertEvaluationOptions{})
	require.NoError(t, err)
	assert.Equal(t, 1, summary.Unchanged)
	assert.Len(t, store.events, 1, "open alerts do not emit repeat failure events")

	reporter.next = &service.CIReport{
		Status: service.CIReportStatusSkipped, StatusReason: "not enough history",
		ReportURL: "/ci/report?run_ids=run-1",
	}
	summary, err = evaluator.Evaluate(ctx, service.AlertEvaluationOptions{})
	require.NoError(t, err)
	assert.Equal(t, 1, summary.Skipped)
	assert.Equal(t, storage.AlertRuleStateOpen, store.rules["rule-1"].State, "skipped reports do not resolve an open alert")
	assert.Len(t, store.events, 1)

	reporter.next = &service.CIReport{
		Status: service.CIReportStatusSuccess, StatusReason: "all compared rows stable",
		ReportURL: "/ci/report?run_ids=run-1",
		Summary:   service.CIReportSummary{Compared: 4},
	}
	summary, err = evaluator.Evaluate(ctx, service.AlertEvaluationOptions{})
	require.NoError(t, err)
	assert.Equal(t, 1, summary.Resolved)
	require.Len(t, store.events, 2)
	assert.Equal(t, storage.AlertEventKindResolved, store.events[1].Kind)
	assert.Equal(t, storage.AlertRuleStateInactive, store.rules["rule-1"].State)
}

func TestAlertEvaluatorReportsRuleFailuresAndContinues(t *testing.T) {
	ctx := context.Background()
	store := newFakeAlertStore(
		storage.AlertRule{ID: "no-run", Repository: "https://github.com/no/run", Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5, Enabled: true, State: storage.AlertRuleStateInactive},
		storage.AlertRule{ID: "bad-report", Repository: "https://github.com/org/repo", Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5, Enabled: true, State: storage.AlertRuleStateInactive},
	)
	store.missingRunFor["no-run"] = true
	reporter := &fakeAlertReporter{err: errors.New("report boom")}
	evaluator := service.NewAlertEvaluator(store, reporter, fixedAlertNow)

	summary, err := evaluator.Evaluate(ctx, service.AlertEvaluationOptions{})
	require.Error(t, err)
	assert.Equal(t, 2, summary.Rules)
	assert.Equal(t, 1, summary.NoCandidate)
	assert.Equal(t, 1, summary.Failed)
	assert.Len(t, summary.Failures, 1)
	assert.Equal(t, "bad-report", summary.Failures[0].RuleID)
}

func TestAlertEvaluatorConstrainsDuplicateRunIDByCommit(t *testing.T) {
	_, store, pool, ctx := newIngester(t)
	t0 := time.Date(2024, 2, 1, 0, 0, 0, 0, time.UTC)
	provider := ciCommitProvider{
		"base":  ciCommitInfo("base", nil, "base", t0),
		"head":  ciCommitInfo("head", new("base"), "base", t0.Add(24*time.Hour)),
		"later": ciCommitInfo("later", new("head"), "later", t0.Add(48*time.Hour)),
	}
	ing := service.NewIngester(store, provider)
	ciSubmit(t, ing, ctx, "baseline-run", "base", 10)
	ciSubmit(t, ing, ctx, "ci-run", "head", 20)
	ciSubmit(t, ing, ctx, "ci-run", "later", 30)

	userID := dbtest.SeedUser(t, ctx, pool)
	_, err := store.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "duplicate run ids", Repository: testRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: fixedAlertNow(),
	})
	require.NoError(t, err)

	evaluator := service.NewAlertEvaluator(store, service.NewCIReporter(store, ""), fixedAlertNow)
	summary, err := evaluator.Evaluate(ctx, service.AlertEvaluationOptions{})
	require.NoError(t, err)
	assert.Equal(t, 1, summary.Rules)
	assert.Equal(t, 1, summary.Evaluated)
	assert.Equal(t, 0, summary.Failed)
}

func fixedAlertNow() time.Time {
	return time.Date(2026, 6, 18, 12, 0, 0, 0, time.UTC)
}

type fakeAlertStore struct {
	rules         map[string]storage.AlertRule
	order         []string
	events        []storage.InsertAlertEventParams
	missingRunFor map[string]bool
	beforeUpdate  func(*fakeAlertStore, storage.AlertRule)
}

func newFakeAlertStore(rules ...storage.AlertRule) *fakeAlertStore {
	out := &fakeAlertStore{rules: map[string]storage.AlertRule{}, missingRunFor: map[string]bool{}}
	for _, rule := range rules {
		out.rules[rule.ID] = rule
		out.order = append(out.order, rule.ID)
	}
	return out
}

func (s *fakeAlertStore) ListEnabledAlertRules(context.Context) ([]storage.AlertRule, error) {
	out := make([]storage.AlertRule, 0, len(s.order))
	for _, id := range s.order {
		rule := s.rules[id]
		if rule.Enabled {
			out = append(out, rule)
		}
	}
	return out, nil
}

func (s *fakeAlertStore) SelectLatestAlertRun(_ context.Context, p storage.SelectLatestAlertRunParams) (storage.AlertCandidateRun, error) {
	for _, rule := range s.rules {
		if rule.Repository == p.Repository && s.missingRunFor[rule.ID] {
			return storage.AlertCandidateRun{}, storage.ErrNotFound
		}
	}
	return storage.AlertCandidateRun{RunID: "run-1", CommitSHA: "sha-1", LastResultTimestamp: fixedAlertNow()}, nil
}

func (s *fakeAlertStore) TouchAlertRuleEvaluation(_ context.Context, p storage.TouchAlertRuleEvaluationParams) (storage.AlertRuleTouch, error) {
	rule := s.rules[p.ID]
	if s.beforeUpdate != nil {
		s.beforeUpdate(s, rule)
		rule = s.rules[p.ID]
	}
	if rule.State != p.State || !alertSnapshotMatches(rule, p.Repository, p.Baseline, p.Threshold, p.ThresholdZ, p.RunReason) || !rule.Enabled {
		return storage.AlertRuleTouch{Rule: s.rules[p.ID]}, nil
	}
	rule.LastEvaluatedAt = &p.EvaluatedAt
	rule.UpdatedAt = p.EvaluatedAt
	s.rules[p.ID] = rule
	return storage.AlertRuleTouch{Rule: rule, Touched: true}, nil
}

func (s *fakeAlertStore) CreateAlertEvent(_ context.Context, p storage.InsertAlertEventParams) (storage.AlertEvent, error) {
	s.events = append(s.events, p)
	return storage.AlertEvent{ID: "event", RuleID: p.RuleID, Kind: p.Kind, Status: p.Status, StatusReason: p.StatusReason, Summary: p.Summary, CreatedAt: p.CreatedAt}, nil
}

func (s *fakeAlertStore) TransitionAlertRule(_ context.Context, p storage.TransitionAlertRuleParams) (storage.AlertRuleTransition, error) {
	rule := s.rules[p.ID]
	if s.beforeUpdate != nil {
		s.beforeUpdate(s, rule)
		rule = s.rules[p.ID]
	}
	if rule.State != p.FromState || !alertSnapshotMatches(rule, p.Repository, p.Baseline, p.Threshold, p.ThresholdZ, p.RunReason) || !rule.Enabled {
		return storage.AlertRuleTransition{Rule: rule}, nil
	}
	rule.State = p.ToState
	rule.LastEvaluatedAt = &p.EvaluatedAt
	rule.UpdatedAt = p.EvaluatedAt
	s.rules[p.ID] = rule
	event := storage.AlertEvent{
		ID:           "event",
		RuleID:       p.ID,
		Kind:         p.EventKind,
		Status:       p.Status,
		StatusReason: p.StatusReason,
		RunID:        p.RunID,
		CommitSHA:    p.CommitSHA,
		ReportURL:    p.ReportURL,
		Summary:      p.Summary,
		CreatedAt:    p.EvaluatedAt,
	}
	s.events = append(s.events, storage.InsertAlertEventParams{
		RuleID:       p.ID,
		Kind:         p.EventKind,
		Status:       p.Status,
		StatusReason: p.StatusReason,
		RunID:        p.RunID,
		CommitSHA:    p.CommitSHA,
		ReportURL:    p.ReportURL,
		Summary:      p.Summary,
		CreatedAt:    p.EvaluatedAt,
	})
	return storage.AlertRuleTransition{Rule: rule, Event: &event, Transitioned: true}, nil
}

func alertSnapshotMatches(
	rule storage.AlertRule,
	repository string,
	baseline string,
	threshold float64,
	thresholdZ float64,
	runReason *string,
) bool {
	if rule.Repository != repository || rule.Baseline != baseline || rule.Threshold != threshold || rule.ThresholdZ != thresholdZ {
		return false
	}
	if rule.RunReason == nil || runReason == nil {
		return rule.RunReason == nil && runReason == nil
	}
	return *rule.RunReason == *runReason
}

type fakeAlertReporter struct {
	next  *service.CIReport
	err   error
	calls []service.CIReportQuery
}

func (r *fakeAlertReporter) Report(_ context.Context, q service.CIReportQuery) (*service.CIReport, error) {
	r.calls = append(r.calls, q)
	if r.err != nil {
		return nil, r.err
	}
	return r.next, nil
}
