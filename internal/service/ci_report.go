package service

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/stats"
	"github.com/conbench/conbench/internal/storage"
)

const CIReportMaxComparisonRows = 5000
const CIReportBaselineAncestorLimit = 20

type CIReportStatus string

const (
	CIReportStatusSuccess        CIReportStatus = "success"
	CIReportStatusFailure        CIReportStatus = "failure"
	CIReportStatusActionRequired CIReportStatus = "action_required"
	CIReportStatusSkipped        CIReportStatus = "skipped"
)

type CIReportBaseline string

const (
	CIReportBaselineForkPoint     CIReportBaseline = "fork_point"
	CIReportBaselineParent        CIReportBaseline = "parent"
	CIReportBaselineLatestDefault CIReportBaseline = "latest_default"
	CIReportBaselineExplicitRun   CIReportBaseline = "explicit_run"
)

const (
	CIReportRowStatusRegressed       = statusRegressed
	CIReportRowStatusImproved        = statusImproved
	CIReportRowStatusStable          = statusStable
	CIReportRowStatusInsufficient    = statusInsufficient
	CIReportRowStatusErrored         = "errored"
	CIReportRowStatusMissingBaseline = "missing_baseline"
	CIReportRowStatusNotComparable   = "not_comparable"
)

const (
	CIReportBaselineErrorMissingCommitMetadata = "missing_commit_metadata"
	CIReportBaselineErrorNoBaselineRun         = "no_baseline_run"
	CIReportBaselineErrorUnknownParent         = "unknown_parent"
	CIReportBaselineErrorUnknownForkPoint      = "unknown_fork_point"
	CIReportBaselineErrorDefaultBranchRun      = "default_branch_run"
	CIReportBaselineErrorUnknownLatestDefault  = "unknown_latest_default"
	CIReportBaselineErrorUnknownCandidate      = "unknown_baseline_candidate"
	CIReportBaselineErrorExplicitRunNotFound   = "explicit_baseline_run_not_found"
	CIReportBaselineErrorAmbiguousBaselineRun  = "ambiguous_baseline_run"
)

type CIReportQuery struct {
	Repository     string
	CommitSHA      string
	RunIDs         []string
	BaselineRunIDs []string
	Baseline       CIReportBaseline
	Threshold      float64
	ThresholdZ     float64
	PublicBaseURL  string
}

type CIReport struct {
	Repository     string               `json:"repository"`
	CommitSHA      *string              `json:"commit_sha"`
	SelectedRunIDs []string             `json:"selected_run_ids"`
	MissingRunIDs  []string             `json:"missing_run_ids"`
	Baseline       CIReportBaseline     `json:"baseline"`
	Status         CIReportStatus       `json:"status" enum:"success,failure,action_required,skipped"`
	StatusReason   string               `json:"status_reason"`
	Threshold      float64              `json:"threshold"`
	ThresholdZ     float64              `json:"threshold_z"`
	Summary        CIReportSummary      `json:"summary"`
	Runs           []CIReportRun        `json:"runs"`
	ReportURL      string               `json:"report_url"`
	Comparisons    []CIReportComparison `json:"-"`
}

type CIReportSummary struct {
	Runs              int `json:"runs"`
	MissingRuns       int `json:"missing_runs"`
	ContenderResults  int `json:"contender_results"`
	Compared          int `json:"compared"`
	Analyzed          int `json:"analyzed"`
	Regressions       int `json:"regressions"`
	Improvements      int `json:"improvements"`
	BenchmarkErrors   int `json:"benchmark_errors"`
	MissingBaseline   int `json:"missing_baseline"`
	NotComparable     int `json:"not_comparable"`
	commitlessRuns    int
	baselineErrors    int
	baselineActionErr int
	insufficient      int
	stable            int
}

type CIReportRun struct {
	RunID          string                 `json:"run_id"`
	RunTags        map[string]any         `json:"run_tags"`
	RunReason      *string                `json:"run_reason"`
	Commit         *Commit                `json:"commit"`
	BaselineRunID  *string                `json:"baseline_run_id"`
	BaselineCommit *Commit                `json:"baseline_commit"`
	CommitsSkipped []string               `json:"commits_skipped"`
	BaselineError  *CIReportBaselineError `json:"baseline_error"`
	Comparisons    []CIReportComparison   `json:"comparisons"`
}

type CIReportComparison struct {
	Status             string                `json:"status" enum:"regressed,improved,stable,insufficient,errored,missing_baseline,not_comparable"`
	Name               string                `json:"name"`
	Tags               map[string]any        `json:"tags"`
	Context            map[string]any        `json:"context"`
	Info               map[string]any        `json:"info"`
	Hardware           Hardware              `json:"hardware"`
	HistoryFingerprint string                `json:"history_fingerprint"`
	Unit               *string               `json:"unit"`
	LessIsBetter       *bool                 `json:"less_is_better"`
	Contender          CIReportSide          `json:"contender"`
	Baseline           *CIReportBaselineSide `json:"baseline"`
	Analysis           *CIReportAnalysis     `json:"analysis"`
	Error              map[string]any        `json:"error" nullable:"true"`
	Reason             *string               `json:"reason,omitempty"`
	Links              CIReportRowLinks      `json:"links"`
}

// CIReportAnalysis has the same wire shape as CompareAnalysis, but is nullable
// in CI report rows where comparison is not attempted or not comparable. Keeping
// it separate avoids marking the compare endpoint's non-null analysis nullable.
type CIReportAnalysis struct {
	_              struct{}          `json:"-" nullable:"true"`
	Pairwise       *PairwiseAnalysis `json:"pairwise"`
	LookbackZScore *LookbackAnalysis `json:"lookback_z_score"`
}

