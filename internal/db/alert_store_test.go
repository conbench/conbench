package db_test

import (
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

func TestAlertRuleAndEventStorage(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	otherUserID := dbtest.SeedUser(t, ctx, pool)

	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 4, ThresholdZ: 6,
		RunReason: new("nightly"), Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)
	assert.NotEmpty(t, rule.ID)
	assert.Equal(t, userID, rule.UserID)
	assert.Equal(t, "Arrow nightly", rule.Name)
	assert.Equal(t, ciReportRepo, rule.Repository)
	assert.Equal(t, string(service.CIReportBaselineParent), rule.Baseline)
	assert.InDelta(t, 4.0, rule.Threshold, 1e-9)
	assert.InDelta(t, 6.0, rule.ThresholdZ, 1e-9)
	require.NotNil(t, rule.RunReason)
	assert.Equal(t, "nightly", *rule.RunReason)
	assert.True(t, rule.Enabled)
	assert.Equal(t, storage.AlertRuleStateInactive, rule.State)
	assert.True(t, rule.CreatedAt.Equal(created))
	assert.True(t, rule.UpdatedAt.Equal(created))
	assert.Nil(t, rule.LastEvaluatedAt)

	visible, err := st.ListAlertRulesByUser(ctx, userID)
	require.NoError(t, err)
	require.Len(t, visible, 1)
	assert.Equal(t, rule.ID, visible[0].ID)
	otherVisible, err := st.ListAlertRulesByUser(ctx, otherUserID)
	require.NoError(t, err)
	assert.Empty(t, otherVisible)

	updatedAt := created.Add(time.Hour)
	updated, err := st.UpdateAlertRule(ctx, storage.UpdateAlertRuleParams{
		ID: rule.ID, UserID: userID, Name: "Arrow PR", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineForkPoint), Threshold: 5, ThresholdZ: 5,
		RunReason: nil, Enabled: false, UpdatedAt: updatedAt,
	})
	require.NoError(t, err)
	assert.Equal(t, "Arrow PR", updated.Name)
	assert.Equal(t, string(service.CIReportBaselineForkPoint), updated.Baseline)
	assert.Nil(t, updated.RunReason)
	assert.False(t, updated.Enabled)
	assert.True(t, updated.UpdatedAt.Equal(updatedAt))

	_, err = st.UpdateAlertRule(ctx, storage.UpdateAlertRuleParams{
		ID: rule.ID, UserID: otherUserID, Name: "steal", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, UpdatedAt: updatedAt,
	})
	require.ErrorIs(t, err, storage.ErrNotFound)

	enabled, err := st.ListEnabledAlertRules(ctx)
	require.NoError(t, err)
	assert.Empty(t, enabled, "disabled rules must not be scheduled")

	evalAt := updatedAt.Add(time.Hour)
	opened, err := st.UpdateAlertRuleEvaluation(ctx, storage.UpdateAlertRuleEvaluationParams{
		ID: rule.ID, State: storage.AlertRuleStateOpen, EvaluatedAt: evalAt,
	})
	require.NoError(t, err)
	assert.Equal(t, storage.AlertRuleStateOpen, opened.State)
	require.NotNil(t, opened.LastEvaluatedAt)
	assert.True(t, opened.LastEvaluatedAt.Equal(evalAt))

	eventA, err := st.CreateAlertEvent(ctx, storage.InsertAlertEventParams{
		RuleID: rule.ID, Kind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "regressions detected", RunID: new("run-a"), CommitSHA: new("sha-a"),
		ReportURL: "/ci/report?run_ids=run-a", Summary: []byte(`{"regressions":1}`), CreatedAt: evalAt,
	})
	require.NoError(t, err)
	eventB, err := st.CreateAlertEvent(ctx, storage.InsertAlertEventParams{
		RuleID: rule.ID, Kind: storage.AlertEventKindResolved, Status: string(service.CIReportStatusSuccess),
		StatusReason: "all rows stable", RunID: new("run-b"), CommitSHA: new("sha-b"),
		ReportURL: "/ci/report?run_ids=run-b", Summary: []byte(`{"regressions":0}`), CreatedAt: evalAt.Add(time.Minute),
	})
	require.NoError(t, err)

	events, err := st.ListAlertEventsByRule(ctx, storage.ListAlertEventsParams{RuleID: rule.ID, Limit: 10})
	require.NoError(t, err)
	require.Len(t, events, 2)
	assert.Equal(t, eventB.ID, events[0].ID, "newest first")
	assert.Equal(t, eventA.ID, events[1].ID)

	err = st.DeleteAlertRule(ctx, rule.ID, otherUserID)
	require.ErrorIs(t, err, storage.ErrNotFound)
	require.NoError(t, st.DeleteAlertRule(ctx, rule.ID, userID))
	_, err = st.GetAlertRule(ctx, rule.ID)
	require.ErrorIs(t, err, storage.ErrNotFound)
}

