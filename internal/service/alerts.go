package service

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/conbench/conbench/internal/storage"
)

type AlertStore interface {
	ListEnabledAlertRules(ctx context.Context) ([]storage.AlertRule, error)
	SelectLatestAlertRun(ctx context.Context, p storage.SelectLatestAlertRunParams) (storage.AlertCandidateRun, error)
	TouchAlertRuleEvaluation(ctx context.Context, p storage.TouchAlertRuleEvaluationParams) (storage.AlertRuleTouch, error)
	TransitionAlertRule(ctx context.Context, p storage.TransitionAlertRuleParams) (storage.AlertRuleTransition, error)
}

type AlertReporter interface {
	Report(ctx context.Context, q CIReportQuery) (*CIReport, error)
}

type AlertEvaluationOptions struct{}

type AlertEvaluationSummary struct {
	Rules       int                  `json:"rules"`
	Evaluated   int                  `json:"evaluated"`
	Opened      int                  `json:"opened"`
	Resolved    int                  `json:"resolved"`
	Unchanged   int                  `json:"unchanged"`
	Skipped     int                  `json:"skipped"`
	NoCandidate int                  `json:"no_candidate"`
	Failed      int                  `json:"failed"`
	Failures    []AlertRuleFailure   `json:"failures,omitempty"`
	Events      []storage.AlertEvent `json:"events,omitempty"`
}

type AlertRuleFailure struct {
	RuleID string `json:"rule_id"`
	Error  string `json:"error"`
}

type AlertEvaluator struct {
	store    AlertStore
	reporter AlertReporter
	now      func() time.Time
}

func NewAlertEvaluator(store AlertStore, reporter AlertReporter, now func() time.Time) *AlertEvaluator {
	if now == nil {
		now = func() time.Time { return time.Now().UTC() }
	}
	return &AlertEvaluator{store: store, reporter: reporter, now: now}
}

func (e *AlertEvaluator) Evaluate(ctx context.Context, _ AlertEvaluationOptions) (AlertEvaluationSummary, error) {
	rules, err := e.store.ListEnabledAlertRules(ctx)
	if err != nil {
		return AlertEvaluationSummary{}, err
	}
	summary := AlertEvaluationSummary{Rules: len(rules)}
	for _, rule := range rules {
		if err := e.evaluateRule(ctx, rule, &summary); err != nil {
			summary.Failed++
			summary.Failures = append(summary.Failures, AlertRuleFailure{RuleID: rule.ID, Error: err.Error()})
		}
	}
	if summary.Failed > 0 {
		return summary, errors.New("one or more alert rules failed to evaluate")
	}
	return summary, nil
}

func (e *AlertEvaluator) evaluateRule(ctx context.Context, rule storage.AlertRule, summary *AlertEvaluationSummary) error {
	now := e.now().UTC()
	candidate, err := e.store.SelectLatestAlertRun(ctx, storage.SelectLatestAlertRunParams{
		Repository: rule.Repository,
		RunReason:  rule.RunReason,
	})
	if errors.Is(err, storage.ErrNotFound) {
		summary.NoCandidate++
		_, updateErr := e.touchRule(ctx, rule, now)
		return updateErr
	}
	if err != nil {
		return err
	}

	report, err := e.reporter.Report(ctx, CIReportQuery{
		Repository: rule.Repository,
		CommitSHA:  candidate.CommitSHA,
		RunIDs:     []string{candidate.RunID},
		Baseline:   CIReportBaseline(rule.Baseline),
		Threshold:  rule.Threshold,
		ThresholdZ: rule.ThresholdZ,
	})
	if err != nil {
		return err
	}
	if report == nil {
		return errors.New("nil CI report")
	}
	summary.Evaluated++
	alertReport := automatedAlertReport(report)

	switch alertReport.Status {
	case CIReportStatusFailure:
		return e.openIfNeeded(ctx, rule, candidate, alertReport, now, summary)
	case CIReportStatusSuccess:
		return e.resolveIfNeeded(ctx, rule, candidate, alertReport, now, summary)
	default:
		summary.Skipped++
		_, err = e.touchRule(ctx, rule, now)
		return err
	}
}