type CIReportSide struct {
	ResultID        string         `json:"result_id"`
	RunID           string         `json:"run_id"`
	ResultTimestamp time.Time      `json:"result_timestamp"`
	CommitSHA       *string        `json:"commit_sha"`
	CommitTimestamp *time.Time     `json:"commit_timestamp"`
	Error           map[string]any `json:"error" nullable:"true"`
	SVS             *float64       `json:"single_value_summary"`
	SVSType         string         `json:"single_value_summary_type"`
}

// CIReportBaselineSide is nullable when a contender row has no baseline. It
// omits the contender-only error object so generated clients can model the
// nullable ref without tripping over a nested arbitrary-object union.
type CIReportBaselineSide struct {
	_               struct{}   `json:"-" nullable:"true"`
	ResultID        string     `json:"result_id"`
	RunID           string     `json:"run_id"`
	ResultTimestamp time.Time  `json:"result_timestamp"`
	CommitSHA       *string    `json:"commit_sha"`
	CommitTimestamp *time.Time `json:"commit_timestamp"`
	SVS             *float64   `json:"single_value_summary"`
	SVSType         string     `json:"single_value_summary_type"`
}

type CIReportRowLinks struct {
	Result  string `json:"result"`
	Compare string `json:"compare,omitempty"`
	Series  string `json:"series"`
}

type CIReportBaselineError struct {
	_                     struct{}         `json:"-" nullable:"true"`
	Code                  string           `json:"code"`
	Message               string           `json:"message"`
	RunID                 string           `json:"run_id"`
	Baseline              CIReportBaseline `json:"baseline"`
	CommitSHA             *string          `json:"commit_sha"`
	SearchedAncestorLimit int              `json:"searched_ancestor_limit,omitempty"`
	SearchedCommitSHAs    []string         `json:"searched_commit_shas,omitempty"`
}

type CIReporter struct {
	store         storage.Store
	reader        *Reader
	publicBaseURL string
}

func NewCIReporter(store storage.Store, publicBaseURL ...string) *CIReporter {
	baseURL := ""
	if len(publicBaseURL) > 0 {
		baseURL = publicBaseURL[0]
	}
	return &CIReporter{store: store, reader: NewReader(store), publicBaseURL: baseURL}
}

func (r *CIReporter) Report(ctx context.Context, q CIReportQuery) (*CIReport, error) {
	baseline := ciReportBaseline(q.Baseline)
	if err := validateExplicitBaselineRunIDs(q); err != nil {
		return nil, err
	}
	if len(q.BaselineRunIDs) > 0 {
		baseline = CIReportBaselineExplicitRun
	} else if !validCIReportBaseline(baseline) {
		return nil, &ValidationError{Message: "invalid baseline"}
	}
	threshold := q.Threshold
	if threshold == 0 {
		threshold = stats.PairwisePercentThresholdDefault
	}
	thresholdZ := q.ThresholdZ
	if thresholdZ == 0 {
		thresholdZ = stats.ZScoreThresholdDefault
	}

	selection, err := r.selectCIReportRuns(ctx, q)
	if err != nil {
		return nil, err
	}

	report := &CIReport{
		Repository:     selection.repository,
		CommitSHA:      selection.commitSHA,
		SelectedRunIDs: ciReportSelectedRunIDs(selection.runs),
		MissingRunIDs:  selection.missingRunIDs,
		Baseline:       baseline,
		Threshold:      threshold,
		ThresholdZ:     thresholdZ,
		ReportURL:      r.ciReportURL(q, selection.repository, selection.commitSHA, baseline, threshold, thresholdZ),
	}
	report.Runs, err = ciReportRunsFromRows(selection.runs)
	if err != nil {
		return nil, err
	}
	report.Summary.Runs = len(report.Runs)
	report.Summary.MissingRuns = len(selection.missingRunIDs)

	if len(selection.runs) == 0 {
		report.Status = CIReportStatusActionRequired
		report.StatusReason = "no runs found for selected commit"
		return report, nil
	}
	if selection.allCommitless {
		report.Summary.commitlessRuns = len(selection.runs)
		report.applyCommitlessBaselineErrors(baseline)
		report.Status = CIReportStatusActionRequired
		report.StatusReason = "selected runs are not connected to commit metadata"
		return report, nil
	}

	runKeys := ciReportRunKeys(selection.runs)
	rowCount, err := r.store.CountCIReportRows(ctx, runKeys)
	if err != nil {
		return nil, fmt.Errorf("count ci report rows: %w", err)
	}
	if rowCount > CIReportMaxComparisonRows {
		return nil, &ValidationError{Message: fmt.Sprintf("comparison row limit exceeded: %d > %d", rowCount, CIReportMaxComparisonRows)}
	}
	report.Summary.ContenderResults = int(rowCount)
	if rowCount == 0 {
		report.Status = CIReportStatusActionRequired
		report.StatusReason = "selected runs contain no benchmark results"
		return report, nil
	}

	contenderRows, err := r.store.SelectCIReportRows(ctx, runKeys, nil)
	if err != nil {
		return nil, fmt.Errorf("select ci report contender rows: %w", err)
	}
	contendersByRun := ciReportRowsByRunID(contenderRows)
	var selections map[string]ciReportBaselineSelection
	if len(q.BaselineRunIDs) > 0 {
		selections, err = r.selectExplicitBaselineRuns(ctx, baseline, q.RunIDs, q.BaselineRunIDs, selection.runs)
	} else {
		selections, err = r.selectBaselineRuns(ctx, baseline, selection.runs, contendersByRun)
	}
	if err != nil {
		return nil, err
	}
	report.applyBaselineSelections(selections)

	baselineRunKeys := ciReportBaselineRunKeys(selections)
	rows, err := r.store.SelectCIReportRows(ctx, runKeys, baselineRunKeys)
	if err != nil {
		return nil, fmt.Errorf("select ci report rows: %w", err)
	}
	report.Comparisons, err = r.assembleComparisons(ctx, rows, selections, threshold, thresholdZ)
	if err != nil {
		return nil, err
	}
	report.attachComparisonsToRuns()
	report.deriveSummaryFromComparisons()
	report.Status = report.deriveStatus()
	report.StatusReason = report.deriveStatusReason()
	return report, nil
}