func TestSelectLatestAlertRun(t *testing.T) {
	st, _, ctx := newTestStore(t)
	seed := newCIReportSeed(t, st, ctx)
	olderTS := ciReportTime(1)
	newerTS := ciReportTime(2)
	olderCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "older", "", "older", &olderTS, "older")
	newerCommitID := insertCIReportCommit(t, st, ctx, ciReportRepo, "newer", "older", "older", &newerTS, "newer")

	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-old", RunTags: []byte(`{}`), RunReason: new("nightly"),
		CommitID: olderCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-alert",
		ResultTimestamp: ciReportTime(3), Unit: new("ns"), Data: []*float64{new(10.0)},
	})
	insertCIReportResult(t, st, ctx, seed, ciResultSeed{
		RunID: "run-new", RunTags: []byte(`{}`), RunReason: new("pull request"),
		CommitID: newerCommitID, CommitRepoURL: ciReportRepo, HistoryFingerprint: "fp-alert",
		ResultTimestamp: ciReportTime(4), Unit: new("ns"), Data: []*float64{new(12.0)},
	})

	got, err := st.SelectLatestAlertRun(ctx, storage.SelectLatestAlertRunParams{Repository: ciReportRepo})
	require.NoError(t, err)
	assert.Equal(t, "run-new", got.RunID)
	assert.Equal(t, "newer", got.CommitSHA)
	assert.True(t, got.LastResultTimestamp.Equal(ciReportTime(4)))

	nightly, err := st.SelectLatestAlertRun(ctx, storage.SelectLatestAlertRunParams{
		Repository: ciReportRepo, RunReason: new("nightly"),
	})
	require.NoError(t, err)
	assert.Equal(t, "run-old", nightly.RunID)

	_, err = st.SelectLatestAlertRun(ctx, storage.SelectLatestAlertRunParams{Repository: "https://github.com/no/such"})
	require.ErrorIs(t, err, storage.ErrNotFound)
}