// automatedAlertReport removes explicit distribution-boundary contenders from
// alert status derivation. The source report remains unchanged for manual CI
// report consumers.
func automatedAlertReport(report *CIReport) *CIReport {
	comparisons := make([]CIReportComparison, 0, len(report.Comparisons))
	for _, comparison := range report.Comparisons {
		if !comparison.Contender.BeginsDistributionChange {
			comparisons = append(comparisons, comparison)
		}
	}
	if len(comparisons) == len(report.Comparisons) {
		return report
	}

	filtered := *report
	filtered.Comparisons = comparisons
	filtered.Runs = make([]CIReportRun, len(report.Runs))
	for i, run := range report.Runs {
		filtered.Runs[i] = run
		filtered.Runs[i].Comparisons = make([]CIReportComparison, 0, len(run.Comparisons))
		for _, comparison := range run.Comparisons {
			if !comparison.Contender.BeginsDistributionChange {
				filtered.Runs[i].Comparisons = append(filtered.Runs[i].Comparisons, comparison)
			}
		}
	}
	filtered.Summary = CIReportSummary{
		Runs:              report.Summary.Runs,
		MissingRuns:       report.Summary.MissingRuns,
		ContenderResults:  len(comparisons),
		commitlessRuns:    report.Summary.commitlessRuns,
		baselineErrors:    report.Summary.baselineErrors,
		baselineActionErr: report.Summary.baselineActionErr,
	}
	if len(comparisons) == 0 {
		filtered.Status = CIReportStatusSkipped
		filtered.StatusReason = "all contender rows begin a distribution change"
		return &filtered
	}
	filtered.deriveSummaryFromComparisons()
	filtered.Status = filtered.deriveStatus()
	filtered.StatusReason = filtered.deriveStatusReason()
	return &filtered
}

func (e *AlertEvaluator) openIfNeeded(
	ctx context.Context,
	rule storage.AlertRule,
	candidate storage.AlertCandidateRun,
	report *CIReport,
	now time.Time,
	summary *AlertEvaluationSummary,
) error {
	if rule.State == storage.AlertRuleStateOpen {
		summary.Unchanged++
		_, err := e.touchRule(ctx, rule, now)
		return err
	}
	transition, err := e.transitionRule(
		ctx, rule, candidate, report, storage.AlertRuleStateInactive, storage.AlertRuleStateOpen,
		storage.AlertEventKindOpened, now,
	)
	if err != nil {
		return err
	}
	if !transition.Transitioned {
		summary.Unchanged++
		return nil
	}
	summary.Opened++
	if transition.Event != nil {
		summary.Events = append(summary.Events, *transition.Event)
	}
	return nil
}

func (e *AlertEvaluator) resolveIfNeeded(
	ctx context.Context,
	rule storage.AlertRule,
	candidate storage.AlertCandidateRun,
	report *CIReport,
	now time.Time,
	summary *AlertEvaluationSummary,
) error {
	if rule.State != storage.AlertRuleStateOpen {
		summary.Unchanged++
		_, err := e.touchRule(ctx, rule, now)
		return err
	}
	transition, err := e.transitionRule(
		ctx, rule, candidate, report, storage.AlertRuleStateOpen, storage.AlertRuleStateInactive,
		storage.AlertEventKindResolved, now,
	)
	if err != nil {
		return err
	}
	if !transition.Transitioned {
		summary.Unchanged++
		return nil
	}
	summary.Resolved++
	if transition.Event != nil {
		summary.Events = append(summary.Events, *transition.Event)
	}
	return nil
}

func (e *AlertEvaluator) transitionRule(
	ctx context.Context,
	rule storage.AlertRule,
	candidate storage.AlertCandidateRun,
	report *CIReport,
	fromState string,
	toState string,
	kind string,
	now time.Time,
) (storage.AlertRuleTransition, error) {
	summary, err := json.Marshal(report.Summary)
	if err != nil {
		return storage.AlertRuleTransition{}, err
	}
	return e.store.TransitionAlertRule(ctx, storage.TransitionAlertRuleParams{
		ID:           rule.ID,
		FromState:    fromState,
		ToState:      toState,
		Repository:   rule.Repository,
		Baseline:     rule.Baseline,
		Threshold:    rule.Threshold,
		ThresholdZ:   rule.ThresholdZ,
		RunReason:    rule.RunReason,
		EventKind:    kind,
		Status:       string(report.Status),
		StatusReason: report.StatusReason,
		RunID:        &candidate.RunID,
		CommitSHA:    &candidate.CommitSHA,
		ReportURL:    report.ReportURL,
		Summary:      summary,
		EvaluatedAt:  now,
	})
}

func (e *AlertEvaluator) touchRule(
	ctx context.Context,
	rule storage.AlertRule,
	now time.Time,
) (storage.AlertRuleTouch, error) {
	return e.store.TouchAlertRuleEvaluation(ctx, storage.TouchAlertRuleEvaluationParams{
		ID:          rule.ID,
		State:       rule.State,
		Repository:  rule.Repository,
		Baseline:    rule.Baseline,
		Threshold:   rule.Threshold,
		ThresholdZ:  rule.ThresholdZ,
		RunReason:   rule.RunReason,
		EvaluatedAt: now,
	})
}