func validateExplicitBaselineRunIDs(q CIReportQuery) error {
	if len(q.BaselineRunIDs) == 0 {
		return nil
	}
	switch {
	case len(q.RunIDs) == 0:
		return &ValidationError{Message: "baseline_run_ids requires run_ids"}
	case q.Baseline != "":
		return &ValidationError{Message: "baseline cannot be set with baseline_run_ids"}
	case len(q.BaselineRunIDs) != len(q.RunIDs):
		return &ValidationError{Message: "baseline_run_ids must match run_ids count"}
	default:
		return nil
	}
}

type ciReportRunSelection struct {
	repository     string
	commitSHA      *string
	runs           []storage.CIReportRunRow
	missingRunIDs  []string
	allCommitless  bool
	commitSelector bool
}

func (r *CIReporter) selectCIReportRuns(ctx context.Context, q CIReportQuery) (ciReportRunSelection, error) {
	hasRepo := strings.TrimSpace(q.Repository) != ""
	hasCommit := strings.TrimSpace(q.CommitSHA) != ""
	hasRunIDs := len(q.RunIDs) > 0
	if hasRepo != hasCommit {
		return ciReportRunSelection{}, &ValidationError{Message: "repository and commit_sha must be provided together"}
	}
	if !hasRepo && !hasRunIDs {
		return ciReportRunSelection{}, &ValidationError{Message: "provide repository and commit_sha or run_ids"}
	}

	if hasRepo {
		return r.selectCommitModeRuns(ctx, q)
	}
	return r.selectRunOnlyRuns(ctx, q.RunIDs)
}

func (r *CIReporter) selectCommitModeRuns(ctx context.Context, q CIReportQuery) (ciReportRunSelection, error) {
	repository := commit.NormalizeRepoURL(q.Repository)
	sha := strings.TrimSpace(q.CommitSHA)
	out := ciReportRunSelection{
		repository: repository, commitSHA: &sha, commitSelector: true,
	}
	rows, err := r.store.SelectCIReportRunsByCommit(ctx, repository, sha)
	if err != nil {
		return ciReportRunSelection{}, fmt.Errorf("select ci report runs by commit: %w", err)
	}
	if len(q.RunIDs) == 0 {
		out.runs = rows
		return out, nil
	}

	out.runs = ciReportFilterRunsByIDs(rows, q.RunIDs)
	out.missingRunIDs = ciReportMissingRunIDs(q.RunIDs, rows)
	return out, nil
}

func (r *CIReporter) selectRunOnlyRuns(ctx context.Context, runIDs []string) (ciReportRunSelection, error) {
	rows, err := r.store.SelectCIReportRunsByIDs(ctx, runIDs)
	if err != nil {
		return ciReportRunSelection{}, fmt.Errorf("select ci report runs by ids: %w", err)
	}
	if len(rows) == 0 {
		return ciReportRunSelection{}, ErrNotFound
	}
	repository, commitSHA, allCommitless, err := ciReportValidateRunOnlyRows(rows)
	if err != nil {
		return ciReportRunSelection{}, err
	}
	return ciReportRunSelection{
		repository:    repository,
		commitSHA:     commitSHA,
		runs:          rows,
		missingRunIDs: ciReportMissingRunIDs(runIDs, rows),
		allCommitless: allCommitless,
	}, nil
}

func ciReportValidateRunOnlyRows(rows []storage.CIReportRunRow) (string, *string, bool, error) {
	repository := commit.NormalizeRepoURL(rows[0].CommitRepoURL)
	allCommitless := rows[0].CommitSha == nil
	var commitSHA *string
	if rows[0].CommitSha != nil {
		sha := *rows[0].CommitSha
		commitSHA = &sha
	}

	for _, row := range rows {
		if commit.NormalizeRepoURL(row.CommitRepoURL) != repository {
			return "", nil, false, &ValidationError{Message: "run_ids must share the same repository and commit"}
		}
		rowCommitless := row.CommitSha == nil
		if rowCommitless != allCommitless {
			return "", nil, false, &ValidationError{Message: "run_ids must share the same repository and commit"}
		}
		if allCommitless {
			continue
		}
		if row.CommitRepository == nil || commit.NormalizeRepoURL(*row.CommitRepository) != repository ||
			row.CommitSha == nil || *row.CommitSha != *commitSHA {
			return "", nil, false, &ValidationError{Message: "run_ids must share the same repository and commit"}
		}
	}
	return repository, commitSHA, allCommitless, nil
}

func ciReportMissingRunIDs(explicit []string, rows []storage.CIReportRunRow) []string {
	found := make(map[string]bool, len(rows))
	for _, row := range rows {
		found[row.RunID] = true
	}
	seenMissing := map[string]bool{}
	missing := []string{}
	for _, id := range explicit {
		if found[id] || seenMissing[id] {
			continue
		}
		seenMissing[id] = true
		missing = append(missing, id)
	}
	return missing
}

func ciReportFilterRunsByIDs(rows []storage.CIReportRunRow, runIDs []string) []storage.CIReportRunRow {
	keep := make(map[string]bool, len(runIDs))
	for _, id := range runIDs {
		keep[id] = true
	}
	out := make([]storage.CIReportRunRow, 0, len(rows))
	for _, row := range rows {
		if keep[row.RunID] {
			out = append(out, row)
		}
	}
	return out
}

