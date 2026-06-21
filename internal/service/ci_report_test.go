package service_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/service"
)

type ciCommitProvider map[string]commit.Info

func (p ciCommitProvider) Resolve(_ context.Context, req commit.Request) (*commit.Info, error) {
	if req.Commit == "" {
		return nil, nil
	}
	info, ok := p[req.Commit]
	if !ok {
		sha := req.Commit
		ts := req.ResultTimestamp
		return &commit.Info{
			Sha:          sha,
			Repository:   commit.NormalizeRepoURL(req.Repository),
			ForkPointSha: &sha,
			Timestamp:    &ts,
		}, nil
	}
	if info.Repository == "" {
		info.Repository = commit.NormalizeRepoURL(req.Repository)
	}
	return &info, nil
}

func ciCommitInfo(sha string, parent *string, forkPoint string, ts time.Time) commit.Info {
	fp := forkPoint
	return commit.Info{
		Sha:          sha,
		Repository:   testRepo,
		Parent:       parent,
		Message:      "commit " + sha,
		Timestamp:    &ts,
		ForkPointSha: &fp,
	}
}

func ciSubmit(t *testing.T, ing *service.Ingester, ctx context.Context, runID, sha string, value float64) *service.Result {
	t.Helper()
	req := machineReq(samples(value, value+1, value+2), "s")
	req.RunID = runID
	req.BatchID = runID + "-batch"
	req.GitHub.Commit = sha
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	return res
}

func TestCIReportRunOnlyCommitlessAndMissing(t *testing.T) {
	ing, store, _, ctx := newIngester(t)
	reporter := service.NewCIReporter(store, "")

	req := machineReq(samples(1, 2, 3), "s")
	req.RunID = "commitless-run"
	req.GitHub.Commit = ""
	_, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	report, err := reporter.Report(ctx, service.CIReportQuery{
		RunIDs: []string{"commitless-run", "missing-run"},
	})
	require.NoError(t, err)

	assert.Equal(t, service.CIReportStatusActionRequired, report.Status)
	assert.Equal(t, []string{"commitless-run"}, report.SelectedRunIDs)
	assert.Equal(t, []string{"missing-run"}, report.MissingRunIDs)
	assert.Nil(t, report.CommitSHA)
	require.Len(t, report.Runs, 1)
	assert.Nil(t, report.Runs[0].Commit)
	if assert.NotNil(t, report.Runs[0].BaselineError) {
		assert.Equal(t, service.CIReportBaselineErrorMissingCommitMetadata, report.Runs[0].BaselineError.Code)
	}
	assert.Empty(t, report.Runs[0].Comparisons)

	_, err = reporter.Report(ctx, service.CIReportQuery{RunIDs: []string{"missing-run"}})
	assert.ErrorIs(t, err, service.ErrNotFound)
}

func TestCIReportForkPointUsesLookbackStatusNotPairwiseOnly(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	t0 := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	provider := ciCommitProvider{
		"c1": ciCommitInfo("c1", nil, "c1", t0),
		"c2": ciCommitInfo("c2", new("c1"), "c2", t0.Add(24*time.Hour)),
		"c3": ciCommitInfo("c3", new("c2"), "c3", t0.Add(48*time.Hour)),
		"c4": ciCommitInfo("c4", new("c3"), "c3", t0.Add(72*time.Hour)),
		"c5": ciCommitInfo("c5", new("c4"), "c5", t0.Add(96*time.Hour)),
	}
	ing := service.NewIngester(store, provider)
	ciSubmit(t, ing, ctx, "default-c1", "c1", 10)
	ciSubmit(t, ing, ctx, "default-c2", "c2", 20)
	baseline := ciSubmit(t, ing, ctx, "default-c3", "c3", 30)
	contender := ciSubmit(t, ing, ctx, "ci-run", "c4", 100)
	ciSubmit(t, ing, ctx, "ci-run", "c5", 1000)
	ciSubmit(t, ing, ctx, "default-c3", "c5", 2000)

	reporter := service.NewCIReporter(store, "https://conbench.example")
	report, err := reporter.Report(ctx, service.CIReportQuery{
		Repository: testRepo,
		CommitSHA:  "c4",
		Baseline:   service.CIReportBaselineForkPoint,
	})
	require.NoError(t, err)

	assert.Equal(t, service.CIReportStatusFailure, report.Status)
	assert.Equal(t, []string{"ci-run"}, report.SelectedRunIDs)
	if assert.NotNil(t, report.CommitSHA) {
		assert.Equal(t, "c4", *report.CommitSHA)
	}
	assert.True(t, strings.HasPrefix(report.ReportURL, "https://conbench.example/ci/report?"))
	require.Len(t, report.Runs, 1)
	assert.Equal(t, "c3", report.Runs[0].BaselineCommit.Sha)
	assert.Equal(t, "default-c3", *report.Runs[0].BaselineRunID)
	require.Len(t, report.Runs[0].Comparisons, 1)
	row := report.Runs[0].Comparisons[0]
	assert.Equal(t, contender.ID, row.Contender.ResultID)
	require.NotNil(t, row.Baseline)
	assert.Equal(t, baseline.ID, row.Baseline.ResultID)
	require.NotNil(t, row.Baseline.CommitSHA)
	assert.Equal(t, "c3", *row.Baseline.CommitSHA)
	assert.Equal(t, service.CIReportRowStatusRegressed, row.Status)
	require.NotNil(t, row.Analysis)
	require.NotNil(t, row.Analysis.Pairwise)
	require.NotNil(t, row.Analysis.LookbackZScore)
	assert.True(t, row.Analysis.Pairwise.RegressionIndicated)
	assert.True(t, row.Analysis.LookbackZScore.RegressionIndicated)
	assert.Equal(t, 1, report.Summary.Compared)
	assert.Equal(t, 1, report.Summary.Analyzed)
	assert.Equal(t, 1, report.Summary.Regressions)
}

