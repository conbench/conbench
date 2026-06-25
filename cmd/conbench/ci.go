package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/conbench/conbench/internal/githubapi"
	"github.com/conbench/conbench/sdk/go/conbench"
	"github.com/spf13/cobra"
)

type ciReportConfig struct {
	server              string
	token               string
	repository          string
	commit              string
	runIDs              string
	baselineRunIDs      string
	baseline            string
	threshold           string
	thresholdSet        bool
	thresholdZ          string
	thresholdZSet       bool
	format              string
	output              string
	githubCheck         bool
	githubPRComment     bool
	githubToken         string
	githubAppID         string
	githubAppPrivateKey string
	githubAPIURL        string
	githubPRNumber      string
	githubExternalID    string
	buildURL            string
	githubCheckName     string
}

type codedError struct {
	err  error
	code int
}

func (e codedError) Error() string {
	return e.err.Error()
}

func (e codedError) Unwrap() error {
	return e.err
}

func (e codedError) ExitCode() int {
	return e.code
}

type ciReportStatusError struct {
	status conbench.CIReportStatus
}

func (e ciReportStatusError) Error() string {
	return "ci report status " + string(e.status)
}

func (ciReportStatusError) SuppressDiagnostic() {}

func (ciReportStatusError) ExitCode() int {
	return 1
}

func ciReportCommand(stdout io.Writer) *cobra.Command {
	return newCIReportCommand(stdout, runCIReportConfig)
}

