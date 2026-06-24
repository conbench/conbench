package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/conbench/conbench/sdk/go/conbench"
	"github.com/spf13/cobra"
)

// submitConfig is a parsed `results submit` invocation.
type submitConfig struct {
	fixtures []string
	server   string
	token    string
}

type resultGetConfig struct {
	id     string
	server string
}

type submitResultLine struct {
	File               string `json:"file"`
	OK                 bool   `json:"ok"`
	ID                 string `json:"id,omitempty"`
	HistoryFingerprint string `json:"history_fingerprint,omitempty"`
	Error              string `json:"error,omitempty"`
}

func resultsSubmitCommand(stdout io.Writer) *cobra.Command {
	return newResultsSubmitCommand(stdout, runSubmitConfig)
}

func newResultsSubmitCommand(
	stdout io.Writer,
	run func(context.Context, submitConfig, io.Writer) error,
) *cobra.Command {
	var cfg submitConfig
	cmd := configureCommand(&cobra.Command{
		Use:   "submit <file-or-glob>...",
		Short: "Submit benchmark result JSON.",
		Args: func(cmd *cobra.Command, args []string) error {
			switch {
			case len(args) == 0:
				return commandUsageError(cmd, "missing benchmark result file")
			case cfg.server == "":
				return commandUsageError(cmd, "--server is required")
			}

			fixtures, err := expandSubmitPositionals(cmd, args)
			if err != nil {
				return err
			}
			cfg.fixtures = fixtures
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout)
		},
	})
	cmd.Flags().StringVar(&cfg.server, "server", "", "Conbench server base URL (required)")
	cmd.Flags().StringVar(&cfg.token, "token", "", "bearer token for write authentication")
	return cmd
}

// parseSubmitArgs parses the submit flags, which may appear before, after, or
// interspersed with positional file/glob arguments. One or more expanded files
// and a non-empty --server are required.
func parseSubmitArgs(args []string) (submitConfig, error) {
	var cfg submitConfig
	cmd := newResultsSubmitCommand(io.Discard, func(_ context.Context, parsed submitConfig, _ io.Writer) error {
		cfg = parsed
		return nil
	})
	if err := executeParseCommand(cmd, args); err != nil {
		return submitConfig{}, err
	}
	return cfg, nil
}

func resultsGetCommand(stdout io.Writer) *cobra.Command {
	return newResultsGetCommand(stdout, runResultGetConfig)
}

func newResultsGetCommand(
	stdout io.Writer,
	run func(context.Context, resultGetConfig, io.Writer) error,
) *cobra.Command {
	var cfg resultGetConfig
	cmd := configureCommand(&cobra.Command{
		Use:   "get <id>",
		Short: "Fetch a benchmark result by id.",
		Args: func(cmd *cobra.Command, args []string) error {
			switch {
			case len(args) == 0:
				return commandUsageError(cmd, "missing benchmark result id")
			case len(args) > 1:
				return commandUsageError(cmd, "too many benchmark result ids")
			case cfg.server == "":
				return commandUsageError(cmd, "--server is required")
			}
			cfg.id = args[0]
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout)
		},
	})
	cmd.Flags().StringVar(&cfg.server, "server", "", "Conbench server base URL (required)")
	return cmd
}

func parseResultGetArgs(args []string) (resultGetConfig, error) {
	var cfg resultGetConfig
	cmd := newResultsGetCommand(io.Discard, func(_ context.Context, parsed resultGetConfig, _ io.Writer) error {
		cfg = parsed
		return nil
	})
	if err := executeParseCommand(cmd, args); err != nil {
		return resultGetConfig{}, err
	}
	return cfg, nil
}

func expandSubmitPositionals(cmd *cobra.Command, positionals []string) ([]string, error) {
	var fixtures []string
	for _, positional := range positionals {
		if !hasGlobMeta(positional) {
			fixtures = append(fixtures, positional)
			continue
		}
		matches, err := filepath.Glob(positional)
		if err != nil {
			return nil, commandUsageError(cmd, "malformed glob %q: %s", positional, err)
		}
		if len(matches) == 0 {
			return nil, commandUsageError(cmd, "glob %q matched no files", positional)
		}
		fixtures = append(fixtures, matches...)
	}
	return fixtures, nil
}

