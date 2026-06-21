package prodclone

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"reflect"
	"slices"
	"strings"
	"time"

	conbenchclient "github.com/conbench/conbench/sdk/go/conbench"
)

type APIProbeConfig struct {
	ServerURL string
	Samples   SampleManifest
}

type CompatibilityProbeArtifact struct {
	ServerURL string                     `json:"server_url,omitempty"`
	Passed    bool                       `json:"passed"`
	Probes    []CompatibilityProbeResult `json:"probes"`
}

type CompatibilityProbeResult struct {
	Surface    string  `json:"surface"`
	Name       string  `json:"name"`
	Operation  string  `json:"operation"`
	Method     string  `json:"method,omitempty"`
	Path       string  `json:"path,omitempty"`
	StatusCode int     `json:"status_code,omitempty"`
	DurationMS float64 `json:"duration_ms,omitempty"`
	Passed     bool    `json:"passed"`
	Error      string  `json:"error,omitempty"`
}

type HTTPProbeTiming struct {
	Surface    string  `json:"surface"`
	Name       string  `json:"name"`
	Operation  string  `json:"operation"`
	Method     string  `json:"method"`
	Path       string  `json:"path"`
	StatusCode int     `json:"status_code,omitempty"`
	DurationMS float64 `json:"duration_ms"`
	Passed     bool    `json:"passed"`
	Error      string  `json:"error,omitempty"`
}

type apiProbeCall struct {
	name      string
	operation string
	method    string
	path      string
	call      func(context.Context) (int, bool, error)
}