func TestCIReportCommitSelectorRunIDsIgnoreSameRunIDOnOtherCommit(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	t0 := time.Date(2024, 1, 10, 0, 0, 0, 0, time.UTC)
	provider := ciCommitProvider{
		"base":  ciCommitInfo("base", nil, "base", t0),
		"head":  ciCommitInfo("head", new("base"), "base", t0.Add(24*time.Hour)),
		"later": ciCommitInfo("later", new("head"), "later", t0.Add(48*time.Hour)),
	}
	ing := service.NewIngester(store, provider)
	baseline := ciSubmit(t, ing, ctx, "baseline-run", "base", 10)
	contender := ciSubmit(t, ing, ctx, "ci-run", "head", 20)
	ciSubmit(t, ing, ctx, "ci-run", "later", 1000)

	reporter := service.NewCIReporter(store, "")
	report, err := reporter.Report(ctx, service.CIReportQuery{
		Repository: testRepo,
		CommitSHA:  "head",
		RunIDs:     []string{"ci-run"},
		Baseline:   service.CIReportBaselineParent,
	})
	require.NoError(t, err)

	assert.Equal(t, []string{"ci-run"}, report.SelectedRunIDs)
	assert.Empty(t, report.MissingRunIDs)
	if assert.NotNil(t, report.CommitSHA) {
		assert.Equal(t, "head", *report.CommitSHA)
	}
	require.Len(t, report.Runs, 1)
	require.NotNil(t, report.Runs[0].Commit)
	assert.Equal(t, "head", report.Runs[0].Commit.Sha)
	require.Len(t, report.Runs[0].Comparisons, 1)
	row := report.Runs[0].Comparisons[0]
	assert.Equal(t, contender.ID, row.Contender.ResultID)
	require.NotNil(t, row.Baseline)
	assert.Equal(t, baseline.ID, row.Baseline.ResultID)
}

func TestCIReportBaselineCanReuseContenderRunIDOnAncestorCommit(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	t0 := time.Date(2024, 1, 20, 0, 0, 0, 0, time.UTC)
	provider := ciCommitProvider{
		"base": ciCommitInfo("base", nil, "base", t0),
		"head": ciCommitInfo("head", new("base"), "base", t0.Add(24*time.Hour)),
	}
	ing := service.NewIngester(store, provider)
	baseline := ciSubmit(t, ing, ctx, "ci-run", "base", 10)
	contender := ciSubmit(t, ing, ctx, "ci-run", "head", 20)

	reporter := service.NewCIReporter(store, "")
	report, err := reporter.Report(ctx, service.CIReportQuery{
		Repository: testRepo,
		CommitSHA:  "head",
		RunIDs:     []string{"ci-run"},
		Baseline:   service.CIReportBaselineParent,
	})
	require.NoError(t, err)

	require.Len(t, report.Runs, 1)
	require.NotNil(t, report.Runs[0].BaselineRunID)
	assert.Equal(t, "ci-run", *report.Runs[0].BaselineRunID)
	require.Len(t, report.Runs[0].Comparisons, 1)
	row := report.Runs[0].Comparisons[0]
	assert.Equal(t, contender.ID, row.Contender.ResultID)
	require.NotNil(t, row.Baseline)
	assert.Equal(t, baseline.ID, row.Baseline.ResultID)
	require.NotNil(t, row.Baseline.CommitSHA)
	assert.Equal(t, "base", *row.Baseline.CommitSHA)
}