func newCIReportCommand(
	stdout io.Writer,
	run func(context.Context, ciReportConfig, io.Writer) error,
) *cobra.Command {
	var cfg ciReportConfig
	cfg.format = "json"
	cmd := configureCommand(&cobra.Command{
		Use:   "report",
		Short: "Generate a CI benchmark report.",
		Args: func(cmd *cobra.Command, args []string) error {
			cfg.thresholdSet = cmd.Flags().Changed("threshold")
			cfg.thresholdZSet = cmd.Flags().Changed("threshold-z")

			switch {
			case len(args) > 0:
				return commandUsageError(cmd, "ci report does not accept positional arguments")
			case cfg.server == "":
				return commandUsageError(cmd, "--server is required")
			case (cfg.repository == "") != (cfg.commit == ""):
				return commandUsageError(cmd, "--repository and --commit must be provided together")
			case cfg.repository == "" && cfg.runIDs == "":
				return commandUsageError(cmd, "provide --repository and --commit, --run-ids, or both")
			case cfg.baselineRunIDs != "" && cfg.runIDs == "":
				return commandUsageError(cmd, "--baseline-run-ids requires --run-ids")
			case cfg.baselineRunIDs != "" && cfg.baseline != "":
				return commandUsageError(cmd, "--baseline cannot be used with --baseline-run-ids")
			case cfg.baselineRunIDs != "" && len(commaIDs(cfg.baselineRunIDs)) != len(commaIDs(cfg.runIDs)):
				return commandUsageError(cmd, "--baseline-run-ids must match --run-ids count")
			case cfg.baseline != "" && !validCIReportBaselineFlag(cfg.baseline):
				return commandUsageError(cmd, "invalid --baseline %q", cfg.baseline)
			case cfg.format != "json" && cfg.format != "markdown":
				return commandUsageError(cmd, "invalid --format %q", cfg.format)
			case (cfg.githubCheck || cfg.githubPRComment) && (cfg.repository == "" || cfg.commit == ""):
				return commandUsageError(cmd, "github publishing requires --repository and --commit")
			}
			if cfg.githubPRNumber != "" {
				if _, err := parsePositiveIntFlag(cfg.githubPRNumber, "--github-pr-number"); err != nil {
					return commandUsageError(cmd, "%s", err)
				}
			}
			if cfg.thresholdSet {
				if err := validatePositiveFloatFlag(cfg.threshold, "--threshold"); err != nil {
					return commandUsageError(cmd, "%s", err)
				}
			}
			if cfg.thresholdZSet {
				if err := validatePositiveFloatFlag(cfg.thresholdZ, "--threshold-z"); err != nil {
					return commandUsageError(cmd, "%s", err)
				}
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout)
		},
	})
	cmd.Flags().StringVar(&cfg.server, "server", "", "Conbench server base URL (required)")
	cmd.Flags().StringVar(&cfg.token, "token", "", "bearer token for read authentication")
	cmd.Flags().StringVar(&cfg.repository, "repository", "", "repository URL")
	cmd.Flags().StringVar(&cfg.commit, "commit", "", "commit SHA")
	cmd.Flags().StringVar(&cfg.runIDs, "run-ids", "", "comma-separated run IDs")
	cmd.Flags().StringVar(&cfg.baselineRunIDs, "baseline-run-ids", "", "comma-separated explicit baseline run IDs")
	cmd.Flags().StringVar(&cfg.baseline, "baseline", "", "baseline selector: fork_point, parent, or latest_default")
	cmd.Flags().StringVar(&cfg.threshold, "threshold", "", "pairwise percent-change threshold")
	cmd.Flags().StringVar(&cfg.thresholdZ, "threshold-z", "", "lookback z-score threshold")
	cmd.Flags().StringVar(&cfg.format, "format", "json", "output format: json or markdown")
	cmd.Flags().StringVar(&cfg.output, "output", "", "write rendered report to this path")
	cmd.Flags().BoolVar(&cfg.githubCheck, "github-check", false, "create a GitHub Check Run for the report")
	cmd.Flags().BoolVar(&cfg.githubPRComment, "github-pr-comment", false, "post a pull request comment linking to the GitHub Check")
	cmd.Flags().StringVar(&cfg.githubToken, "github-token", "", "GitHub token for report publishing")
	cmd.Flags().StringVar(&cfg.githubAppID, "github-app-id", "", "GitHub App ID for report publishing")
	cmd.Flags().StringVar(&cfg.githubAppPrivateKey, "github-app-private-key", "", "GitHub App private key contents for report publishing")
	cmd.Flags().StringVar(&cfg.githubAPIURL, "github-api-url", "", "GitHub API base URL for report publishing")
	cmd.Flags().StringVar(&cfg.githubPRNumber, "github-pr-number", "", "pull request number for --github-pr-comment")
	cmd.Flags().StringVar(&cfg.githubExternalID, "github-external-id", "", "external identifier for the GitHub Check Run")
	cmd.Flags().StringVar(&cfg.buildURL, "build-url", "", "CI build URL to include in the GitHub report")
	cmd.Flags().StringVar(&cfg.githubCheckName, "github-check-name", "", "GitHub Check Run name")
	return cmd
}

func parseCIReportArgs(args []string) (ciReportConfig, error) {
	var cfg ciReportConfig
	cmd := newCIReportCommand(io.Discard, func(_ context.Context, parsed ciReportConfig, _ io.Writer) error {
		cfg = parsed
		return nil
	})
	if err := executeParseCommand(cmd, args); err != nil {
		return ciReportConfig{}, err
	}
	return cfg, nil
}

