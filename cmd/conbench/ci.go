package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"strconv"
	"strings"

	"github.com/conbench/conbench/sdk/go/conbench"
	"github.com/spf13/cobra"
)

type ciReportConfig struct {
	server         string
	token          string
	repository     string
	commit         string
	runIDs         string
	baselineRunIDs string
	baseline       string
	threshold      string
	thresholdSet   bool
	thresholdZ     string
	thresholdZSet  bool
	format         string
	output         string
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
	if resp.JSON200.Status == conbench.Failure || resp.JSON200.Status == conbench.ActionRequired {
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