func RunAPIProbes(ctx context.Context, cfg APIProbeConfig) (CompatibilityProbeArtifact, []HTTPProbeTiming, error) {
	artifact := CompatibilityProbeArtifact{ServerURL: cfg.ServerURL, Passed: true}

	client, err := conbenchclient.NewClientWithResponses(cfg.ServerURL)
	if err != nil {
		artifact.Passed = false
		artifact.Probes = append(artifact.Probes, CompatibilityProbeResult{
			Surface:   "API",
			Name:      "CreateGeneratedClient",
			Operation: "NewClientWithResponses",
			Passed:    false,
			Error:     err.Error(),
		})
		return artifact, nil, fmt.Errorf("create generated client: %w", err)
	}

	resultID, historyFingerprint, sampleErr := selectReadProbeSample(cfg.Samples)
	calls := []apiProbeCall{
		{
			name:      "ListSeries",
			operation: "GET /api/series",
			method:    http.MethodGet,
			path:      "/api/series",
			call: func(ctx context.Context) (int, bool, error) {
				pageSize := int64(5)
				resp, err := client.ListSeriesWithResponse(ctx, &conbenchclient.ListSeriesParams{PageSize: &pageSize})
				if err != nil {
					return responseStatus(resp), false, fmt.Errorf("decode response: %w", err)
				}
				if resp.JSON200 == nil {
					return resp.StatusCode(), false, nil
				}
				return resp.StatusCode(), true, validateSeriesPage(resp.JSON200, resp.Body)
			},
		},
		{
			name:      "ListBenchmarkResults",
			operation: "GET /api/benchmark-results",
			method:    http.MethodGet,
			path:      "/api/benchmark-results",
			call: func(ctx context.Context) (int, bool, error) {
				pageSize := int64(5)
				resp, err := client.ListBenchmarkResultsWithResponse(ctx, &conbenchclient.ListBenchmarkResultsParams{PageSize: &pageSize})
				if err != nil {
					return responseStatus(resp), false, fmt.Errorf("decode response: %w", err)
				}
				if resp.JSON200 == nil {
					return resp.StatusCode(), false, nil
				}
				return resp.StatusCode(), true, validateResultPage(resp.JSON200, resp.Body)
			},
		},
	}

	if sampleErr == nil {
		calls = append(calls,
			apiProbeCall{
				name:      "GetBenchmarkResult",
				operation: "GET /api/benchmark-results/{id}",
				method:    http.MethodGet,
				path:      "/api/benchmark-results/" + resultID,
				call: func(ctx context.Context) (int, bool, error) {
					resp, err := client.GetBenchmarkResultWithResponse(ctx, resultID)
					if err != nil {
						return responseStatus(resp), false, fmt.Errorf("decode response: %w", err)
					}
					if resp.JSON200 == nil {
						return resp.StatusCode(), false, nil
					}
					return resp.StatusCode(), true, validateResultDetail(resp.JSON200, resp.Body, resultID, historyFingerprint)
				},
			},
			apiProbeCall{
				name:      "GetHistoryForResult",
				operation: "GET /api/history/{benchmark_result_id}",
				method:    http.MethodGet,
				path:      "/api/history/" + resultID,
				call: func(ctx context.Context) (int, bool, error) {
					resp, err := client.GetHistoryForResultWithResponse(ctx, resultID)
					if err != nil {
						return responseStatus(resp), false, fmt.Errorf("decode response: %w", err)
					}
					if resp.JSON200 == nil {
						return resp.StatusCode(), false, nil
					}
					return resp.StatusCode(), true, validateHistorySeries(resp.JSON200, resp.Body, historyFingerprint)
				},
			},
			apiProbeCall{
				name:      "GetHistory",
				operation: "GET /api/history?fingerprint=...",
				method:    http.MethodGet,
				path:      "/api/history",
				call: func(ctx context.Context) (int, bool, error) {
					resp, err := client.GetHistoryWithResponse(ctx, &conbenchclient.GetHistoryParams{Fingerprint: historyFingerprint})
					if err != nil {
						return responseStatus(resp), false, fmt.Errorf("decode response: %w", err)
					}
					if resp.JSON200 == nil {
						return resp.StatusCode(), false, nil
					}
					return resp.StatusCode(), true, validateHistorySeries(resp.JSON200, resp.Body, historyFingerprint)
				},
			},
		)
	} else {
		calls = append(calls, missingSampleProbeFailures(sampleErr)...)
	}

	if cfg.Samples.Compare != nil {
		compare := cfg.Samples.Compare
		calls = append(calls, apiProbeCall{
			name:      "CompareBenchmarkResults",
			operation: "GET /api/compare/benchmark-results",
			method:    http.MethodGet,
			path:      "/api/compare/benchmark-results",
			call: func(ctx context.Context) (int, bool, error) {
				resp, err := client.CompareBenchmarkResultsWithResponse(ctx, &conbenchclient.CompareBenchmarkResultsParams{
					BaselineResultId:  compare.BaselineResultID,
					ContenderResultId: compare.ContenderResultID,
				})
				if err != nil {
					return responseStatus(resp), false, fmt.Errorf("decode response: %w", err)
				}
				if resp.JSON200 == nil {
					return resp.StatusCode(), false, nil
				}
				return resp.StatusCode(), true, validateCompareResult(resp.JSON200, resp.Body, compare.BaselineResultID, compare.ContenderResultID)
			},
		})
	}
	if cfg.Samples.CIReport != nil {
		sample := cfg.Samples.CIReport
		runIDs := strings.Join(sample.RunIDs, ",")
		calls = append(calls, apiProbeCall{
			name:      "CIReportByCommitRun",
			operation: "GET /api/ci/report",
			method:    http.MethodGet,
			path:      "/api/ci/report",
			call: func(ctx context.Context) (int, bool, error) {
				resp, err := client.GetCiReportWithResponse(ctx, &conbenchclient.GetCiReportParams{
					Repository: &sample.Repository,
					CommitSha:  &sample.CommitSHA,
					RunIds:     &runIDs,
				})
				if err != nil {
					return responseStatus(resp), false, fmt.Errorf("decode response: %w", err)
				}
				if resp.JSON200 == nil {
					return resp.StatusCode(), false, nil
				}
				return resp.StatusCode(), true, validateCIReport(resp.JSON200, resp.Body, *sample)
			},
		})
	}

	timings := make([]HTTPProbeTiming, 0, len(calls))
	var failures int
	for _, call := range calls {
		result, timing := runOneAPIProbe(ctx, call)
		artifact.Probes = append(artifact.Probes, result)
		timings = append(timings, timing)
		if !result.Passed {
			failures++
		}
	}
	if failures > 0 {
		artifact.Passed = false
		return artifact, timings, fmt.Errorf("%d API probe %s failed", failures, plural(failures, "check", "checks"))
	}
	return artifact, timings, nil
}