func runCIReportConfig(ctx context.Context, cfg ciReportConfig, stdout io.Writer) error {
	bearer, err := resolveBearer(cfg.token, cfg.server)
	if err != nil {
		return codedError{err: err, code: 2}
	}
	client, err := newClient(cfg.server)
	if err != nil {
		return codedError{err: err, code: 2}
	}

	params := conbench.GetCiReportParams{
		Repository:     optionalString(cfg.repository),
		CommitSha:      optionalString(cfg.commit),
		RunIds:         optionalString(cfg.runIDs),
		BaselineRunIds: optionalString(cfg.baselineRunIDs),
	}
	if cfg.baseline != "" {
		baseline := conbench.GetCiReportParamsBaseline(cfg.baseline)
		params.Baseline = &baseline
	}
	if cfg.thresholdSet {
		threshold, err := positiveFloatFlagValue(cfg.threshold, "--threshold")
		if err != nil {
			return codedError{err: err, code: 2}
		}
		params.Threshold = &threshold
	}
	if cfg.thresholdZSet {
		thresholdZ, err := positiveFloatFlagValue(cfg.thresholdZ, "--threshold-z")
		if err != nil {
			return codedError{err: err, code: 2}
		}
		params.ThresholdZ = &thresholdZ
	}

	resp, err := client.GetCiReportWithResponse(ctx, &params, bearerRequestEditor(bearer))
	if err != nil {
		return codedError{err: fmt.Errorf("get ci report from %s: %w", cfg.server, err), code: 2}
	}
	if resp.JSON200 == nil {
		return codedError{err: statusError(resp.HTTPResponse, resp.Body), code: 2}
	}
	if err := writeCIReport(cfg, stdout, resp.JSON200); err != nil {
		return codedError{err: err, code: 2}
	}
	if cfg.githubCheck || cfg.githubPRComment {
		if err := publishCIReportGitHub(ctx, cfg, resp.JSON200); err != nil {
			return codedError{err: err, code: 2}
		}
	}
	if resp.JSON200.Status == conbench.CIReportStatusFailure || resp.JSON200.Status == conbench.CIReportStatusActionRequired {
		return ciReportStatusError{status: resp.JSON200.Status}
	}
	return nil
}

func writeCIReport(cfg ciReportConfig, stdout io.Writer, report *conbench.CIReport) error {
	var rendered []byte
	var err error
	switch cfg.format {
	case "json":
		rendered, err = json.Marshal(report)
		if err != nil {
			return fmt.Errorf("encode ci report: %w", err)
		}
	case "markdown":
		rendered = []byte(renderCIReportMarkdown(report))
	default:
		return errors.New("unsupported ci report format")
	}
	rendered = append(rendered, '\n')
	if cfg.output != "" {
		if err := os.WriteFile(cfg.output, rendered, 0o600); err != nil {
			return fmt.Errorf("write %s: %w", cfg.output, err)
		}
		return nil
	}
	_, err = stdout.Write(rendered)
	return err
}

func publishCIReportGitHub(ctx context.Context, cfg ciReportConfig, report *conbench.CIReport) error {
	if report == nil {
		return errors.New("github publish requires a CI report")
	}
	gh, err := newCIReportGitHubClient(ctx, cfg)
	if err != nil {
		return err
	}
	checkName := cfg.githubCheckName
	if checkName == "" {
		checkName = "Conbench performance report"
	}
	check, err := gh.CreateCheckRun(ctx, cfg.repository, githubapi.CheckRunRequest{
		Name:        checkName,
		HeadSHA:     cfg.commit,
		Status:      "completed",
		Conclusion:  githubCheckConclusion(report.Status),
		CompletedAt: time.Now().UTC().Format(time.RFC3339),
		DetailsURL:  absoluteHTTPURL(report.ReportUrl),
		ExternalID:  cfg.githubExternalID,
		Output: githubapi.CheckRunOutput{
			Title:   githubCheckTitle(report),
			Summary: githubCheckSummary(report, cfg.buildURL),
			Text:    githubCheckDetails(report),
		},
	})
	if err != nil {
		return fmt.Errorf("create github check run: %w", err)
	}
	if !cfg.githubPRComment {
		return nil
	}
	prNumber, err := ciReportGitHubPRNumber(ctx, gh, cfg)
	if err != nil {
		return err
	}
	comment := githubPRComment(report, check.HTMLURL, cfg.server)
	if comment == "" {
		return nil
	}
	if _, err := gh.CreatePullRequestComment(ctx, cfg.repository, prNumber, comment); err != nil {
		return fmt.Errorf("create github pull request comment: %w", err)
	}
	return nil
}

