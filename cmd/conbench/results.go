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
	"sync"

	"github.com/conbench/conbench/sdk/go/conbench"
	"github.com/spf13/cobra"
)

const defaultSubmitJobs = 8

// submitConfig is a parsed `results submit` invocation.
type submitConfig struct {
	fixtures []string
	server   string
	token    string
	jobs     int
}

type resultGetConfig struct {
	id     string
	server string
}

type submitResultLine struct {
	File               string `json:"file"`
	Index              *int   `json:"index,omitempty"`
	OK                 bool   `json:"ok"`
	ID                 string `json:"id,omitempty"`
	HistoryFingerprint string `json:"history_fingerprint,omitempty"`
	Error              string `json:"error,omitempty"`
}

type submitRequestBody struct {
	File  string
	Index *int
	Body  []byte
}

type submitWorkItem struct {
	lineIndex int
	body      submitRequestBody
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
			case cfg.jobs <= 0:
				return commandUsageError(cmd, "--jobs must be greater than zero")
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
	cmd.Flags().IntVar(&cfg.jobs, "jobs", defaultSubmitJobs, "maximum concurrent result submissions")
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

	jobs := cfg.jobs
	if jobs <= 0 {
		jobs = defaultSubmitJobs
	}

	lines, tasks, err := prepareSubmitWork(cfg.fixtures)
	if err != nil {
		return err
	}

	if len(tasks) == 1 && len(lines) == 1 {
		result, err := submitBody(ctx, client, params, cfg.server, tasks[0].body)
		if err != nil {
			return err
		}
		return writeJSONLine(stdout, struct {
			ID                 string `json:"id"`
			HistoryFingerprint string `json:"history_fingerprint"`
		}{result.ID, result.HistoryFingerprint})
	}

	submitMany(ctx, client, params, cfg.server, jobs, lines, tasks)

	anyFailed := false
	for _, line := range lines {
		if !line.OK {
			anyFailed = true
		}
		if err := writeJSONLine(stdout, line); err != nil {
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

func prepareSubmitWork(fixtures []string) ([]submitResultLine, []submitWorkItem, error) {
	lines := make([]submitResultLine, 0, len(fixtures))
	var tasks []submitWorkItem
	for _, fixture := range fixtures {
		bodies, err := decodeFixtureRequests(fixture)
		if err != nil {
			if len(fixtures) == 1 {
				return nil, nil, err
			}
			lines = append(lines, submitResultLine{File: fixture, Error: err.Error()})
			continue
		}
		for _, body := range bodies {
			lineIndex := len(lines)
			lines = append(lines, submitResultLine{File: body.File, Index: body.Index})
			tasks = append(tasks, submitWorkItem{lineIndex: lineIndex, body: body})
		}
	}
	return lines, tasks, nil
}

func submitMany(
	ctx context.Context,
	client *conbench.ClientWithResponses,
	params *conbench.SubmitResultParams,
	server string,
	jobs int,
	lines []submitResultLine,
	tasks []submitWorkItem,
) {
	if jobs > len(tasks) {
		jobs = len(tasks)
	}
	if jobs <= 0 {
		return
	}

	work := make(chan submitWorkItem)
	var wg sync.WaitGroup
	for worker := 0; worker < jobs; worker++ {
		wg.Go(func() {
			for task := range work {
				line, _ := submitBody(ctx, client, params, server, task.body)
				lines[task.lineIndex] = line
			}
		})
	}
	for _, task := range tasks {
		work <- task
	}
	close(work)
	wg.Wait()
}

func submitBody(
	ctx context.Context,
	client *conbench.ClientWithResponses,
	params *conbench.SubmitResultParams,
	server string,
	body submitRequestBody,
) (submitResultLine, error) {
	result := submitResultLine{File: body.File, Index: body.Index}

	resp, err := client.SubmitResultWithBodyWithResponse(ctx, params, "application/json", bytes.NewReader(body.Body))
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
		File:               body.File,
		Index:              body.Index,
		OK:                 true,
		ID:                 resp.JSON201.Id,
		HistoryFingerprint: resp.JSON201.HistoryFingerprint,
	}, nil
}

func decodeFixtureRequests(path string) ([]submitRequestBody, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	var value json.RawMessage
	if err := dec.Decode(&value); err != nil {
		return nil, fmt.Errorf("decode %s: %w", path, err)
	}
	if err := dec.Decode(new(json.RawMessage)); !errors.Is(err, io.EOF) {
		return nil, fmt.Errorf("decode %s: trailing data after the JSON object", path)
	}
	if len(bytes.TrimSpace(value)) == 0 {
		return nil, fmt.Errorf("decode %s: empty JSON value", path)
	}
	if bytes.HasPrefix(bytes.TrimSpace(value), []byte("[")) {
		var items []json.RawMessage
		if err := json.Unmarshal(value, &items); err != nil {
			return nil, fmt.Errorf("decode %s: %w", path, err)
		}
		if len(items) == 0 {
			return nil, fmt.Errorf("decode %s: array must contain at least one benchmark result", path)
		}
		out := make([]submitRequestBody, 0, len(items))
		for idx, item := range items {
			source := fmt.Sprintf("%s[%d]", path, idx)
			if err := validateSubmitRequest(source, item); err != nil {
				return nil, err
			}
			index := idx
			out = append(out, submitRequestBody{File: path, Index: &index, Body: item})
		}
		return out, nil
	}
	if err := validateSubmitRequest(path, value); err != nil {
		return nil, err
	}
	return []submitRequestBody{{File: path, Body: value}}, nil
}

func validateSubmitRequest(source string, raw []byte) error {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	var body conbench.SubmitRequest
	if err := dec.Decode(&body); err != nil {
		return fmt.Errorf("decode %s: %w", source, err)
	}
	if err := dec.Decode(new(json.RawMessage)); !errors.Is(err, io.EOF) {
		return fmt.Errorf("decode %s: trailing data after the JSON object", source)
	}
	return nil
}