func validateSeriesPage(page *conbenchclient.SeriesPage, body []byte) error {
	if page.Series == nil {
		return fmt.Errorf("invalid response: missing series array")
	}
	if len(*page.Series) == 0 {
		return fmt.Errorf("invalid response: series array is empty")
	}
	if _, err := requireArrayObjectFields(body, "SeriesPage", "series",
		"history_fingerprint",
		"context",
		"hardware",
		"latest_commit_sha",
		"latest_commit_timestamp",
		"latest_result_id",
		"latest_result_timestamp",
		"latest_single_value_summary",
		"latest_single_value_summary_type",
		"less_is_better",
		"name",
		"point_count",
		"repository",
		"sparkline",
		"status",
		"tags",
		"unit",
	); err != nil {
		return err
	}
	for i, item := range *page.Series {
		if err := validateSeriesListItem(item, i); err != nil {
			return err
		}
	}
	return nil
}

func validateResultPage(page *conbenchclient.ResultPage, body []byte) error {
	if page.Results == nil {
		return fmt.Errorf("invalid response: missing results array")
	}
	if len(*page.Results) == 0 {
		return fmt.Errorf("invalid response: results array is empty")
	}
	if _, err := requireArrayObjectFields(body, "ResultPage", "results",
		"id",
		"run_id",
		"history_fingerprint",
		"commit",
		"has_error",
		"run_tags",
		"single_value_summary",
		"single_value_summary_type",
		"timestamp",
		"unit",
	); err != nil {
		return err
	}
	for i, item := range *page.Results {
		if err := validateResultListItem(item, i); err != nil {
			return err
		}
	}
	return nil
}

func validateSeriesListItem(item conbenchclient.SeriesListItem, index int) error {
	prefix := fmt.Sprintf("series[%d]", index)
	if item.HistoryFingerprint == "" {
		return fmt.Errorf("invalid response: missing required field %s.history_fingerprint", prefix)
	}
	if item.Name == "" {
		return fmt.Errorf("invalid response: missing required field %s.name", prefix)
	}
	if item.Context == nil {
		return fmt.Errorf("invalid response: missing required field %s.context", prefix)
	}
	if item.Tags == nil {
		return fmt.Errorf("invalid response: missing required field %s.tags", prefix)
	}
	if err := validateHardware(item.Hardware, prefix+".hardware"); err != nil {
		return err
	}
	if item.Repository == "" {
		return fmt.Errorf("invalid response: missing required field %s.repository", prefix)
	}
	if item.LatestResultId == "" {
		return fmt.Errorf("invalid response: missing required field %s.latest_result_id", prefix)
	}
	if item.LatestCommitSha == "" {
		return fmt.Errorf("invalid response: missing required field %s.latest_commit_sha", prefix)
	}
	if item.LatestCommitTimestamp.IsZero() {
		return fmt.Errorf("invalid response: missing required field %s.latest_commit_timestamp", prefix)
	}
	if item.LatestResultTimestamp.IsZero() {
		return fmt.Errorf("invalid response: missing required field %s.latest_result_timestamp", prefix)
	}
	if item.PointCount <= 0 {
		return fmt.Errorf("invalid response: missing required field %s.point_count", prefix)
	}
	if !item.Status.Valid() {
		return fmt.Errorf("invalid response: missing required field %s.status", prefix)
	}
	return nil
}

func validateResultListItem(item conbenchclient.ResultListItem, index int) error {
	prefix := fmt.Sprintf("results[%d]", index)
	if item.Id == "" {
		return fmt.Errorf("invalid response: missing required field %s.id", prefix)
	}
	if item.RunId == "" {
		return fmt.Errorf("invalid response: missing required field %s.run_id", prefix)
	}
	if item.RunTags == nil {
		return fmt.Errorf("invalid response: missing required field %s.run_tags", prefix)
	}
	if item.Timestamp.IsZero() {
		return fmt.Errorf("invalid response: missing required field %s.timestamp", prefix)
	}
	if item.SingleValueSummaryType == "" {
		return fmt.Errorf("invalid response: missing required field %s.single_value_summary_type", prefix)
	}
	if item.HistoryFingerprint == "" {
		return fmt.Errorf("invalid response: missing required field %s.history_fingerprint", prefix)
	}
	return nil
}