func ciReportRunsFromRows(rows []storage.CIReportRunRow) ([]CIReportRun, error) {
	runs := make([]CIReportRun, 0, len(rows))
	for _, row := range rows {
		tags, err := jsonObject(row.RunTags)
		if err != nil {
			return nil, err
		}
		if tags == nil {
			tags = map[string]any{}
		}
		runs = append(runs, CIReportRun{
			RunID:     row.RunID,
			RunTags:   tags,
			RunReason: row.RunReason,
			Commit:    ciReportCommitFromRun(row),
		})
	}
	return runs, nil
}

type ciReportBaselineSelection struct {
	runID             string
	contenderCommitID string
	baselineRunID     *string
	baselineCommitID  string
	commit            *storage.CIReportCommitRow
	commitsSkipped    []string
	baselineError     *CIReportBaselineError
}

type ciReportBaselineCandidate struct {
	runID           string
	commitID        string
	runReason       *string
	commit          storage.CIReportCommitRow
	depth           int
	resultTimestamp time.Time
	sameReason      bool
}

func (r *CIReporter) selectBaselineRuns(
	ctx context.Context,
	baseline CIReportBaseline,
	runs []storage.CIReportRunRow,
	contendersByRun map[string][]storage.CIReportResultRow,
) (map[string]ciReportBaselineSelection, error) {
	selections := make(map[string]ciReportBaselineSelection, len(runs))
	for _, run := range runs {
		selection := ciReportBaselineSelection{runID: run.RunID}
		if run.CommitID != nil {
			selection.contenderCommitID = *run.CommitID
		}
		if run.CommitSha == nil {
			selections[run.RunID] = selection
			continue
		}
		candidateSHA, candidateErr, err := r.resolveBaselineCandidate(ctx, baseline, run)
		if err != nil {
			return nil, err
		}
		if candidateErr != nil {
			selection.baselineError = candidateErr
			selections[run.RunID] = selection
			continue
		}

		ancestry, err := r.store.SelectCIReportBaselineAncestry(ctx, commit.NormalizeRepoURL(run.CommitRepoURL), candidateSHA, CIReportBaselineAncestorLimit)
		if err != nil {
			return nil, fmt.Errorf("select ci report baseline ancestry: %w", err)
		}
		if len(ancestry) == 0 {
			selection.baselineError = &CIReportBaselineError{
				Code: CIReportBaselineErrorUnknownCandidate, Message: "baseline candidate commit metadata not found",
				RunID: run.RunID, Baseline: baseline, CommitSHA: run.CommitSha,
			}
			selections[run.RunID] = selection
			continue
		}

		candidate, ok, err := r.findBaselineRun(ctx, run, contendersByRun[run.RunID], ancestry)
		if err != nil {
			return nil, err
		}
		if ok {
			runID := candidate.runID
			selection.baselineRunID = &runID
			selection.baselineCommitID = candidate.commitID
			selection.commit = &candidate.commit
			selection.commitsSkipped = ciReportSkippedCommits(ancestry, candidate.depth)
		} else {
			selection.baselineError = &CIReportBaselineError{
				Code:                  CIReportBaselineErrorNoBaselineRun,
				Message:               fmt.Sprintf("searched %d ancestors, no baseline run found", CIReportBaselineAncestorLimit),
				RunID:                 run.RunID,
				Baseline:              baseline,
				CommitSHA:             run.CommitSha,
				SearchedAncestorLimit: CIReportBaselineAncestorLimit,
				SearchedCommitSHAs:    ciReportCommitSHAs(ancestry),
			}
		}
		selections[run.RunID] = selection
	}
	return selections, nil
}

func (r *CIReporter) selectExplicitBaselineRuns(
	ctx context.Context,
	baseline CIReportBaseline,
	runIDs []string,
	baselineRunIDs []string,
	runs []storage.CIReportRunRow,
) (map[string]ciReportBaselineSelection, error) {
	baselineByRunID := make(map[string]string, len(runIDs))
	for i, runID := range runIDs {
		baselineByRunID[runID] = baselineRunIDs[i]
	}

	baselineRows, err := r.store.SelectCIReportRunsByIDs(ctx, baselineRunIDs)
	if err != nil {
		return nil, fmt.Errorf("select ci report explicit baseline runs: %w", err)
	}
	baselineRowsByID := map[string][]storage.CIReportRunRow{}
	for _, row := range baselineRows {
		baselineRowsByID[row.RunID] = append(baselineRowsByID[row.RunID], row)
	}

	selections := make(map[string]ciReportBaselineSelection, len(runs))
	for _, run := range runs {
		selection := ciReportBaselineSelection{
			runID:             run.RunID,
			contenderCommitID: metaCommitID(run),
		}
		baselineRunID := baselineByRunID[run.RunID]
		if baselineRunID == "" {
			selections[run.RunID] = selection
			continue
		}
		rows := baselineRowsByID[baselineRunID]
		contenderRepo := commit.NormalizeRepoURL(run.CommitRepoURL)
		sameRepoRows := make([]storage.CIReportRunRow, 0, len(rows))
		for _, row := range rows {
			if commit.NormalizeRepoURL(row.CommitRepoURL) == contenderRepo {
				sameRepoRows = append(sameRepoRows, row)
			}
		}
		rows = sameRepoRows
		switch {
		case len(rows) == 0:
			selection.baselineError = &CIReportBaselineError{
				Code:     CIReportBaselineErrorExplicitRunNotFound,
				Message:  "explicit baseline run was not found",
				RunID:    run.RunID,
				Baseline: baseline,
			}
		case len(rows) > 1:
			selection.baselineError = &CIReportBaselineError{
				Code:     CIReportBaselineErrorAmbiguousBaselineRun,
				Message:  "explicit baseline run id matched multiple commits or run metadata groups",
				RunID:    run.RunID,
				Baseline: baseline,
			}
		default:
			base := rows[0]
			if base.CommitID == nil || base.CommitSha == nil {
				selection.baselineError = &CIReportBaselineError{
					Code:     CIReportBaselineErrorMissingCommitMetadata,
					Message:  "explicit baseline run is not connected to commit metadata",
					RunID:    run.RunID,
					Baseline: baseline,
				}
				break
			}
			commitRow, err := r.store.GetCIReportCommit(ctx, commit.NormalizeRepoURL(base.CommitRepoURL), *base.CommitSha)
			if err != nil {
				if errors.Is(err, storage.ErrNotFound) {
					selection.baselineError = &CIReportBaselineError{
						Code:     CIReportBaselineErrorMissingCommitMetadata,
						Message:  "explicit baseline commit metadata was not found",
						RunID:    run.RunID,
						Baseline: baseline,
					}
					break
				}
				return nil, fmt.Errorf("get explicit baseline commit: %w", err)
			}
			id := baselineRunID
			selection.baselineRunID = &id
			selection.baselineCommitID = *base.CommitID
			selection.commit = &commitRow
		}
		selections[run.RunID] = selection
	}
	return selections, nil
}