func TestCIReportExplicitBaselineRunIDsCompareSelectedRuns(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	t0 := time.Date(2024, 1, 25, 0, 0, 0, 0, time.UTC)
	provider := ciCommitProvider{
		"c1": ciCommitInfo("c1", nil, "c1", t0),
		"c2": ciCommitInfo("c2", new("c1"), "c2", t0.Add(24*time.Hour)),
		"c3": ciCommitInfo("c3", new("c2"), "c3", t0.Add(48*time.Hour)),
		"c4": ciCommitInfo("c4", new("c3"), "c4", t0.Add(72*time.Hour)),
	}
	ing := service.NewIngester(store, provider)
	ciSubmit(t, ing, ctx, "history-c1", "c1", 10)
	ciSubmit(t, ing, ctx, "history-c2", "c2", 20)
	baseline := ciSubmit(t, ing, ctx, "explicit-baseline", "c3", 30)
	contender := ciSubmit(t, ing, ctx, "ci-run", "c4", 100)

	reporter := service.NewCIReporter(store, "https://conbench.example")
	report, err := reporter.Report(ctx, service.CIReportQuery{
		RunIDs:         []string{"ci-run"},
		BaselineRunIDs: []string{"explicit-baseline"},
	})
	require.NoError(t, err)

	assert.Equal(t, service.CIReportBaselineExplicitRun, report.Baseline)
	assert.Equal(t, service.CIReportStatusFailure, report.Status)
	assert.Equal(t, []string{"ci-run"}, report.SelectedRunIDs)
	assert.Contains(t, report.ReportURL, "run_ids=ci-run")
	assert.Contains(t, report.ReportURL, "baseline_run_ids=explicit-baseline")
	require.Len(t, report.Runs, 1)
	assert.Equal(t, "explicit-baseline", *report.Runs[0].BaselineRunID)
	require.NotNil(t, report.Runs[0].BaselineCommit)
	assert.Equal(t, "c3", report.Runs[0].BaselineCommit.Sha)
	require.Len(t, report.Runs[0].Comparisons, 1)
	row := report.Runs[0].Comparisons[0]
	assert.Equal(t, contender.ID, row.Contender.ResultID)
	require.NotNil(t, row.Baseline)
	assert.Equal(t, baseline.ID, row.Baseline.ResultID)
	assert.Equal(t, service.CIReportRowStatusRegressed, row.Status)
}

func TestCIReportExplicitBaselineRunIDsIgnoreOtherRepositories(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	t0 := time.Date(2024, 1, 26, 0, 0, 0, 0, time.UTC)
	otherRepo := "https://github.com/other/repo"
	provider := ciCommitProvider{
		"base":       ciCommitInfo("base", nil, "base", t0),
		"head":       ciCommitInfo("head", new("base"), "head", t0.Add(24*time.Hour)),
		"other-base": {Sha: "other-base", Repository: otherRepo, Timestamp: &t0},
	}
	ing := service.NewIngester(store, provider)
	baseline := ciSubmit(t, ing, ctx, "explicit-baseline", "base", 30)
	contender := ciSubmit(t, ing, ctx, "ci-run", "head", 100)
	otherReq := machineReq(samples(300, 301, 302), "s")
	otherReq.RunID = "explicit-baseline"
	otherReq.GitHub.Repository = otherRepo
	otherReq.GitHub.Commit = "other-base"
	_, err := ing.Submit(ctx, otherReq)
	require.NoError(t, err)

	reporter := service.NewCIReporter(store, "")
	report, err := reporter.Report(ctx, service.CIReportQuery{
		RunIDs:         []string{"ci-run"},
		BaselineRunIDs: []string{"explicit-baseline"},
	})
	require.NoError(t, err)

	require.Len(t, report.Runs, 1)
	require.Nil(t, report.Runs[0].BaselineError)
	require.NotNil(t, report.Runs[0].BaselineRunID)
	assert.Equal(t, "explicit-baseline", *report.Runs[0].BaselineRunID)
	require.Len(t, report.Runs[0].Comparisons, 1)
	row := report.Runs[0].Comparisons[0]
	assert.Equal(t, contender.ID, row.Contender.ResultID)
	require.NotNil(t, row.Baseline)
	assert.Equal(t, baseline.ID, row.Baseline.ResultID)
}