func validateResultDetail(result *conbenchclient.ResultDetail, body []byte, resultID string, historyFingerprint string) error {
	fields, err := requireJSONObjectFields(body, "ResultDetail",
		"run_id",
		"timestamp",
		"hardware",
		"stats",
		"tags",
		"context",
		"info",
		"run_tags",
		"single_value_summary_type",
		"batch_id",
		"change_annotations",
		"commit",
		"commit_repo_url",
		"data",
		"error",
		"iterations",
		"less_is_better",
		"optional_benchmark_info",
		"run_reason",
		"single_value_summary",
		"time_unit",
		"times",
		"unit",
		"validation",
	)
	if err != nil {
		return err
	}
	for _, field := range []string{"hardware", "stats", "tags", "context", "info", "run_tags", "change_annotations"} {
		if err := requireJSONObjectField(fields, field); err != nil {
			return err
		}
	}

	if result.Id != resultID {
		return fmt.Errorf("invalid response: expected result id %q, got %q", resultID, result.Id)
	}
	if result.HistoryFingerprint != historyFingerprint {
		return fmt.Errorf("invalid response: expected history_fingerprint %q, got %q", historyFingerprint, result.HistoryFingerprint)
	}
	if result.RunId == "" {
		return fmt.Errorf("invalid response: missing required field run_id")
	}
	if result.Timestamp.IsZero() {
		return fmt.Errorf("invalid response: missing required field timestamp")
	}
	if err := validateHardware(result.Hardware, "hardware"); err != nil {
		return err
	}
	if result.SingleValueSummaryType == "" {
		return fmt.Errorf("invalid response: missing required field single_value_summary_type")
	}
	return nil
}

func validateHistorySeries(series *conbenchclient.HistorySeries, body []byte, historyFingerprint string) error {
	if series.HistoryFingerprint != historyFingerprint {
		return fmt.Errorf("invalid response: expected history_fingerprint %q, got %q", historyFingerprint, series.HistoryFingerprint)
	}
	if series.Samples == nil {
		return fmt.Errorf("invalid response: missing samples array")
	}
	if len(*series.Samples) == 0 {
		return fmt.Errorf("invalid response: samples array is empty")
	}
	if _, err := requireArrayObjectFields(body, "HistorySeries", "samples",
		"benchmark_result_id",
		"commit_hash",
		"commit_message",
		"commit_repository",
		"commit_timestamp",
		"hardware_hash",
		"mean",
		"result_timestamp",
		"single_value_summary",
		"single_value_summary_type",
		"unit",
		"zscorestats",
	); err != nil {
		return err
	}
	for i, sample := range *series.Samples {
		if err := validateHistorySample(sample, i); err != nil {
			return err
		}
	}
	return nil
}

func validateHistorySample(sample conbenchclient.HistorySample, index int) error {
	prefix := fmt.Sprintf("samples[%d]", index)
	if sample.BenchmarkResultId == "" {
		return fmt.Errorf("invalid response: missing required field %s.benchmark_result_id", prefix)
	}
	if sample.CommitHash == "" {
		return fmt.Errorf("invalid response: missing required field %s.commit_hash", prefix)
	}
	if sample.CommitRepository == "" {
		return fmt.Errorf("invalid response: missing required field %s.commit_repository", prefix)
	}
	if sample.HardwareHash == "" {
		return fmt.Errorf("invalid response: missing required field %s.hardware_hash", prefix)
	}
	if sample.ResultTimestamp.IsZero() {
		return fmt.Errorf("invalid response: missing required field %s.result_timestamp", prefix)
	}
	if sample.SingleValueSummaryType == "" {
		return fmt.Errorf("invalid response: missing required field %s.single_value_summary_type", prefix)
	}
	return nil
}

func validateHardware(hardware conbenchclient.Hardware, prefix string) error {
	if hardware.Id == "" {
		return fmt.Errorf("invalid response: missing required field %s.id", prefix)
	}
	if hardware.Hash == "" {
		return fmt.Errorf("invalid response: missing required field %s.hash", prefix)
	}
	if hardware.Name == "" {
		return fmt.Errorf("invalid response: missing required field %s.name", prefix)
	}
	if hardware.Type == "" {
		return fmt.Errorf("invalid response: missing required field %s.type", prefix)
	}
	return nil
}