func (r *CIReporter) resolveBaselineCandidate(
	ctx context.Context,
	baseline CIReportBaseline,
	run storage.CIReportRunRow,
) (string, *CIReportBaselineError, error) {
	switch baseline {
	case CIReportBaselineParent:
		if run.CommitParent == nil || *run.CommitParent == "" {
			return "", &CIReportBaselineError{
				Code: CIReportBaselineErrorUnknownParent, Message: "contender parent commit is unknown",
				RunID: run.RunID, Baseline: baseline, CommitSHA: run.CommitSha,
			}, nil
		}
		return *run.CommitParent, nil, nil
	case CIReportBaselineForkPoint:
		if run.CommitForkPointSha == nil || *run.CommitForkPointSha == "" {
			return "", &CIReportBaselineError{
				Code: CIReportBaselineErrorUnknownForkPoint, Message: "contender fork point is unknown",
				RunID: run.RunID, Baseline: baseline, CommitSHA: run.CommitSha,
			}, nil
		}
		if run.CommitSha != nil && *run.CommitForkPointSha == *run.CommitSha {
			return "", &CIReportBaselineError{
				Code: CIReportBaselineErrorDefaultBranchRun, Message: "contender is already on the default branch",
				RunID: run.RunID, Baseline: baseline, CommitSHA: run.CommitSha,
			}, nil
		}
		return *run.CommitForkPointSha, nil, nil
	case CIReportBaselineLatestDefault:
		row, err := r.store.SelectLatestDefaultCommit(ctx, commit.NormalizeRepoURL(run.CommitRepoURL))
		if err != nil {
			if errors.Is(err, storage.ErrNotFound) {
				return "", &CIReportBaselineError{
					Code: CIReportBaselineErrorUnknownLatestDefault, Message: "latest default branch commit is unknown",
					RunID: run.RunID, Baseline: baseline, CommitSHA: run.CommitSha,
				}, nil
			}
			return "", nil, fmt.Errorf("select latest default commit: %w", err)
		}
		return row.CommitSha, nil, nil
	default:
		return "", nil, &ValidationError{Message: "invalid baseline"}
	}
}

func (r *CIReporter) findBaselineRun(
	ctx context.Context,
	contender storage.CIReportRunRow,
	contenderRows []storage.CIReportResultRow,
	ancestry []storage.CIReportCommitRow,
) (ciReportBaselineCandidate, bool, error) {
	fingerprints := map[string]bool{}
	for _, row := range contenderRows {
		fingerprints[row.HistoryFingerprint] = true
	}
	if len(fingerprints) == 0 {
		return ciReportBaselineCandidate{}, false, nil
	}

	var candidates []ciReportBaselineCandidate
	repository := commit.NormalizeRepoURL(contender.CommitRepoURL)
	for depth, c := range ancestry {
		runs, err := r.store.SelectCIReportRunsByCommit(ctx, repository, c.CommitSha)
		if err != nil {
			return ciReportBaselineCandidate{}, false, fmt.Errorf("select ci report baseline runs: %w", err)
		}
		runMeta := map[string]storage.CIReportRunRow{}
		candidateRunKeys := []storage.CIReportRunKey{}
		for _, run := range runs {
			if run.CommitID == nil {
				continue
			}
			if run.RunID == contender.RunID && contender.CommitID != nil && *run.CommitID == *contender.CommitID {
				continue
			}
			key := ciReportRunKeyString(run.RunID, *run.CommitID)
			runMeta[key] = run
			candidateRunKeys = append(candidateRunKeys, storage.CIReportRunKey{RunID: run.RunID, CommitID: *run.CommitID})
		}
		if len(candidateRunKeys) == 0 {
			continue
		}
		rows, err := r.store.SelectCIReportRows(ctx, candidateRunKeys, nil)
		if err != nil {
			return ciReportBaselineCandidate{}, false, fmt.Errorf("select ci report baseline candidate rows: %w", err)
		}
		latestByRunKey := map[string]time.Time{}
		for _, row := range rows {
			if !fingerprints[row.HistoryFingerprint] {
				continue
			}
			key, ok := ciReportResultRunKey(row)
			if !ok {
				continue
			}
			if ts, ok := latestByRunKey[key]; !ok || row.ResultTimestamp.After(ts) {
				latestByRunKey[key] = row.ResultTimestamp
			}
		}
		for runKey, ts := range latestByRunKey {
			meta := runMeta[runKey]
			candidates = append(candidates, ciReportBaselineCandidate{
				runID: meta.RunID, commitID: metaCommitID(meta), runReason: meta.RunReason, commit: c, depth: depth,
				resultTimestamp: ts,
				sameReason:      sameStringPtr(contender.RunReason, meta.RunReason),
			})
		}
	}
	if len(candidates) == 0 {
		return ciReportBaselineCandidate{}, false, nil
	}
	sort.Slice(candidates, func(i, j int) bool {
		a, b := candidates[i], candidates[j]
		if a.sameReason != b.sameReason {
			return a.sameReason
		}
		if !sameTimePtr(a.commit.Timestamp, b.commit.Timestamp) {
			if a.commit.Timestamp == nil {
				return false
			}
			if b.commit.Timestamp == nil {
				return true
			}
			return a.commit.Timestamp.After(*b.commit.Timestamp)
		}
		if !a.resultTimestamp.Equal(b.resultTimestamp) {
			return a.resultTimestamp.After(b.resultTimestamp)
		}
		if a.runID != b.runID {
			return a.runID > b.runID
		}
		return a.commitID > b.commitID
	})
	return candidates[0], true, nil
}

