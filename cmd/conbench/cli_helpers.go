package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/conbench/conbench/sdk/go/conbench"
	"github.com/spf13/cobra"
)

var errUsage = errors.New("usage")

type usageErr struct {
	msg string
}

func (e usageErr) Error() string {
	return e.msg
}

func (e usageErr) Is(target error) bool {
	return target == errUsage
}

func usageError(message string) error {
	return usageErr{msg: message}
}

func commandUsageError(cmd *cobra.Command, format string, args ...any) error {
	message := fmt.Sprintf(format, args...)
	usage := strings.TrimRight(cmd.UsageString(), "\n")
	if message == "" {
		return usageError(usage)
	}
	return usageError(message + "\n" + usage)
}

func isUsage(err error) bool {
	return errors.Is(err, errUsage)
}

func configureCommand(cmd *cobra.Command) *cobra.Command {
	cmd.SilenceUsage = true
	cmd.SilenceErrors = true
	cmd.SetFlagErrorFunc(func(cmd *cobra.Command, err error) error {
		return commandUsageError(cmd, "%s", err)
	})
	return cmd
}

func executeParseCommand(cmd *cobra.Command, args []string) error {
	cmd.SetArgs(args)
	cmd.SetOut(io.Discard)
	cmd.SetErr(io.Discard)
	if err := cmd.ExecuteContext(context.Background()); err != nil {
		if isCobraUsageError(err) {
			return commandUsageError(cmd, "%s", err)
		}
		return err
	}
	return nil
}

func resolveBearer(flagToken, server string) (string, error) {
	token, err := resolveTokenFromSources(flagToken, server)
	if err != nil {
		return "", err
	}
	if token == "" {
		return "", nil
	}
	return "Bearer " + token, nil
}

func newClient(server string) (*conbench.ClientWithResponses, error) {
	client, err := conbench.NewClientWithResponses(server, conbench.WithHTTPClient(newCLIHTTPClient()))
	if err != nil {
		return nil, fmt.Errorf("create client: %w", err)
	}
	return client, nil
}

func newCLIHTTPClient() *http.Client {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.MaxIdleConns = 128
	transport.MaxIdleConnsPerHost = 64
	return &http.Client{Transport: transport}
}

func bearerRequestEditor(bearer string) conbench.RequestEditorFn {
	return func(_ context.Context, req *http.Request) error {
		if bearer != "" {
			req.Header.Set("Authorization", bearer)
		}
		return nil
	}
}

func writeJSONLine(stdout io.Writer, value any) error {
	out, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("encode output: %w", err)
	}
	fmt.Fprintln(stdout, string(out))
	return nil
}

func statusError(resp *http.Response, body []byte) error {
	return fmt.Errorf("server returned %s: %s", resp.Status, bytes.TrimSpace(body))
}