func validateCompareResult(result *conbenchclient.CompareResult, body []byte, baselineResultID string, contenderResultID string) error {
	fields, err := requireJSONObjectFields(body, "CompareResult", "baseline", "contender")
	if err != nil {
		return err
	}
	if err := requireCompareSideFields(fields, "baseline"); err != nil {
		return err
	}
	if err := requireCompareSideFields(fields, "contender"); err != nil {
		return err
	}
	if err := requireJSONFields(fields, "unit", "less_is_better", "analysis"); err != nil {
		return err
	}
	if err := requireAnalysisFields(fields); err != nil {
		return err
	}

	if result.Baseline.BenchmarkResultId != baselineResultID {
		return fmt.Errorf("invalid response: expected baseline_result_id %q, got %q", baselineResultID, result.Baseline.BenchmarkResultId)
	}
	if result.Contender.BenchmarkResultId != contenderResultID {
		return fmt.Errorf("invalid response: expected contender_result_id %q, got %q", contenderResultID, result.Contender.BenchmarkResultId)
	}
	if result.Baseline.RunId == "" {
		return fmt.Errorf("invalid response: missing required field baseline.run_id")
	}
	if result.Contender.RunId == "" {
		return fmt.Errorf("invalid response: missing required field contender.run_id")
	}
	if result.Unit == "" {
		return fmt.Errorf("invalid response: missing required field unit")
	}
	return nil
}

func validateCIReport(report *conbenchclient.CIReport, body []byte, sample CIReportSample) error {
	if report == nil {
		return fmt.Errorf("invalid response: missing CI report")
	}
	fields, err := requireJSONObjectFields(body, "CIReport",
		"repository",
		"commit_sha",
		"selected_run_ids",
		"summary",
		"runs",
		"report_url",
	)
	if err != nil {
		return err
	}
	if report.Repository != sample.Repository {
		return fmt.Errorf("invalid response: expected repository %q, got %q", sample.Repository, report.Repository)
	}
	if report.CommitSha == nil || *report.CommitSha != sample.CommitSHA {
		got := ""
		if report.CommitSha != nil {
			got = *report.CommitSha
		}
		return fmt.Errorf("invalid response: expected commit_sha %q, got %q", sample.CommitSHA, got)
	}
	if report.SelectedRunIds == nil {
		return fmt.Errorf("invalid response: missing selected_run_ids array")
	}
	for _, runID := range sample.RunIDs {
		if !stringSliceContains(*report.SelectedRunIds, runID) {
			return fmt.Errorf("invalid response: selected_run_ids missing %q", runID)
		}
	}
	if report.Runs == nil {
		return fmt.Errorf("invalid response: missing runs array")
	}
	if report.ReportUrl == "" {
		return fmt.Errorf("invalid response: missing required field report_url")
	}
	if err := requireJSONObjectField(fields, "summary"); err != nil {
		return err
	}
	if err := validateCIReportSummary(report.Summary); err != nil {
		return err
	}
	for i, run := range *report.Runs {
		if err := validateCIReportRun(run, i); err != nil {
			return err
		}
	}
	return nil
}

func validateCIReportSummary(summary conbenchclient.CIReportSummary) error {
	counters := map[string]int64{
		"analyzed":          summary.Analyzed,
		"benchmark_errors":  summary.BenchmarkErrors,
		"compared":          summary.Compared,
		"contender_results": summary.ContenderResults,
		"improvements":      summary.Improvements,
		"missing_baseline":  summary.MissingBaseline,
		"missing_runs":      summary.MissingRuns,
		"not_comparable":    summary.NotComparable,
		"regressions":       summary.Regressions,
		"runs":              summary.Runs,
	}
	for name, value := range counters {
		if value < 0 {
			return fmt.Errorf("invalid response: summary.%s is negative", name)
		}
	}
	return nil
}