func TestTransitionAlertRuleIsConditionalAndSingleEvent(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)

	transitioned, err := st.TransitionAlertRule(ctx, storage.TransitionAlertRuleParams{
		ID: rule.ID, FromState: storage.AlertRuleStateInactive, ToState: storage.AlertRuleStateOpen,
		Repository: rule.Repository, Baseline: rule.Baseline, Threshold: rule.Threshold,
		ThresholdZ: rule.ThresholdZ, RunReason: rule.RunReason,
		EventKind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "regressions detected", RunID: new("run-1"), CommitSHA: new("sha-1"),
		ReportURL: "/ci/report?run_ids=run-1", Summary: []byte(`{"regressions":1}`),
		EvaluatedAt: created.Add(time.Hour),
	})
	require.NoError(t, err)
	assert.True(t, transitioned.Transitioned)
	assert.Equal(t, storage.AlertRuleStateOpen, transitioned.Rule.State)
	require.NotNil(t, transitioned.Event)
	assert.Equal(t, storage.AlertEventKindOpened, transitioned.Event.Kind)

	duplicate, err := st.TransitionAlertRule(ctx, storage.TransitionAlertRuleParams{
		ID: rule.ID, FromState: storage.AlertRuleStateInactive, ToState: storage.AlertRuleStateOpen,
		Repository: rule.Repository, Baseline: rule.Baseline, Threshold: rule.Threshold,
		ThresholdZ: rule.ThresholdZ, RunReason: rule.RunReason,
		EventKind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "still regressed", RunID: new("run-1"), CommitSHA: new("sha-1"),
		ReportURL: "/ci/report?run_ids=run-1", Summary: []byte(`{"regressions":1}`),
		EvaluatedAt: created.Add(2 * time.Hour),
	})
	require.NoError(t, err)
	assert.False(t, duplicate.Transitioned)
	assert.Nil(t, duplicate.Event)
	assert.Equal(t, storage.AlertRuleStateOpen, duplicate.Rule.State)

	events, err := st.ListAlertEventsByRule(ctx, storage.ListAlertEventsParams{RuleID: rule.ID, Limit: 10})
	require.NoError(t, err)
	require.Len(t, events, 1)
	assert.Equal(t, transitioned.Event.ID, events[0].ID)
}

func TestAlertRuleEvaluationTouchIsConditionalOnSnapshot(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)

	_, err = st.UpdateAlertRule(ctx, storage.UpdateAlertRuleParams{
		ID: rule.ID, UserID: userID, Name: rule.Name, Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 10, ThresholdZ: 5,
		Enabled: true, UpdatedAt: created.Add(time.Minute), ResetEvaluation: true,
	})
	require.NoError(t, err)

	touched, err := st.TouchAlertRuleEvaluation(ctx, storage.TouchAlertRuleEvaluationParams{
		ID: rule.ID, State: rule.State, Repository: rule.Repository, Baseline: rule.Baseline,
		Threshold: rule.Threshold, ThresholdZ: rule.ThresholdZ, RunReason: rule.RunReason,
		EvaluatedAt: created.Add(time.Hour),
	})
	require.NoError(t, err)
	assert.False(t, touched.Touched)
	assert.InDelta(t, 10.0, touched.Rule.Threshold, 1e-9)
	assert.Nil(t, touched.Rule.LastEvaluatedAt)
}

func TestTransitionAlertRuleIsConditionalOnSnapshot(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)

	_, err = st.UpdateAlertRule(ctx, storage.UpdateAlertRuleParams{
		ID: rule.ID, UserID: userID, Name: rule.Name, Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 10, ThresholdZ: 5,
		Enabled: true, UpdatedAt: created.Add(time.Minute), ResetEvaluation: true,
	})
	require.NoError(t, err)

	transitioned, err := st.TransitionAlertRule(ctx, storage.TransitionAlertRuleParams{
		ID: rule.ID, FromState: storage.AlertRuleStateInactive, ToState: storage.AlertRuleStateOpen,
		Repository: rule.Repository, Baseline: rule.Baseline, Threshold: rule.Threshold,
		ThresholdZ: rule.ThresholdZ, RunReason: rule.RunReason,
		EventKind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "regressions detected", RunID: new("run-1"), CommitSHA: new("sha-1"),
		ReportURL: "/ci/report?run_ids=run-1", Summary: []byte(`{"regressions":1}`),
		EvaluatedAt: created.Add(time.Hour),
	})
	require.NoError(t, err)
	assert.False(t, transitioned.Transitioned)
	assert.Equal(t, storage.AlertRuleStateInactive, transitioned.Rule.State)
	assert.InDelta(t, 10.0, transitioned.Rule.Threshold, 1e-9)
	assert.Nil(t, transitioned.Event)
}

