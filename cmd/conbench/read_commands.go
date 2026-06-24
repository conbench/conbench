package main

import (
	"context"
	"fmt"
	"io"

	"github.com/conbench/conbench/sdk/go/conbench"
	"github.com/spf13/cobra"
)

type compareConfig struct {
	server        string
	baseline      string
	contender     string
	threshold     float64
	thresholdSet  bool
	thresholdZ    float64
	thresholdZSet bool
}

type seriesListConfig struct {
	server      string
	q           string
	hardware    string
	repository  string
	fingerprint string
	activeSince string
	activeUntil string
	cursor      string
	pageSize    int64
	pageSizeSet bool
}

func compareCommand(stdout io.Writer) *cobra.Command {
	return newCompareCommand(stdout, runCompareConfig)
}

func newCompareCommand(
	stdout io.Writer,
	run func(context.Context, compareConfig, io.Writer) error,
) *cobra.Command {
	var cfg compareConfig
	cmd := configureCommand(&cobra.Command{
		Use:   "compare <baseline-id> <contender-id>",
		Short: "Compare two benchmark results.",
		Args: func(cmd *cobra.Command, args []string) error {
			cfg.thresholdSet = cmd.Flags().Changed("threshold")
			cfg.thresholdZSet = cmd.Flags().Changed("threshold-z")
			switch {
			case len(args) == 0:
				return commandUsageError(cmd, "missing baseline benchmark result id")
			case len(args) == 1:
				return commandUsageError(cmd, "missing contender benchmark result id")
			case len(args) > 2:
				return commandUsageError(cmd, "too many benchmark result ids")
			case cfg.server == "":
				return commandUsageError(cmd, "--server is required")
			}
			cfg.baseline = args[0]
			cfg.contender = args[1]
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout)
		},
	})
	cmd.Flags().StringVar(&cfg.server, "server", "", "Conbench server base URL (required)")
	cmd.Flags().Float64Var(&cfg.threshold, "threshold", 0, "pairwise percent-change threshold")
	cmd.Flags().Float64Var(&cfg.thresholdZ, "threshold-z", 0, "lookback z-score threshold")
	return cmd
}

func parseCompareArgs(args []string) (compareConfig, error) {
	var cfg compareConfig
	cmd := newCompareCommand(io.Discard, func(_ context.Context, parsed compareConfig, _ io.Writer) error {
		cfg = parsed
		return nil
	})
	if err := executeParseCommand(cmd, args); err != nil {
		return compareConfig{}, err
	}
	return cfg, nil
}

func runCompareConfig(ctx context.Context, cfg compareConfig, stdout io.Writer) error {
	client, err := newClient(cfg.server)
	if err != nil {
		return err
	}
	params := &conbench.CompareBenchmarkResultsParams{
		BaselineResultId:  cfg.baseline,
		ContenderResultId: cfg.contender,
	}
	if cfg.thresholdSet {
		params.Threshold = &cfg.threshold
	}
	if cfg.thresholdZSet {
		params.ThresholdZ = &cfg.thresholdZ
	}

	resp, err := client.CompareBenchmarkResultsWithResponse(ctx, params)
	if err != nil {
		return fmt.Errorf("compare results from %s: %w", cfg.server, err)
	}
	if resp.JSON200 == nil {
		return statusError(resp.HTTPResponse, resp.Body)
	}
	return writeJSONLine(stdout, resp.JSON200)
}

func seriesListCommand(stdout io.Writer) *cobra.Command {
	return newSeriesListCommand(stdout, runSeriesListConfig)
}

func newSeriesListCommand(
	stdout io.Writer,
	run func(context.Context, seriesListConfig, io.Writer) error,
) *cobra.Command {
	var cfg seriesListConfig
	cmd := configureCommand(&cobra.Command{
		Use:   "list",
		Short: "List benchmark series.",
		Args: func(cmd *cobra.Command, args []string) error {
			cfg.pageSizeSet = cmd.Flags().Changed("page-size")
			switch {
			case len(args) > 0:
				return commandUsageError(cmd, "series list does not accept positional arguments")
			case cfg.server == "":
				return commandUsageError(cmd, "--server is required")
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout)
		},
	})
	cmd.Flags().StringVar(&cfg.server, "server", "", "Conbench server base URL (required)")
	cmd.Flags().StringVar(&cfg.q, "q", "", "substring match on case name and case tags")
	cmd.Flags().StringVar(&cfg.hardware, "hardware", "", "hardware name")
	cmd.Flags().StringVar(&cfg.repository, "repository", "", "repository URL")
	cmd.Flags().StringVar(&cfg.fingerprint, "fingerprint", "", "history fingerprint")
	cmd.Flags().StringVar(&cfg.activeSince, "active-since", "", "latest commit at or after this RFC3339 instant")
	cmd.Flags().StringVar(&cfg.activeUntil, "active-until", "", "latest commit at or before this RFC3339 instant")
	cmd.Flags().StringVar(&cfg.cursor, "cursor", "", "pagination cursor")
	cmd.Flags().Int64Var(&cfg.pageSize, "page-size", 0, "page size")
	return cmd
}

func parseSeriesListArgs(args []string) (seriesListConfig, error) {
	var cfg seriesListConfig
	cmd := newSeriesListCommand(io.Discard, func(_ context.Context, parsed seriesListConfig, _ io.Writer) error {
		cfg = parsed
		return nil
	})
	if err := executeParseCommand(cmd, args); err != nil {
		return seriesListConfig{}, err
	}
	return cfg, nil
}

func runSeriesListConfig(ctx context.Context, cfg seriesListConfig, stdout io.Writer) error {
	client, err := newClient(cfg.server)
	if err != nil {
		return err
	}
	params := conbench.ListSeriesParams{
		Q:           optionalString(cfg.q),
		Hardware:    optionalString(cfg.hardware),
		Repository:  optionalString(cfg.repository),
		Fingerprint: optionalString(cfg.fingerprint),
		ActiveSince: optionalString(cfg.activeSince),
		ActiveUntil: optionalString(cfg.activeUntil),
		Cursor:      optionalString(cfg.cursor),
	}
	if cfg.pageSizeSet {
		params.PageSize = &cfg.pageSize
	}

	resp, err := client.ListSeriesWithResponse(ctx, &params)
	if err != nil {
		return fmt.Errorf("list series from %s: %w", cfg.server, err)
	}
	if resp.JSON200 == nil {
		return statusError(resp.HTTPResponse, resp.Body)
	}
	return writeJSONLine(stdout, resp.JSON200)
}

func optionalString(value string) *string {
	if value == "" {
		return nil
	}
	return &value
}