func validateCIReportRun(run conbenchclient.CIReportRun, index int) error {
	prefix := fmt.Sprintf("runs[%d]", index)
	if run.RunId == "" {
		return fmt.Errorf("invalid response: missing required field %s.run_id", prefix)
	}
	if run.RunTags == nil {
		return fmt.Errorf("invalid response: missing required field %s.run_tags", prefix)
	}
	if run.Comparisons == nil {
		return nil
	}
	for i, comparison := range *run.Comparisons {
		if err := validateCIReportComparison(comparison, fmt.Sprintf("%s.comparisons[%d]", prefix, i)); err != nil {
			return err
		}
	}
	return nil
}

func validateCIReportComparison(comparison conbenchclient.CIReportComparison, prefix string) error {
	if comparison.HistoryFingerprint == "" {
		return fmt.Errorf("invalid response: missing required field %s.history_fingerprint", prefix)
	}
	if !comparison.Status.Valid() {
		return fmt.Errorf("invalid response: missing required field %s.status", prefix)
	}
	if comparison.Contender.ResultId == "" {
		return fmt.Errorf("invalid response: missing required field %s.contender.result_id", prefix)
	}
	if comparison.Contender.RunId == "" {
		return fmt.Errorf("invalid response: missing required field %s.contender.run_id", prefix)
	}
	if comparison.Links.Result == "" {
		return fmt.Errorf("invalid response: missing required field %s.links.result", prefix)
	}
	if comparison.Links.Series == "" {
		return fmt.Errorf("invalid response: missing required field %s.links.series", prefix)
	}
	return nil
}

func requireCompareSideFields(fields map[string]json.RawMessage, name string) error {
	sideFields, err := requireNestedJSONObjectFields(fields, name, "benchmark_result_id", "run_id", "single_value_summary")
	if err != nil {
		return err
	}
	if err := requireNonNullJSONField(sideFields, "benchmark_result_id", name+".benchmark_result_id"); err != nil {
		return err
	}
	if err := requireNonNullJSONField(sideFields, "run_id", name+".run_id"); err != nil {
		return err
	}
	return requireNonNullJSONField(sideFields, "single_value_summary", name+".single_value_summary")
}

func stringSliceContains(values []string, target string) bool {
	return slices.Contains(values, target)
}

func requireAnalysisFields(fields map[string]json.RawMessage) error {
	_, err := requireNestedJSONObjectFields(fields, "analysis", "pairwise", "lookback_z_score")
	return err
}

func requireJSONObjectFields(body []byte, model string, fields ...string) (map[string]json.RawMessage, error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(body, &object); err != nil {
		return nil, fmt.Errorf("invalid response: decode %s object: %w", model, err)
	}
	if object == nil {
		return nil, fmt.Errorf("invalid response: %s body is not an object", model)
	}
	if err := requireJSONFields(object, fields...); err != nil {
		return nil, err
	}
	return object, nil
}

func requireJSONFields(object map[string]json.RawMessage, fields ...string) error {
	for _, field := range fields {
		if _, ok := object[field]; !ok {
			return fmt.Errorf("invalid response: missing required field %s", field)
		}
	}
	return nil
}

func requireArrayObjectFields(body []byte, model string, arrayName string, fields ...string) ([]map[string]json.RawMessage, error) {
	object, err := requireJSONObjectFields(body, model, arrayName)
	if err != nil {
		return nil, err
	}
	var rawItems []json.RawMessage
	if err := json.Unmarshal(object[arrayName], &rawItems); err != nil {
		return nil, fmt.Errorf("invalid response: %s must be an array", arrayName)
	}
	items := make([]map[string]json.RawMessage, 0, len(rawItems))
	for i, raw := range rawItems {
		var item map[string]json.RawMessage
		if err := json.Unmarshal(raw, &item); err != nil {
			return nil, fmt.Errorf("invalid response: %s[%d] must be an object", arrayName, i)
		}
		if item == nil {
			return nil, fmt.Errorf("invalid response: %s[%d] must be an object", arrayName, i)
		}
		for _, field := range fields {
			if _, ok := item[field]; !ok {
				return nil, fmt.Errorf("invalid response: missing required field %s[%d].%s", arrayName, i, field)
			}
		}
		items = append(items, item)
	}
	return items, nil
}