func TestTransitionAlertRuleRollsBackWhenEventInsertFails(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)

	_, err = st.TransitionAlertRule(ctx, storage.TransitionAlertRuleParams{
		ID: rule.ID, FromState: storage.AlertRuleStateInactive, ToState: storage.AlertRuleStateOpen,
		Repository: rule.Repository, Baseline: rule.Baseline, Threshold: rule.Threshold,
		ThresholdZ: rule.ThresholdZ, RunReason: rule.RunReason,
		EventKind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "regressions detected", RunID: new("run-1"), CommitSHA: new("sha-1"),
		ReportURL: "/ci/report?run_ids=run-1", Summary: []byte(`{`),
		EvaluatedAt: created.Add(time.Hour),
	})
	require.Error(t, err)

	after, err := st.GetAlertRule(ctx, rule.ID)
	require.NoError(t, err)
	assert.Equal(t, storage.AlertRuleStateInactive, after.State)
	assert.Nil(t, after.LastEvaluatedAt)
	events, err := st.ListAlertEventsByRule(ctx, storage.ListAlertEventsParams{RuleID: rule.ID, Limit: 10})
	require.NoError(t, err)
	assert.Empty(t, events)
}

func TestAlertDeliveryOutboxStorage(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)
	event, err := st.CreateAlertEvent(ctx, storage.InsertAlertEventParams{
		RuleID: rule.ID, Kind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "regressions detected", RunID: new("run-1"), CommitSHA: new("sha-1"),
		ReportURL: "/ci/report?run_ids=run-1", Summary: []byte(`{"regressions":1}`), CreatedAt: created,
	})
	require.NoError(t, err)

	enqueued, err := st.EnqueueAlertDeliveries(ctx, storage.EnqueueAlertDeliveriesParams{
		Channel: "webhook", Target: "https://hooks.example/conbench", Limit: 10, CreatedAt: created,
	})
	require.NoError(t, err)
	assert.Equal(t, 1, enqueued)
	enqueued, err = st.EnqueueAlertDeliveries(ctx, storage.EnqueueAlertDeliveriesParams{
		Channel: "webhook", Target: "https://hooks.example/conbench", Limit: 10, CreatedAt: created,
	})
	require.NoError(t, err)
	assert.Equal(t, 0, enqueued, "enqueue is idempotent for event/channel/target")

	pending, err := st.ClaimPendingAlertDeliveries(ctx, storage.ClaimPendingAlertDeliveriesParams{
		Channel: "webhook", Target: "https://hooks.example/conbench",
		Now: created, LeaseUntil: created.Add(10 * time.Minute), Limit: 10,
	})
	require.NoError(t, err)
	require.Len(t, pending, 1)
	assert.Equal(t, event.ID, pending[0].EventID)
	assert.Equal(t, event.ID, pending[0].Event.ID)
	assert.Equal(t, storage.AlertDeliveryStatusPending, pending[0].Status)
	assert.Equal(t, int32(1), pending[0].AttemptCount, "claim leases the row and counts the attempt")
	require.NotNil(t, pending[0].NextAttemptAt)
	assert.True(t, pending[0].NextAttemptAt.Equal(created.Add(10*time.Minute)), "claim leases via next_attempt_at")

	failedAt := created.Add(time.Minute)
	nextAttempt := failedAt.Add(5 * time.Minute)
	failed, err := st.MarkAlertDeliveryFailed(ctx, storage.MarkAlertDeliveryFailedParams{
		ID: pending[0].ID, Error: "webhook unavailable", AttemptedAt: failedAt, NextAttemptAt: nextAttempt,
	})
	require.NoError(t, err)
	assert.Equal(t, storage.AlertDeliveryStatusFailed, failed.Status)
	assert.Equal(t, int32(1), failed.AttemptCount)
	require.NotNil(t, failed.NextAttemptAt)
	assert.True(t, failed.NextAttemptAt.Equal(nextAttempt))

	pending, err = st.ClaimPendingAlertDeliveries(ctx, storage.ClaimPendingAlertDeliveriesParams{
		Channel: "webhook", Target: "https://hooks.example/conbench",
		Now: failedAt, LeaseUntil: failedAt.Add(10 * time.Minute), Limit: 10,
	})
	require.NoError(t, err)
	assert.Empty(t, pending, "failed delivery is hidden until next_attempt_at")

	pending, err = st.ClaimPendingAlertDeliveries(ctx, storage.ClaimPendingAlertDeliveriesParams{
		Channel: "webhook", Target: "https://hooks.example/conbench",
		Now: nextAttempt, LeaseUntil: nextAttempt.Add(10 * time.Minute), Limit: 10,
	})
	require.NoError(t, err)
	require.Len(t, pending, 1)
	assert.Equal(t, int32(2), pending[0].AttemptCount, "second claim counts another attempt")

	deliveredAt := nextAttempt.Add(time.Minute)
	delivered, err := st.MarkAlertDeliveryDelivered(ctx, storage.MarkAlertDeliveryDeliveredParams{
		ID: pending[0].ID, AttemptedAt: deliveredAt,
	})
	require.NoError(t, err)
	assert.Equal(t, storage.AlertDeliveryStatusDelivered, delivered.Status)
	assert.Equal(t, int32(2), delivered.AttemptCount)
	require.NotNil(t, delivered.DeliveredAt)
	assert.True(t, delivered.DeliveredAt.Equal(deliveredAt))

	pending, err = st.ClaimPendingAlertDeliveries(ctx, storage.ClaimPendingAlertDeliveriesParams{
		Channel: "webhook", Target: "https://hooks.example/conbench",
		Now: deliveredAt, LeaseUntil: deliveredAt.Add(10 * time.Minute), Limit: 10,
	})
	require.NoError(t, err)
	assert.Empty(t, pending)
}