func newCIReportGitHubClient(ctx context.Context, cfg ciReportConfig) (*githubapi.Client, error) {
	token := strings.TrimSpace(cfg.githubToken)
	appID := firstNonEmpty(
		cfg.githubAppID,
		os.Getenv("CONBENCH_CI_GITHUB_APP_ID"),
		os.Getenv("CONBENCH_GITHUB_APP_ID"),
		os.Getenv("GITHUB_APP_ID"),
	)
	appPrivateKey := firstNonEmpty(
		cfg.githubAppPrivateKey,
		os.Getenv("CONBENCH_CI_GITHUB_APP_PRIVATE_KEY"),
		os.Getenv("CONBENCH_GITHUB_APP_PRIVATE_KEY"),
		os.Getenv("GITHUB_APP_PRIVATE_KEY"),
	)
	if token == "" && appID == "" && appPrivateKey == "" {
		token = firstNonEmptyEnv("CONBENCH_CI_GITHUB_TOKEN", "GITHUB_TOKEN", "GITHUB_API_TOKEN")
	}
	apiURL := firstNonEmpty(cfg.githubAPIURL, os.Getenv("CONBENCH_CI_GITHUB_API_URL"))
	client, err := githubapi.NewClient(ctx, githubapi.Config{
		Token:         token,
		AppID:         appID,
		AppPrivateKey: appPrivateKey,
		BaseURL:       apiURL,
	})
	if err != nil {
		return nil, fmt.Errorf("configure github publishing: %w", err)
	}
	return client, nil
}

func ciReportGitHubPRNumber(ctx context.Context, gh *githubapi.Client, cfg ciReportConfig) (int, error) {
	if cfg.githubPRNumber != "" {
		return parsePositiveIntFlag(cfg.githubPRNumber, "--github-pr-number")
	}
	pulls, err := gh.PullRequestsForCommit(ctx, cfg.repository, cfg.commit)
	if err != nil {
		return 0, fmt.Errorf("find github pull request for commit: %w", err)
	}
	if len(pulls) != 1 {
		return 0, fmt.Errorf("find github pull request for commit: expected exactly 1 pull request, found %d", len(pulls))
	}
	return pulls[0].Number, nil
}

func githubCheckConclusion(status conbench.CIReportStatus) string {
	switch status {
	case conbench.CIReportStatusActionRequired:
		return "action_required"
	case conbench.CIReportStatusFailure:
		return "failure"
	case conbench.CIReportStatusSkipped:
		return "skipped"
	default:
		return "success"
	}
}

func githubCheckTitle(report *conbench.CIReport) string {
	switch report.Status {
	case conbench.CIReportStatusActionRequired:
		return "Action required for Conbench report"
	case conbench.CIReportStatusFailure:
		return fmt.Sprintf("Found %d benchmark regression%s", report.Summary.Regressions, pluralS(report.Summary.Regressions))
	case conbench.CIReportStatusSkipped:
		return "Conbench report skipped regression verdict"
	default:
		return "No benchmark regressions detected"
	}
}

func githubCheckSummary(report *conbench.CIReport, buildURL string) string {
	var b strings.Builder
	b.WriteString(ciReportIntro(report))
	if report.StatusReason != "" {
		fmt.Fprintf(&b, "\n\nStatus reason: %s", report.StatusReason)
	}
	fmt.Fprintf(&b, "\n\nRuns: %d. Contender results: %d. Compared: %d. Analyzed: %d. Regressions: %d. Benchmark errors: %d.",
		report.Summary.Runs,
		report.Summary.ContenderResults,
		report.Summary.Compared,
		report.Summary.Analyzed,
		report.Summary.Regressions,
		report.Summary.BenchmarkErrors,
	)
	if report.ReportUrl != "" {
		fmt.Fprintf(&b, "\n\nConbench report: %s", report.ReportUrl)
	}
	if buildURL != "" {
		fmt.Fprintf(&b, "\n\nBuild logs: %s", buildURL)
	}
	return b.String()
}