func hasGlobMeta(path string) bool {
	return strings.ContainsAny(path, "*?[")
}

// runSubmitConfig reads the fixture, decodes it into the generated request model
// (rejecting unknown fields so a schema mismatch fails loudly rather than
// silently dropping data), submits it, and prints the result identity.
func runSubmitConfig(ctx context.Context, cfg submitConfig, stdout io.Writer) error {
	bearer, err := resolveBearer(cfg.token, cfg.server)
	if err != nil {
		return err
	}

	client, err := newClient(cfg.server)
	if err != nil {
		return err
	}
	params := &conbench.SubmitResultParams{}
	if bearer != "" {
		params.Authorization = &bearer
	}

	if len(cfg.fixtures) == 1 {
		result, err := submitFixture(ctx, client, params, cfg.server, cfg.fixtures[0])
		if err != nil {
			return err
		}
		return writeJSONLine(stdout, struct {
			ID                 string `json:"id"`
			HistoryFingerprint string `json:"history_fingerprint"`
		}{result.ID, result.HistoryFingerprint})
	}

	anyFailed := false
	for _, fixture := range cfg.fixtures {
		result, _ := submitFixture(ctx, client, params, cfg.server, fixture)
		if !result.OK {
			anyFailed = true
		}
		if err := writeJSONLine(stdout, result); err != nil {
			return err
		}
	}
	if anyFailed {
		return submitPartialFailure{}
	}
	return nil
}

func runResultGetConfig(ctx context.Context, cfg resultGetConfig, stdout io.Writer) error {
	client, err := newClient(cfg.server)
	if err != nil {
		return err
	}
	resp, err := client.GetBenchmarkResultWithResponse(ctx, cfg.id)
	if err != nil {
		return fmt.Errorf("get result from %s: %w", cfg.server, err)
	}
	if resp.JSON200 == nil {
		return statusError(resp.HTTPResponse, resp.Body)
	}
	return writeJSONLine(stdout, resp.JSON200)
}

type submitPartialFailure struct{}

func (submitPartialFailure) Error() string {
	return "one or more result submissions failed"
}

func (submitPartialFailure) SuppressDiagnostic() {}

func submitFixture(
	ctx context.Context,
	client *conbench.ClientWithResponses,
	params *conbench.SubmitResultParams,
	server string,
	fixture string,
) (submitResultLine, error) {
	result := submitResultLine{File: fixture}
	body, err := decodeRequest(fixture)
	if err != nil {
		result.Error = err.Error()
		return result, err
	}

	resp, err := client.SubmitResultWithBodyWithResponse(ctx, params, "application/json", bytes.NewReader(body))
	if err != nil {
		err = fmt.Errorf("submit to %s: %w", server, err)
		result.Error = err.Error()
		return result, err
	}
	if resp.JSON201 == nil {
		err = statusError(resp.HTTPResponse, resp.Body)
		result.Error = string(bytes.TrimSpace(resp.Body))
		if result.Error == "" {
			result.Error = err.Error()
		}
		return result, err
	}

	return submitResultLine{
		File:               fixture,
		OK:                 true,
		ID:                 resp.JSON201.Id,
		HistoryFingerprint: resp.JSON201.HistoryFingerprint,
	}, nil
}

func decodeRequest(path string) ([]byte, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	var body conbench.SubmitRequest
	if err := dec.Decode(&body); err != nil {
		return nil, fmt.Errorf("decode %s: %w", path, err)
	}
	if err := dec.Decode(new(json.RawMessage)); !errors.Is(err, io.EOF) {
		return nil, fmt.Errorf("decode %s: trailing data after the JSON object", path)
	}
	return raw, nil
}