func requireNestedJSONObjectFields(parent map[string]json.RawMessage, name string, fields ...string) (map[string]json.RawMessage, error) {
	raw, ok := parent[name]
	if !ok {
		return nil, fmt.Errorf("invalid response: missing required field %s", name)
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil {
		return nil, fmt.Errorf("invalid response: %s must be an object", name)
	}
	if object == nil {
		return nil, fmt.Errorf("invalid response: %s must be an object", name)
	}
	for _, field := range fields {
		qualified := name + "." + field
		if _, ok := object[field]; !ok {
			return nil, fmt.Errorf("invalid response: missing required field %s", qualified)
		}
	}
	return object, nil
}

func requireJSONObjectField(fields map[string]json.RawMessage, name string) error {
	raw, ok := fields[name]
	if !ok {
		return fmt.Errorf("invalid response: missing required field %s", name)
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil {
		return fmt.Errorf("invalid response: %s must be an object", name)
	}
	if object == nil {
		return fmt.Errorf("invalid response: %s must be an object", name)
	}
	return nil
}

func requireNonNullJSONField(fields map[string]json.RawMessage, field string, qualified string) error {
	raw, ok := fields[field]
	if !ok {
		return fmt.Errorf("invalid response: missing required field %s", qualified)
	}
	if strings.TrimSpace(string(raw)) == "null" {
		return fmt.Errorf("invalid response: missing required field %s", qualified)
	}
	return nil
}

func runOneAPIProbe(ctx context.Context, call apiProbeCall) (CompatibilityProbeResult, HTTPProbeTiming) {
	start := time.Now()
	statusCode, decoded, err := call.call(ctx)
	durationMS := float64(time.Since(start).Microseconds()) / 1000

	result := CompatibilityProbeResult{
		Surface:    "API",
		Name:       call.name,
		Operation:  call.operation,
		Method:     call.method,
		Path:       call.path,
		StatusCode: statusCode,
		DurationMS: durationMS,
		Passed:     true,
	}
	if err != nil {
		result.Passed = false
		result.Error = err.Error()
	} else if statusCode != http.StatusOK {
		result.Passed = false
		result.Error = fmt.Sprintf("expected HTTP 200, got %d", statusCode)
	} else if !decoded {
		result.Passed = false
		result.Error = "decode response: missing JSON200 body"
	}

	timing := HTTPProbeTiming(result)
	return result, timing
}

func selectReadProbeSample(samples SampleManifest) (string, string, error) {
	preferred := []string{sampleCategoryLongHistory, sampleCategoryShortHistory, sampleCategoryHistoryMember, sampleCategoryRecentResult}
	for _, name := range preferred {
		category, ok := samples.Categories[name]
		if ok && category.ResultID != "" && category.HistoryFingerprint != "" {
			return category.ResultID, category.HistoryFingerprint, nil
		}
	}
	for _, category := range samples.Categories {
		if category.ResultID != "" && category.HistoryFingerprint != "" {
			return category.ResultID, category.HistoryFingerprint, nil
		}
	}
	return "", "", fmt.Errorf("sample manifest must include a result_id and history_fingerprint")
}

func missingSampleProbeFailures(err error) []apiProbeCall {
	failure := func(name string, operation string, path string) apiProbeCall {
		return apiProbeCall{
			name:      name,
			operation: operation,
			method:    http.MethodGet,
			path:      path,
			call: func(context.Context) (int, bool, error) {
				return 0, false, err
			},
		}
	}
	return []apiProbeCall{
		failure("GetBenchmarkResult", "GET /api/benchmark-results/{id}", "/api/benchmark-results/{id}"),
		failure("GetHistoryForResult", "GET /api/history/{benchmark_result_id}", "/api/history/{benchmark_result_id}"),
		failure("GetHistory", "GET /api/history?fingerprint=...", "/api/history"),
	}
}

type statusCoder interface {
	StatusCode() int
}

func responseStatus(response any) int {
	if response == nil {
		return 0
	}
	value := reflect.ValueOf(response)
	if value.Kind() == reflect.Pointer && value.IsNil() {
		return 0
	}
	coder, ok := response.(statusCoder)
	if !ok {
		return 0
	}
	return coder.StatusCode()
}