func (r *CIReporter) assembleComparisons(
	ctx context.Context,
	rows []storage.CIReportResultRow,
	selections map[string]ciReportBaselineSelection,
	threshold float64,
	thresholdZ float64,
) ([]CIReportComparison, error) {
	contenderRunKeys := map[string]bool{}
	baselineRunKeys := map[string]bool{}
	for runID, selection := range selections {
		if selection.contenderCommitID != "" {
			contenderRunKeys[ciReportRunKeyString(runID, selection.contenderCommitID)] = true
		}
		if selection.baselineRunID != nil && selection.baselineCommitID != "" {
			baselineRunKeys[ciReportRunKeyString(*selection.baselineRunID, selection.baselineCommitID)] = true
		}
	}
	baselineRows := map[string]map[string]storage.CIReportResultRow{}
	for _, row := range rows {
		runKey, ok := ciReportResultRunKey(row)
		if !ok || !baselineRunKeys[runKey] {
			continue
		}
		if baselineRows[runKey] == nil {
			baselineRows[runKey] = map[string]storage.CIReportResultRow{}
		}
		baselineRows[runKey][row.HistoryFingerprint] = row
	}

	comparisons := []CIReportComparison{}
	for _, row := range rows {
		runKey, ok := ciReportResultRunKey(row)
		if !ok || !contenderRunKeys[runKey] {
			continue
		}
		comp, err := ciReportComparisonBase(row)
		if err != nil {
			return nil, err
		}
		if row.Error != nil {
			comp.Status = CIReportRowStatusErrored
			comp.Error, err = jsonObject(row.Error)
			if err != nil {
				return nil, err
			}
			comp.Contender.Error = comp.Error
			comparisons = append(comparisons, comp)
			continue
		}
		selection := selections[row.RunID]
		if selection.baselineRunID == nil {
			comp.Status = CIReportRowStatusMissingBaseline
			comparisons = append(comparisons, comp)
			continue
		}
		baselineKey := ciReportRunKeyString(*selection.baselineRunID, selection.baselineCommitID)
		baselineRow, ok := baselineRows[baselineKey][row.HistoryFingerprint]
		if !ok {
			comp.Status = CIReportRowStatusMissingBaseline
			comparisons = append(comparisons, comp)
			continue
		}
		analysis, err := r.reader.Compare(ctx, baselineRow.ResultID, row.ResultID, threshold, thresholdZ)
		if err != nil {
			if errors.Is(err, ErrNotComparable) {
				comp.Status = CIReportRowStatusNotComparable
				reason := err.Error()
				comp.Reason = &reason
				baseSide := ciReportBaselineSideFromRow(baselineRow)
				comp.Baseline = &baseSide
				comparisons = append(comparisons, comp)
				continue
			}
			return nil, err
		}
		comp.Analysis = ciReportAnalysisFromCompare(analysis.Analysis)
		comp.Unit = &analysis.Unit
		comp.LessIsBetter = &analysis.LessIsBetter
		baseSide := ciReportBaselineSideFromRow(baselineRow)
		baseSide.SVS = &analysis.Baseline.SVS
		comp.Baseline = &baseSide
		comp.Contender.SVS = &analysis.Contender.SVS
		comp.Links.Compare = ciReportCompareLink(baselineRow.ResultID, row.ResultID, threshold, thresholdZ)
		comp.Status = ciReportComparisonStatus(analysis.Analysis.LookbackZScore)
		comparisons = append(comparisons, comp)
	}
	return comparisons, nil
}

func ciReportComparisonBase(row storage.CIReportResultRow) (CIReportComparison, error) {
	tags, err := jsonObject(row.CaseTags)
	if err != nil {
		return CIReportComparison{}, err
	}
	if tags == nil {
		tags = map[string]any{}
	}
	tags["name"] = row.CaseName
	contextTags, err := jsonObject(row.ContextTags)
	if err != nil {
		return CIReportComparison{}, err
	}
	infoTags, err := jsonObject(row.InfoTags)
	if err != nil {
		return CIReportComparison{}, err
	}
	return CIReportComparison{
		Name:               row.CaseName,
		Tags:               tags,
		Context:            contextTags,
		Info:               infoTags,
		Hardware:           Hardware{ID: row.HardwareID, Type: row.HardwareType, Name: row.HardwareName, Hash: row.HardwareHash},
		HistoryFingerprint: row.HistoryFingerprint,
		Unit:               row.Unit,
		LessIsBetter:       lessIsBetterPtr(row.Unit),
		Contender:          ciReportSideFromRow(row),
		Links: CIReportRowLinks{
			Result: ciReportResultLink(row.ResultID),
			Series: ciReportSeriesLink(row.HistoryFingerprint),
		},
	}, nil
}

func ciReportSideFromRow(row storage.CIReportResultRow) CIReportSide {
	svs, svsType, err := resultSVS(row.Unit, nonNullFloats(row.Data), row.Error != nil)
	if err != nil {
		svs = nil
		svsType = "n/a"
	}
	return CIReportSide{
		ResultID:        row.ResultID,
		RunID:           row.RunID,
		ResultTimestamp: row.ResultTimestamp,
		CommitSHA:       row.CommitSha,
		CommitTimestamp: row.CommitTimestamp,
		SVS:             svs,
		SVSType:         svsType,
	}
}