func githubCheckDetails(report *conbench.CIReport) string {
	var b strings.Builder
	writeGitHubRows(&b, "Benchmark errors", ciReportRowsWithStatus(report, conbench.CIReportComparisonStatusErrored), 10, report.ReportUrl, "")
	writeGitHubRows(&b, "Benchmark regressions", ciReportRowsWithStatus(report, conbench.CIReportComparisonStatusRegressed), 10, report.ReportUrl, "")
	if b.Len() == 0 {
		return ""
	}
	return b.String()
}

func githubPRComment(report *conbench.CIReport, checkURL string, serverURL string) string {
	var b strings.Builder
	b.WriteString(ciReportIntro(report))
	errors := ciReportRowsWithStatus(report, conbench.CIReportComparisonStatusErrored)
	regressions := ciReportRowsWithStatus(report, conbench.CIReportComparisonStatusRegressed)
	switch {
	case len(errors) > 0:
		fmt.Fprintf(&b, "There %s %d benchmark result%s with an error:", were(len(errors)), len(errors), pluralS(len(errors)))
		writeGitHubRows(&b, "", errors, 2, report.ReportUrl, serverURL)
	case report.Summary.ContenderResults == 0:
		b.WriteString("None of the specified runs had any associated benchmark results.\n\n")
	case report.Summary.Analyzed == 0:
		b.WriteString("There were not enough matching historic benchmark results to make a call on whether there were regressions.\n\n")
	case len(regressions) > 0:
		fmt.Fprintf(&b, "There %s %d benchmark result%s indicating a performance regression:", were(len(regressions)), len(regressions), pluralS(len(regressions)))
		writeGitHubRows(&b, "", regressions, 2, report.ReportUrl, serverURL)
	default:
		b.WriteString("There were no benchmark performance regressions.\n\n")
	}
	if checkURL != "" {
		fmt.Fprintf(&b, "The [full Conbench report](%s) has more details.", checkURL)
	} else if report.ReportUrl != "" {
		fmt.Fprintf(&b, "The [full Conbench report](%s) has more details.", absoluteConbenchLink(report.ReportUrl, report.ReportUrl, serverURL))
	}
	return b.String()
}

type ciReportGitHubRow struct {
	runID      string
	runReason  string
	hardware   string
	timestamp  string
	runLink    string
	name       string
	resultLink string
}

func ciReportRowsWithStatus(report *conbench.CIReport, status conbench.CIReportComparisonStatus) []ciReportGitHubRow {
	if report == nil || report.Runs == nil {
		return nil
	}
	rows := []ciReportGitHubRow{}
	for _, run := range *report.Runs {
		if run.Comparisons == nil {
			continue
		}
		reason := "commit"
		if run.RunReason != nil && *run.RunReason != "" {
			reason = *run.RunReason
		}
		for _, comp := range *run.Comparisons {
			if comp.Status != status {
				continue
			}
			link := comp.Links.Result
			if comp.Links.Compare != nil && *comp.Links.Compare != "" {
				link = *comp.Links.Compare
			}
			rows = append(rows, ciReportGitHubRow{
				runID:      run.RunId,
				runReason:  reason,
				hardware:   comp.Hardware.Name,
				timestamp:  comp.Contender.ResultTimestamp.UTC().Format("2006-01-02 15:04:05Z"),
				runLink:    "/runs/" + url.PathEscape(run.RunId),
				name:       ciReportGitHubBenchmarkName(comp),
				resultLink: link,
			})
		}
	}
	return rows
}