func TestCIReportPairwiseOnlyRegressionIsSkipped(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	t0 := time.Date(2024, 2, 1, 0, 0, 0, 0, time.UTC)
	provider := ciCommitProvider{
		"base": ciCommitInfo("base", nil, "base", t0),
		"head": ciCommitInfo("head", new("base"), "base", t0.Add(24*time.Hour)),
	}
	ing := service.NewIngester(store, provider)
	ciSubmit(t, ing, ctx, "baseline-run", "base", 10)
	ciSubmit(t, ing, ctx, "ci-run", "head", 100)

	reporter := service.NewCIReporter(store, "")
	report, err := reporter.Report(ctx, service.CIReportQuery{
		Repository: testRepo,
		CommitSHA:  "head",
		Baseline:   service.CIReportBaselineParent,
	})
	require.NoError(t, err)

	assert.Equal(t, service.CIReportStatusSkipped, report.Status)
	require.Len(t, report.Runs, 1)
	require.Len(t, report.Runs[0].Comparisons, 1)
	row := report.Runs[0].Comparisons[0]
	assert.Equal(t, service.CIReportRowStatusInsufficient, row.Status)
	require.NotNil(t, row.Analysis)
	require.NotNil(t, row.Analysis.Pairwise)
	assert.True(t, row.Analysis.Pairwise.RegressionIndicated)
	assert.Nil(t, row.Analysis.LookbackZScore)
	assert.Equal(t, 0, report.Summary.Regressions)
	assert.Equal(t, 0, report.Summary.Analyzed)
}

func TestCIReportNoBaselineRunIsSkipped(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	t0 := time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC)
	provider := ciCommitProvider{
		"base": ciCommitInfo("base", nil, "base", t0),
		"head": ciCommitInfo("head", new("base"), "base", t0.Add(24*time.Hour)),
	}
	ing := service.NewIngester(store, provider)

	baselineReq := machineReq(samples(10, 11, 12), "s")
	baselineReq.RunID = "unrelated-baseline"
	baselineReq.Tags["name"] = "other-bench"
	baselineReq.GitHub.Commit = "base"
	_, err := ing.Submit(ctx, baselineReq)
	require.NoError(t, err)
	ciSubmit(t, ing, ctx, "ci-run", "head", 100)

	reporter := service.NewCIReporter(store, "")
	report, err := reporter.Report(ctx, service.CIReportQuery{
		Repository: testRepo,
		CommitSHA:  "head",
		Baseline:   service.CIReportBaselineParent,
	})
	require.NoError(t, err)

	assert.Equal(t, service.CIReportStatusSkipped, report.Status)
	require.Len(t, report.Runs, 1)
	assert.Nil(t, report.Runs[0].BaselineRunID)
	if assert.NotNil(t, report.Runs[0].BaselineError) {
		assert.Equal(t, service.CIReportBaselineErrorNoBaselineRun, report.Runs[0].BaselineError.Code)
		assert.Equal(t, service.CIReportBaselineAncestorLimit, report.Runs[0].BaselineError.SearchedAncestorLimit)
	}
	assert.Equal(t, 1, report.Summary.MissingBaseline)
}

func TestCIReportRejectsMixedRunSelector(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	ing := service.NewIngester(store, commit.LocalProvider{})
	req := machineReq(samples(1, 2, 3), "s")
	req.RunID = "run-a"
	req.GitHub.Commit = "sha-a"
	_, err := ing.Submit(ctx, req)
	require.NoError(t, err)
	req.RunID = "run-b"
	req.GitHub.Commit = "sha-b"
	_, err = ing.Submit(ctx, req)
	require.NoError(t, err)

	reporter := service.NewCIReporter(store, "")
	_, err = reporter.Report(ctx, service.CIReportQuery{RunIDs: []string{"run-a", "run-b"}})
	var validation *service.ValidationError
	require.ErrorAs(t, err, &validation)
	assert.Contains(t, validation.Error(), "same repository and commit")
}

func TestCIReportRejectsInvalidExplicitBaselineRunIDs(t *testing.T) {
	_, store, _, ctx := newIngester(t)
	reporter := service.NewCIReporter(store, "")

	tests := []struct {
		name  string
		query service.CIReportQuery
		want  string
	}{
		{
			name: "without run ids",
			query: service.CIReportQuery{
				Repository:     testRepo,
				CommitSHA:      "head",
				BaselineRunIDs: []string{"baseline-run"},
			},
			want: "baseline_run_ids requires run_ids",
		},
		{
			name: "with automatic baseline selector",
			query: service.CIReportQuery{
				RunIDs:         []string{"ci-run"},
				BaselineRunIDs: []string{"baseline-run"},
				Baseline:       service.CIReportBaselineParent,
			},
			want: "baseline cannot be set with baseline_run_ids",
		},
		{
			name: "count mismatch",
			query: service.CIReportQuery{
				RunIDs:         []string{"ci-run", "other-run"},
				BaselineRunIDs: []string{"baseline-run"},
			},
			want: "baseline_run_ids must match run_ids",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := reporter.Report(ctx, tt.query)
			var validation *service.ValidationError
			require.ErrorAs(t, err, &validation)
			assert.Contains(t, validation.Error(), tt.want)
		})
	}
}
