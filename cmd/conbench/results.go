package main

import (
	"bufio"
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

type submitDecoder func(path string, yield func(submitRequestBody) error) error

type submitFunc func(ctx context.Context, body submitRequestBody) (submitResultLine, error)

type indexedSubmitResult struct {
	lineIndex int
	line      submitResultLine
	err       error
}

type submitStreamResult struct {
	lines          []submitResultLine
	submitted      int
	firstSubmitErr error
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

	stream, err := streamSubmitWork(
		ctx,
		cfg.fixtures,
		jobs,
		streamDecodeFixtureRequests,
		func(ctx context.Context, body submitRequestBody) (submitResultLine, error) {
			return submitBody(ctx, client, params, cfg.server, body)
		},
	)
	if err != nil {
		return err
	}

	if stream.submitted == 1 && len(stream.lines) == 1 {
		line := stream.lines[0]
		if !line.OK {
			if stream.firstSubmitErr != nil {
				return stream.firstSubmitErr
			}
			return submitPartialFailure{}
		}
		return writeJSONLine(stdout, struct {
			ID                 string `json:"id"`
			HistoryFingerprint string `json:"history_fingerprint"`
		}{line.ID, line.HistoryFingerprint})
	}

	anyFailed := false
	for _, line := range stream.lines {
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

func streamSubmitWork(
	ctx context.Context,
	fixtures []string,
	jobs int,
	decode submitDecoder,
	submit submitFunc,
) (submitStreamResult, error) {
	if jobs <= 0 {
		jobs = defaultSubmitJobs
	}

	var (
		mu     sync.Mutex
		stream submitStreamResult
	)
	work := make(chan submitWorkItem)
	results := make(chan indexedSubmitResult, jobs)
	var wg sync.WaitGroup
	for worker := 0; worker < jobs; worker++ {
		wg.Go(func() {
			for task := range work {
				line, err := submit(ctx, task.body)
				results <- indexedSubmitResult{lineIndex: task.lineIndex, line: line, err: err}
			}
		})
	}

	collected := make(chan struct{})
	go func() {
		defer close(collected)
		for result := range results {
			mu.Lock()
			stream.lines[result.lineIndex] = result.line
			if result.err != nil && stream.firstSubmitErr == nil {
				stream.firstSubmitErr = result.err
			}
			mu.Unlock()
		}
	}()

	appendLine := func(line submitResultLine) int {
		mu.Lock()
		defer mu.Unlock()
		stream.lines = append(stream.lines, line)
		return len(stream.lines) - 1
	}
	finish := func() {
		close(work)
		wg.Wait()
		close(results)
		<-collected
	}

	for _, fixture := range fixtures {
		err := decode(fixture, func(body submitRequestBody) error {
			lineIndex := appendLine(submitResultLine{File: body.File, Index: body.Index})
			stream.submitted++
			work <- submitWorkItem{lineIndex: lineIndex, body: body}
			return nil
		})
		if err != nil {
			if len(fixtures) == 1 {
				finish()
				return submitStreamResult{}, err
			}
			appendLine(submitResultLine{File: fixture, Error: err.Error()})
			continue
		}
	}
	finish()
	return stream, nil
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
	var out []submitRequestBody
	err := streamDecodeFixtureRequests(path, func(body submitRequestBody) error {
		out = append(out, body)
		return nil
	})
	return out, err
}

func streamDecodeFixtureRequests(path string, yield func(submitRequestBody) error) error {
	file, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}
	defer file.Close()

	reader := bufio.NewReader(file)
	first, err := peekFirstJSONByte(reader)
	if err != nil {
		return fmt.Errorf("decode %s: %w", path, err)
	}
	if first == '[' {
		return streamDecodeArrayFixture(path, reader, yield)
	}

	raw, err := io.ReadAll(reader)
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}
	return streamDecodeSingleFixture(path, raw, yield)
}

func peekFirstJSONByte(reader *bufio.Reader) (byte, error) {
	for {
		b, err := reader.Peek(1)
		if err != nil {
			return 0, err
		}
		if !isJSONWhitespace(b[0]) {
			return b[0], nil
		}
		if _, err := reader.ReadByte(); err != nil {
			return 0, err
		}
	}
}

func isJSONWhitespace(b byte) bool {
	switch b {
	case ' ', '\n', '\r', '\t':
		return true
	default:
		return false
	}
}

func streamDecodeSingleFixture(path string, raw []byte, yield func(submitRequestBody) error) error {
	dec := json.NewDecoder(bytes.NewReader(raw))
	var value json.RawMessage
	if err := dec.Decode(&value); err != nil {
		return fmt.Errorf("decode %s: %w", path, err)
	}
	if err := dec.Decode(new(json.RawMessage)); !errors.Is(err, io.EOF) {
		return fmt.Errorf("decode %s: trailing data after the JSON object", path)
	}
	if len(bytes.TrimSpace(value)) == 0 {
		return fmt.Errorf("decode %s: empty JSON value", path)
	}
	if err := validateSubmitRequest(path, value); err != nil {
		return err
	}
	return yield(submitRequestBody{File: path, Body: value})
}

func streamDecodeArrayFixture(path string, reader *bufio.Reader, yield func(submitRequestBody) error) error {
	dec := json.NewDecoder(reader)
	if _, err := dec.Token(); err != nil {
		return fmt.Errorf("decode %s: %w", path, err)
	}
	if !dec.More() {
		return fmt.Errorf("decode %s: array must contain at least one benchmark result", path)
	}
	for idx := 0; dec.More(); idx++ {
		var item json.RawMessage
		if err := dec.Decode(&item); err != nil {
			return fmt.Errorf("decode %s: %w", path, err)
		}
		source := fmt.Sprintf("%s[%d]", path, idx)
		if err := validateSubmitRequest(source, item); err != nil {
			return err
		}
		index := idx
		if err := yield(submitRequestBody{File: path, Index: &index, Body: item}); err != nil {
			return err
		}
	}
	if _, err := dec.Token(); err != nil {
		return fmt.Errorf("decode %s: %w", path, err)
	}
	if err := dec.Decode(new(json.RawMessage)); !errors.Is(err, io.EOF) {
		return fmt.Errorf("decode %s: trailing data after the JSON object", path)
	}
	return nil
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