func writeGitHubRows(b *strings.Builder, heading string, rows []ciReportGitHubRow, limit int, reportURL string, fallbackBase string) {
	if len(rows) == 0 {
		return
	}
	if heading != "" {
		fmt.Fprintf(b, "## %s\n", heading)
	}
	previousRunID := ""
	written := 0
	for _, row := range rows {
		if limit > 0 && written >= limit {
			fmt.Fprintf(b, "\n- and %d more (see the report linked below)\n\n", len(rows)-limit)
			return
		}
		if row.runID != previousRunID {
			fmt.Fprintf(b, "\n\n- %s Run on `%s` at [%s](%s)", titleWord(row.runReason), row.hardware, row.timestamp, absoluteConbenchLink(reportURL, row.runLink, fallbackBase))
			previousRunID = row.runID
		}
		fmt.Fprintf(b, "\n  - [%s](%s)", row.name, absoluteConbenchLink(reportURL, row.resultLink, fallbackBase))
		written++
	}
	if written > 0 {
		b.WriteString("\n\n")
	}
}

func ciReportGitHubBenchmarkName(comp conbench.CIReportComparison) string {
	name := "`" + comp.Name + "`"
	parts := make([]string, 0, len(comp.Tags))
	for key, value := range comp.Tags {
		if key == "name" || value == nil {
			continue
		}
		parts = append(parts, fmt.Sprintf("%s=%v", key, value))
	}
	sort.Strings(parts)
	if len(parts) > 0 {
		name += " with " + strings.Join(parts, ", ")
	}
	return name
}

func ciReportIntro(report *conbench.CIReport) string {
	runs := report.Summary.Runs
	if runs == 0 && report.Runs != nil {
		runs = int64(len(*report.Runs))
	}
	if report.CommitSha != nil && *report.CommitSha != "" {
		sha := *report.CommitSha
		if len(sha) > 8 {
			sha = sha[:8]
		}
		return fmt.Sprintf("Conbench analyzed the %d benchmark run%s on commit `%s`.\n\n", runs, pluralS(runs), sha)
	}
	return fmt.Sprintf("Conbench analyzed the %d benchmark run%s that triggered this notification.\n\n", runs, pluralS(runs))
}

func absoluteConbenchLink(reportURL string, raw string, fallbackBase string) string {
	if raw == "" {
		return ""
	}
	if isAbsoluteHTTPURL(raw) {
		return raw
	}
	base := fallbackBase
	if parsed, err := url.Parse(reportURL); err == nil && parsed.Scheme != "" && parsed.Host != "" {
		base = parsed.Scheme + "://" + parsed.Host
	}
	if base == "" {
		return raw
	}
	if strings.HasPrefix(raw, "/") {
		return strings.TrimRight(base, "/") + raw
	}
	return strings.TrimRight(base, "/") + "/" + raw
}

func absoluteHTTPURL(raw string) string {
	if isAbsoluteHTTPURL(raw) {
		return raw
	}
	return ""
}

func isAbsoluteHTTPURL(raw string) bool {
	u, err := url.Parse(raw)
	return err == nil && (u.Scheme == "http" || u.Scheme == "https") && u.Host != ""
}

func parsePositiveIntFlag(raw string, flag string) (int, error) {
	value, err := strconv.Atoi(raw)
	if err != nil || value <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", flag)
	}
	return value, nil
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func firstNonEmptyEnv(names ...string) string {
	for _, name := range names {
		if value := strings.TrimSpace(os.Getenv(name)); value != "" {
			return value
		}
	}
	return ""
}

func pluralS[T ~int | ~int64](n T) string {
	if n == 1 {
		return ""
	}
	return "s"
}

func were(n int) string {
	if n == 1 {
		return "was"
	}
	return "were"
}

func titleWord(value string) string {
	if value == "" {
		return value
	}
	return strings.ToUpper(value[:1]) + value[1:]
}