func ciReportBaselineSideFromRow(row storage.CIReportResultRow) CIReportBaselineSide {
	side := ciReportSideFromRow(row)
	return CIReportBaselineSide{
		ResultID:        side.ResultID,
		RunID:           side.RunID,
		ResultTimestamp: side.ResultTimestamp,
		CommitSHA:       side.CommitSHA,
		CommitTimestamp: side.CommitTimestamp,
		SVS:             side.SVS,
		SVSType:         side.SVSType,
	}
}

func ciReportComparisonStatus(lookback *LookbackAnalysis) string {
	switch {
	case lookback == nil:
		return CIReportRowStatusInsufficient
	case lookback.RegressionIndicated:
		return CIReportRowStatusRegressed
	case lookback.ImprovementIndicated:
		return CIReportRowStatusImproved
	default:
		return CIReportRowStatusStable
	}
}

func ciReportAnalysisFromCompare(analysis CompareAnalysis) *CIReportAnalysis {
	return &CIReportAnalysis{
		Pairwise:       analysis.Pairwise,
		LookbackZScore: analysis.LookbackZScore,
	}
}

func (r *CIReport) applyBaselineSelections(selections map[string]ciReportBaselineSelection) {
	for i := range r.Runs {
		selection := selections[r.Runs[i].RunID]
		if selection.baselineRunID != nil {
			r.Runs[i].BaselineRunID = selection.baselineRunID
		}
		if selection.commit != nil {
			r.Runs[i].BaselineCommit = ciReportCommitFromCommit(*selection.commit)
			r.Runs[i].CommitsSkipped = selection.commitsSkipped
		}
		if selection.baselineError != nil {
			r.Runs[i].BaselineError = selection.baselineError
			r.Summary.baselineErrors++
			if selection.baselineError.Code != CIReportBaselineErrorNoBaselineRun {
				r.Summary.baselineActionErr++
			}
		}
	}
}

func (r *CIReport) deriveSummaryFromComparisons() {
	for _, comp := range r.Comparisons {
		switch comp.Status {
		case CIReportRowStatusErrored:
			r.Summary.BenchmarkErrors++
		case CIReportRowStatusMissingBaseline:
			r.Summary.MissingBaseline++
		case CIReportRowStatusNotComparable:
			r.Summary.NotComparable++
		case CIReportRowStatusInsufficient:
			r.Summary.insufficient++
			r.Summary.Compared++
		case CIReportRowStatusRegressed:
			r.Summary.Regressions++
			r.Summary.Compared++
			r.Summary.Analyzed++
		case CIReportRowStatusImproved:
			r.Summary.Improvements++
			r.Summary.Compared++
			r.Summary.Analyzed++
		case CIReportRowStatusStable:
			r.Summary.stable++
			r.Summary.Compared++
			r.Summary.Analyzed++
		}
	}
}

func (r *CIReport) deriveStatus() CIReportStatus {
	if r.Summary.MissingRuns > 0 ||
		r.Summary.commitlessRuns > 0 ||
		r.Summary.ContenderResults == 0 ||
		r.Summary.BenchmarkErrors > 0 ||
		r.Summary.baselineActionErr > 0 {
		return CIReportStatusActionRequired
	}
	if r.Summary.Regressions > 0 {
		return CIReportStatusFailure
	}
	if r.Summary.Analyzed == 0 {
		return CIReportStatusSkipped
	}
	return CIReportStatusSuccess
}

func (r *CIReport) deriveStatusReason() string {
	switch r.Status {
	case CIReportStatusActionRequired:
		switch {
		case r.Summary.MissingRuns > 0:
			return "explicit run IDs were not found"
		case r.Summary.commitlessRuns > 0:
			return "selected runs are not connected to commit metadata"
		case r.Summary.ContenderResults == 0:
			return "selected runs contain no benchmark results"
		case r.Summary.BenchmarkErrors > 0:
			return "benchmark errors require inspection"
		case r.Summary.baselineActionErr > 0:
			return "baseline commit metadata is incomplete"
		default:
			return "action required"
		}
	case CIReportStatusFailure:
		return "lookback regression detected"
	case CIReportStatusSkipped:
		return "no row has enough baseline history for z-score analysis"
	default:
		return "no regressions"
	}
}

func (r *CIReport) applyCommitlessBaselineErrors(baseline CIReportBaseline) {
	for i := range r.Runs {
		r.Runs[i].BaselineError = &CIReportBaselineError{
			Code:     CIReportBaselineErrorMissingCommitMetadata,
			Message:  "selected run is not connected to commit metadata",
			RunID:    r.Runs[i].RunID,
			Baseline: baseline,
		}
		r.Summary.baselineErrors++
		r.Summary.baselineActionErr++
	}
}

func (r *CIReport) attachComparisonsToRuns() {
	byRun := map[string][]CIReportComparison{}
	for _, comp := range r.Comparisons {
		byRun[comp.Contender.RunID] = append(byRun[comp.Contender.RunID], comp)
	}
	for i := range r.Runs {
		r.Runs[i].Comparisons = byRun[r.Runs[i].RunID]
		if r.Runs[i].Comparisons == nil {
			r.Runs[i].Comparisons = []CIReportComparison{}
		}
	}
}

func ciReportCommitFromRun(row storage.CIReportRunRow) *Commit {
	if row.CommitID == nil {
		return nil
	}
	return &Commit{
		ID:         *row.CommitID,
		Sha:        derefString(row.CommitSha),
		Repository: derefString(row.CommitRepository),
		Timestamp:  row.CommitTimestamp,
	}
}