func TestGitHubAlertDeliveryOutboxFiltersByEventRepository(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	otherRepo := "https://github.com/other/project"
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)
	otherRule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Other nightly", Repository: otherRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)
	event, err := st.CreateAlertEvent(ctx, storage.InsertAlertEventParams{
		RuleID: rule.ID, Kind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "regressions detected", RunID: new("run-1"), CommitSHA: new("sha-1"),
		ReportURL: "/ci/report?run_ids=run-1", Summary: []byte(`{"regressions":1}`), CreatedAt: created,
	})
	require.NoError(t, err)
	otherEvent, err := st.CreateAlertEvent(ctx, storage.InsertAlertEventParams{
		RuleID: otherRule.ID, Kind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
		StatusReason: "regressions detected", RunID: new("run-2"), CommitSHA: new("sha-2"),
		ReportURL: "/ci/report?run_ids=run-2", Summary: []byte(`{"regressions":1}`), CreatedAt: created.Add(time.Minute),
	})
	require.NoError(t, err)
	retargetedRepo := "https://github.com/org/retargeted"
	_, err = st.UpdateAlertRule(ctx, storage.UpdateAlertRuleParams{
		ID: rule.ID, UserID: userID, Name: rule.Name, Repository: retargetedRepo,
		Baseline: rule.Baseline, Threshold: rule.Threshold, ThresholdZ: rule.ThresholdZ,
		RunReason: rule.RunReason, Enabled: true, UpdatedAt: created.Add(time.Hour),
	})
	require.NoError(t, err)

	for _, channel := range []string{
		service.AlertDeliveryChannelGitHubCheck,
		service.AlertDeliveryChannelGitHubComment,
	} {
		t.Run(channel, func(t *testing.T) {
			enqueued, err := st.EnqueueAlertDeliveries(ctx, storage.EnqueueAlertDeliveriesParams{
				Channel: channel, Target: ciReportRepo, Limit: 10, CreatedAt: created,
			})
			require.NoError(t, err)
			assert.Equal(t, 1, enqueued)
			pending, err := st.ClaimPendingAlertDeliveries(ctx, storage.ClaimPendingAlertDeliveriesParams{
				Channel: channel, Target: ciReportRepo,
				Now: created, LeaseUntil: created.Add(10 * time.Minute), Limit: 10,
			})
			require.NoError(t, err)
			require.Len(t, pending, 1)
			assert.Equal(t, event.ID, pending[0].EventID)
			assert.NotEqual(t, otherEvent.ID, pending[0].EventID)
			assert.Equal(t, ciReportRepo, pending[0].Event.Repository)

			enqueued, err = st.EnqueueAlertDeliveries(ctx, storage.EnqueueAlertDeliveriesParams{
				Channel: channel, Target: retargetedRepo, Limit: 10, CreatedAt: created,
			})
			require.NoError(t, err)
			assert.Equal(t, 0, enqueued, "retargeting a rule must not move historical events to the new repository")
		})
	}

	for _, channel := range []string{
		service.AlertDeliveryChannelWebhook,
		service.AlertDeliveryChannelEmail,
	} {
		t.Run(channel, func(t *testing.T) {
			enqueued, err := st.EnqueueAlertDeliveries(ctx, storage.EnqueueAlertDeliveriesParams{
				Channel: channel, Target: "ops@example.com", Limit: 10, CreatedAt: created,
			})
			require.NoError(t, err)
			assert.Equal(t, 2, enqueued, "generic channels should still enqueue every alert event for the target")
		})
	}
}