func renderCIReportMarkdown(report *conbench.CIReport) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Conbench CI report\n\n")
	fmt.Fprintf(&b, "Status: %s\n\n", report.Status)
	if report.StatusReason != "" {
		fmt.Fprintf(&b, "Reason: %s\n\n", report.StatusReason)
	}
	if report.ReportUrl != "" {
		fmt.Fprintf(&b, "Report: %s\n\n", report.ReportUrl)
	}
	fmt.Fprintf(&b, "| Metric | Value |\n| --- | ---: |\n")
	fmt.Fprintf(&b, "| Runs | %d |\n", report.Summary.Runs)
	fmt.Fprintf(&b, "| Contender results | %d |\n", report.Summary.ContenderResults)
	fmt.Fprintf(&b, "| Compared | %d |\n", report.Summary.Compared)
	fmt.Fprintf(&b, "| Analyzed | %d |\n", report.Summary.Analyzed)
	fmt.Fprintf(&b, "| Regressions | %d |\n", report.Summary.Regressions)
	fmt.Fprintf(&b, "| Improvements | %d |\n", report.Summary.Improvements)
	fmt.Fprintf(&b, "| Benchmark errors | %d |\n", report.Summary.BenchmarkErrors)
	fmt.Fprintf(&b, "| Missing baseline | %d |\n", report.Summary.MissingBaseline)
	fmt.Fprintf(&b, "| Not comparable | %d |\n\n", report.Summary.NotComparable)

	if report.Runs == nil || len(*report.Runs) == 0 {
		return b.String()
	}
	fmt.Fprintf(&b, "## Runs\n\n")
	for _, run := range *report.Runs {
		fmt.Fprintf(&b, "### %s\n\n", run.RunId)
		if run.BaselineRunId != nil {
			fmt.Fprintf(&b, "Baseline run: `%s`\n\n", *run.BaselineRunId)
		}
		if run.BaselineError != nil {
			fmt.Fprintf(&b, "Baseline: %s\n\n", run.BaselineError.Message)
		}
		if run.Comparisons == nil || len(*run.Comparisons) == 0 {
			continue
		}
		fmt.Fprintf(&b, "| Status | Benchmark | Unit | Contender | Baseline |\n| --- | --- | --- | ---: | ---: |\n")
		for _, row := range *run.Comparisons {
			fmt.Fprintf(&b, "| %s | %s | %s | %s | %s |\n",
				row.Status,
				escapeMarkdownCell(row.Name),
				stringOrDash(row.Unit),
				floatOrDash(row.Contender.SingleValueSummary),
				baselineSVSOrDash(row.Baseline),
			)
		}
		fmt.Fprintf(&b, "\n")
	}
	return b.String()
}

func validCIReportBaselineFlag(value string) bool {
	return value == string(conbench.ForkPoint) || value == string(conbench.Parent) || value == string(conbench.LatestDefault)
}

func commaIDs(raw string) []string {
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		if id := strings.TrimSpace(part); id != "" {
			out = append(out, id)
		}
	}
	return out
}

func positiveFloatFlagValue(raw, name string) (float64, error) {
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil || math.IsNaN(v) || math.IsInf(v, 0) || v <= 0 {
		return 0, fmt.Errorf("%s must be a finite number greater than zero", name)
	}
	return v, nil
}

func validatePositiveFloatFlag(raw, name string) error {
	_, err := positiveFloatFlagValue(raw, name)
	return err
}

func escapeMarkdownCell(value string) string {
	return strings.ReplaceAll(value, "|", "\\|")
}

func stringOrDash(value *string) string {
	if value == nil || *value == "" {
		return "-"
	}
	return escapeMarkdownCell(*value)
}

func floatOrDash(value *float64) string {
	if value == nil {
		return "-"
	}
	return strconv.FormatFloat(*value, 'g', 6, 64)
}

func baselineSVSOrDash(value *conbench.CIReportBaselineSide) string {
	if value == nil {
		return "-"
	}
	return floatOrDash(value.SingleValueSummary)
}