func ciReportCommitFromCommit(row storage.CIReportCommitRow) *Commit {
	return &Commit{
		ID:         row.CommitID,
		Sha:        row.CommitSha,
		Repository: row.Repository,
		Message:    row.Message,
		Timestamp:  row.Timestamp,
	}
}

func ciReportSelectedRunIDs(rows []storage.CIReportRunRow) []string {
	out := make([]string, 0, len(rows))
	seen := map[string]bool{}
	for _, row := range rows {
		if seen[row.RunID] {
			continue
		}
		seen[row.RunID] = true
		out = append(out, row.RunID)
	}
	return out
}

func ciReportRowsByRunID(rows []storage.CIReportResultRow) map[string][]storage.CIReportResultRow {
	out := map[string][]storage.CIReportResultRow{}
	for _, row := range rows {
		out[row.RunID] = append(out[row.RunID], row)
	}
	return out
}

func ciReportRunKeyString(runID, commitID string) string {
	return runID + "\x00" + commitID
}

func ciReportResultRunKey(row storage.CIReportResultRow) (string, bool) {
	if row.CommitID == nil {
		return "", false
	}
	return ciReportRunKeyString(row.RunID, *row.CommitID), true
}

func ciReportRunKeys(rows []storage.CIReportRunRow) []storage.CIReportRunKey {
	out := make([]storage.CIReportRunKey, 0, len(rows))
	seen := map[string]bool{}
	for _, row := range rows {
		if row.CommitID == nil {
			continue
		}
		key := storage.CIReportRunKey{RunID: row.RunID, CommitID: *row.CommitID}
		dedupe := ciReportRunKeyString(key.RunID, key.CommitID)
		if seen[dedupe] {
			continue
		}
		seen[dedupe] = true
		out = append(out, key)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].RunID != out[j].RunID {
			return out[i].RunID < out[j].RunID
		}
		return out[i].CommitID < out[j].CommitID
	})
	return out
}

func ciReportBaselineRunKeys(selections map[string]ciReportBaselineSelection) []storage.CIReportRunKey {
	seen := map[string]bool{}
	out := []storage.CIReportRunKey{}
	for _, selection := range selections {
		if selection.baselineRunID == nil || selection.baselineCommitID == "" {
			continue
		}
		key := storage.CIReportRunKey{RunID: *selection.baselineRunID, CommitID: selection.baselineCommitID}
		dedupe := ciReportRunKeyString(key.RunID, key.CommitID)
		if seen[dedupe] {
			continue
		}
		seen[dedupe] = true
		out = append(out, key)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].RunID != out[j].RunID {
			return out[i].RunID < out[j].RunID
		}
		return out[i].CommitID < out[j].CommitID
	})
	return out
}

func metaCommitID(row storage.CIReportRunRow) string {
	if row.CommitID == nil {
		return ""
	}
	return *row.CommitID
}

func ciReportSkippedCommits(ancestry []storage.CIReportCommitRow, selectedDepth int) []string {
	out := make([]string, 0, selectedDepth)
	for i := 0; i < selectedDepth && i < len(ancestry); i++ {
		out = append(out, ancestry[i].CommitSha)
	}
	return out
}

func ciReportCommitSHAs(commits []storage.CIReportCommitRow) []string {
	out := make([]string, len(commits))
	for i, commit := range commits {
		out[i] = commit.CommitSha
	}
	return out
}

func ciReportBaseline(b CIReportBaseline) CIReportBaseline {
	if b == "" {
		return CIReportBaselineForkPoint
	}
	return b
}

func validCIReportBaseline(b CIReportBaseline) bool {
	return b == CIReportBaselineForkPoint || b == CIReportBaselineParent || b == CIReportBaselineLatestDefault
}

func (r *CIReporter) ciReportURL(q CIReportQuery, repository string, commitSHA *string, baseline CIReportBaseline, threshold float64, thresholdZ float64) string {
	values := url.Values{}
	if repository != "" && commitSHA != nil {
		values.Set("repository", repository)
		values.Set("commit_sha", *commitSHA)
	}
	if len(q.RunIDs) > 0 {
		values.Set("run_ids", strings.Join(q.RunIDs, ","))
	}
	if len(q.BaselineRunIDs) > 0 {
		values.Set("baseline_run_ids", strings.Join(q.BaselineRunIDs, ","))
	}
	if q.Baseline != "" {
		values.Set("baseline", string(baseline))
	}
	setNonDefaultReportFloat(values, "threshold", threshold, stats.PairwisePercentThresholdDefault)
	setNonDefaultReportFloat(values, "threshold_z", thresholdZ, stats.ZScoreThresholdDefault)
	path := "/ci/report"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	baseURL := q.PublicBaseURL
	if baseURL == "" {
		baseURL = r.publicBaseURL
	}
	if baseURL == "" {
		return path
	}
	return strings.TrimRight(baseURL, "/") + path
}

func ciReportResultLink(resultID string) string {
	return "/results/" + url.PathEscape(resultID)
}

func ciReportCompareLink(baselineID, contenderID string, threshold float64, thresholdZ float64) string {
	values := url.Values{}
	values.Set("baseline", baselineID)
	values.Set("contender", contenderID)
	setNonDefaultReportFloat(values, "threshold", threshold, stats.PairwisePercentThresholdDefault)
	setNonDefaultReportFloat(values, "threshold_z", thresholdZ, stats.ZScoreThresholdDefault)
	return "/compare?" + values.Encode()
}

func ciReportSeriesLink(fingerprint string) string {
	return "/series/" + url.PathEscape(fingerprint)
}

func setNonDefaultReportFloat(values url.Values, key string, value float64, fallback float64) {
	if value == 0 || value == fallback {
		return
	}
	values.Set(key, strconv.FormatFloat(value, 'g', -1, 64))
}

func sameStringPtr(a, b *string) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func sameTimePtr(a, b *time.Time) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return a.Equal(*b)
}