func TestClaimPendingAlertDeliveriesNeverClaimsRowTwice(t *testing.T) {
	st, pool, ctx := newTestStore(t)
	userID := dbtest.SeedUser(t, ctx, pool)
	created := time.Date(2026, 6, 18, 9, 0, 0, 0, time.UTC)
	rule, err := st.CreateAlertRule(ctx, storage.InsertAlertRuleParams{
		UserID: userID, Name: "Arrow nightly", Repository: ciReportRepo,
		Baseline: string(service.CIReportBaselineParent), Threshold: 5, ThresholdZ: 5,
		Enabled: true, CreatedAt: created,
	})
	require.NoError(t, err)

	const eventCount = 8
	for i := range eventCount {
		_, err := st.CreateAlertEvent(ctx, storage.InsertAlertEventParams{
			RuleID: rule.ID, Kind: storage.AlertEventKindOpened, Status: string(service.CIReportStatusFailure),
			StatusReason: "regressions detected", ReportURL: "/ci/report",
			Summary: []byte(`{"regressions":1}`), CreatedAt: created.Add(time.Duration(i) * time.Second),
		})
		require.NoError(t, err)
	}
	enqueued, err := st.EnqueueAlertDeliveries(ctx, storage.EnqueueAlertDeliveriesParams{
		Channel: "webhook", Target: "https://hooks.example/conbench", Limit: eventCount, CreatedAt: created,
	})
	require.NoError(t, err)
	require.Equal(t, eventCount, enqueued)

	// Two overlapping deliver runs claim the same backlog. FOR UPDATE SKIP LOCKED
	// must partition the rows so neither run sees a delivery the other already
	// claimed.
	claims := make([][]storage.AlertDelivery, 2)
	errs := make([]error, 2)
	var wg sync.WaitGroup
	for run := range 2 {
		wg.Go(func() {
			claims[run], errs[run] = st.ClaimPendingAlertDeliveries(ctx, storage.ClaimPendingAlertDeliveriesParams{
				Channel: "webhook", Target: "https://hooks.example/conbench",
				Now: created.Add(time.Hour), LeaseUntil: created.Add(2 * time.Hour), Limit: eventCount,
			})
		})
	}
	wg.Wait()
	require.NoError(t, errs[0])
	require.NoError(t, errs[1])

	seen := map[string]bool{}
	for _, claim := range claims {
		for _, delivery := range claim {
			require.False(t, seen[delivery.ID], "delivery %s claimed by both runs", delivery.ID)
			seen[delivery.ID] = true
		}
	}
	assert.Len(t, seen, eventCount, "every delivery is claimed exactly once across both runs")
}
