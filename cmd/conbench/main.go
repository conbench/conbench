// Command conbench is the Conbench CLI. It has these subcommands:
//
//	conbench results submit <file-or-glob>... --server URL [--token TOKEN]
//	conbench results get <id> --server URL
//	conbench compare <baseline-id> <contender-id> --server URL [--threshold N] [--threshold-z N]
//	conbench series list --server URL [--q TEXT] [--hardware NAME] [--repository URL] [--fingerprint FP] [--active-since RFC3339] [--active-until RFC3339] [--cursor CURSOR] [--page-size N]
//	conbench history export <result-id> --server URL [--token TOKEN] [--output PATH]
//	conbench ci report --server URL [--repository URL --commit SHA] [--run-ids ID[,ID...]] [--baseline-run-ids ID[,ID...]]
//	conbench openapi [--downgrade]
//	conbench auth login --server URL
//	conbench auth token list --server URL [--token TOKEN]
//	conbench auth token revoke <id> --server URL [--token TOKEN]
//	conbench admin repair-commits [--repository URL] [--limit N] [--cursor CURSOR] [--dry-run] [--backfill] [--backfill-timeout DURATION] [--github-timeout DURATION] [--format text|json]
//	conbench admin alerts evaluate [--format text|json]
//	conbench admin alerts deliver [--channel webhook|slack|github-check|github-comment|email] [--webhook-url URL] [--slack-webhook-url URL] [--github-repository URL] [--github-token TOKEN] [--github-api-url URL] [--email-smtp-addr HOST:PORT] [--email-from ADDRESS] [--email-to ADDRESS[,ADDRESS...]] [--email-username USERNAME] [--email-password PASSWORD] [--limit N] [--retry-after DURATION] [--timeout DURATION] [--format text|json]
//	conbench admin prod-clone --help
//	conbench admin prod-clone samples --help
//	conbench serve
//
// `results submit` submits a benchmark result (read from the JSON file) to a
// Conbench server via the generated Go client. On success it prints exactly
//
//	{"id":"...","history_fingerprint":"..."}
//
// to stdout and nothing else; every diagnostic and error goes to stderr. That
// stable, machine-readable contract is what CI and downstream tooling consume.
//
// `auth login` runs the OIDC loopback flow and persists the minted API token to
// the per-user credentials file; it prints only the server and the token prefix
// to stdout, never the plaintext token. `auth token list|revoke` manage the
// caller's API tokens, emitting one line of machine-readable JSON to stdout.
package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/conbench/conbench/internal/prodclone"
	"github.com/conbench/conbench/internal/server"
	"github.com/conbench/conbench/internal/serverapp"
	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

// errLoginFailed signals that `auth login` already wrote its own diagnostics to
// stderr and returned a non-zero code; run maps it to exit 1 without printing a
// second, redundant "conbench: ..." line over the real cause.
var errLoginFailed error = suppressedDiagnosticError{err: errors.New("login failed")}

var serveRunner = serverapp.Run

type suppressDiagnostic interface {
	SuppressDiagnostic()
}

type suppressedDiagnosticError struct {
	err error
}

func (e suppressedDiagnosticError) Error() string {
	return e.err.Error()
}

func (suppressedDiagnosticError) SuppressDiagnostic() {}

type suppressedExitError struct {
	code int
}

func (e suppressedExitError) Error() string {
	return fmt.Sprintf("command exited with status %d", e.code)
}

func (e suppressedExitError) ExitCode() int {
	return e.code
}

func (suppressedExitError) SuppressDiagnostic() {}

// run executes the CLI and returns the process exit code. Success output (the
// exact-JSON result identity) is written to stdout; everything else, including
// the usage line and any error, goes to stderr.
func run(args []string, stdout, stderr io.Writer) int {
	if err := dispatch(context.Background(), args, stdout, stderr); err != nil {
		var suppressed suppressDiagnostic
		if !errors.As(err, &suppressed) {
			fmt.Fprintln(stderr, "conbench:", err)
		}
		if isUsage(err) {
			return 2
		}
		var coded exitCoder
		if errors.As(err, &coded) {
			return coded.ExitCode()
		}
		return 1
	}
	return 0
}

type exitCoder interface {
	ExitCode() int
}

func dispatch(ctx context.Context, args []string, stdout, stderr io.Writer) error {
	cmd := newRootCommand(stdout, stderr)
	cmd.SetArgs(args)
	cmd.SetOut(stdout)
	cmd.SetErr(stderr)
	err := cmd.ExecuteContext(ctx)
	if err != nil && !isUsage(err) && isCobraUsageError(err) {
		return commandUsageError(cmd, "%s", err)
	}
	return err
}

func newRootCommand(stdout, stderr io.Writer) *cobra.Command {
	cmd := configureCommand(&cobra.Command{
		Use:   "conbench",
		Short: "Conbench CLI",
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) > 0 {
				return commandUsageError(cmd, "unknown command %q", args[0])
			}
			return commandUsageError(cmd, "missing command")
		},
	})
	cmd.CompletionOptions.DisableDefaultCmd = true
	cmd.AddCommand(
		resultsCommand(stdout),
		compareCommand(stdout),
		seriesCommand(stdout),
		historyCommand(stdout),
		ciCommand(stdout),
		openAPICommand(stdout),
		authCommand(stdout, stderr),
		adminCommand(stdout, stderr),
		serveCommand(),
	)
	cmd.SetHelpCommand(helpCommand(cmd))
	return cmd
}

func helpCommand(root *cobra.Command) *cobra.Command {
	return configureCommand(&cobra.Command{
		Use:   "help [command]",
		Short: "Help about any command",
		Args: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 {
				return nil
			}
			target, remaining, err := root.Find(args)
			if err != nil || len(remaining) != 0 {
				return commandUsageError(cmd, "unknown help topic %q", strings.Join(args, " "))
			}
			if target == root && args[0] != root.Name() {
				return commandUsageError(cmd, "unknown help topic %q", strings.Join(args, " "))
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			target := root
			if len(args) > 0 {
				found, _, _ := root.Find(args)
				target = found
			}
			target.SetOut(cmd.OutOrStdout())
			target.SetErr(cmd.ErrOrStderr())
			return target.Help()
		},
	})
}

func resultsCommand(stdout io.Writer) *cobra.Command {
	cmd := groupCommand("results", "Read and submit benchmark results.")
	cmd.AddCommand(
		resultsSubmitCommand(stdout),
		resultsGetCommand(stdout),
	)
	return cmd
}

func seriesCommand(stdout io.Writer) *cobra.Command {
	cmd := groupCommand("series", "Browse benchmark series.")
	cmd.AddCommand(seriesListCommand(stdout))
	return cmd
}

func historyCommand(stdout io.Writer) *cobra.Command {
	cmd := groupCommand("history", "Export benchmark history.")
	cmd.AddCommand(historyExportCommand(stdout))
	return cmd
}

func ciCommand(stdout io.Writer) *cobra.Command {
	cmd := groupCommand("ci", "Generate CI benchmark reports.")
	cmd.AddCommand(ciReportCommand(stdout))
	return cmd
}

func openAPICommand(stdout io.Writer) *cobra.Command {
	var downgrade bool
	cmd := configureCommand(&cobra.Command{
		Use:   "openapi",
		Short: "Emit the Conbench OpenAPI document.",
		Args: func(cmd *cobra.Command, args []string) error {
			if len(args) != 0 {
				return commandUsageError(cmd, "unexpected argument %q", args[0])
			}
			return nil
		},
		RunE: func(*cobra.Command, []string) error {
			emit := server.OpenAPISpec
			if downgrade {
				emit = server.OpenAPISpec30
			}
			spec, err := emit()
			if err != nil {
				return err
			}
			_, err = stdout.Write(spec)
			return err
		},
	})
	cmd.Flags().BoolVar(&downgrade, "downgrade", false, "emit the OpenAPI 3.0 compatibility document")
	return cmd
}

func authCommand(stdout, stderr io.Writer) *cobra.Command {
	cmd := groupCommand("auth", "Authenticate and manage API tokens.")
	cmd.AddCommand(authLoginCommand(stdout, stderr))
	token := groupCommand("token", "Manage API tokens.")
	token.AddCommand(
		authTokenListCommand(stdout),
		authTokenRevokeCommand(stdout),
	)
	cmd.AddCommand(token)
	return cmd
}

func adminCommand(stdout, stderr io.Writer) *cobra.Command {
	cmd := groupCommand("admin", "Run trusted operations commands.")
	cmd.AddCommand(
		adminRepairCommand(stdout, stderr),
		adminProdCloneCommand(stdout, stderr),
	)
	alerts := groupCommand("alerts", "Run alert operations.")
	alerts.AddCommand(adminAlertsEvaluateCommand(stdout, stderr))
	alerts.AddCommand(adminAlertsDeliverCommand(stdout, stderr))
	cmd.AddCommand(alerts)
	return cmd
}

func adminProdCloneCommand(stdout, stderr io.Writer) *cobra.Command {
	cmd := groupCommand("prod-clone", "Run production-clone compatibility harness helpers.")
	cmd.AddCommand(
		prodCloneForwardCommand("safe-db-url", "Print the scrubbed production-clone database URL.", stdout, stderr),
		prodCloneForwardCommand(
			"preflight",
			"Validate the production-clone target and write count artifacts.",
			stdout,
			stderr,
			prodCloneStringFlag("out", prodCloneDefaultOutDir, "artifact output directory"),
			prodCloneOptionalStringFlag("json-out", "", "preflight JSON artifact path"),
			prodCloneOptionalStringFlag("counts-out", "", "counts JSON artifact path"),
			prodCloneBoolFlag("allow-dev-role", false, "allow the development role for non-acceptance dry runs"),
		),
		prodCloneForwardCommand(
			"compare-counts",
			"Compare before and after writable-table count artifacts.",
			stdout,
			stderr,
			prodCloneRequiredStringFlag("before", "before counts JSON path"),
			prodCloneRequiredStringFlag("after", "after counts JSON path"),
			prodCloneRequiredStringFlag("out", "count delta JSON output path"),
		),
		prodCloneForwardCommand(
			"samples",
			"Select sample result identifiers for compatibility probes.",
			stdout,
			stderr,
			prodCloneStringFlag("out", prodCloneDefaultOutDir, "artifact output directory"),
			prodCloneOptionalStringFlag("json-out", "", "samples JSON artifact path"),
			prodCloneBoolFlag("allow-dev-role", false, "allow the development role for non-acceptance dry runs"),
		),
		prodCloneForwardCommand(
			"api-probe",
			"Probe read-only API endpoints against selected samples.",
			stdout,
			stderr,
			prodCloneRequiredStringFlag("server", "server base URL"),
			prodCloneRequiredStringFlag("samples", "sample manifest JSON path"),
			prodCloneStringFlag("out", prodCloneDefaultOutDir, "artifact output directory"),
		),
		prodCloneForwardCommand(
			"profile",
			"Profile production-clone read paths against selected samples.",
			stdout,
			stderr,
			prodCloneRequiredStringFlag("server", "server base URL"),
			prodCloneRequiredStringFlag("samples", "sample manifest JSON path"),
			prodCloneStringFlag("out", prodCloneDefaultOutDir, "artifact output directory"),
		),
		prodCloneForwardCommand(
			"log-scan",
			"Scan server logs for blocked writes or read-only violations.",
			stdout,
			stderr,
			prodCloneRequiredStringFlag("log", "server log path"),
			prodCloneStringFlag("out", prodCloneDefaultOutDir, "artifact output directory"),
		),
		prodCloneForwardCommand(
			"report",
			"Render the production-clone compatibility report.",
			stdout,
			stderr,
			prodCloneStringFlag("out", prodCloneDefaultOutDir, "artifact output directory"),
			prodCloneBoolFlag("require-profile", false, "require SQL profile artifacts"),
		),
	)
	return cmd
}

const prodCloneDefaultOutDir = "var/prod-clone-compat"

type prodCloneFlagKind int

const (
	prodCloneFlagString prodCloneFlagKind = iota
	prodCloneFlagBool
)

type prodCloneFlagSpec struct {
	name          string
	defaultString string
	defaultBool   bool
	usage         string
	kind          prodCloneFlagKind
	required      bool
}

func prodCloneStringFlag(name, defaultValue, usage string) prodCloneFlagSpec {
	return prodCloneFlagSpec{name: name, defaultString: defaultValue, usage: usage, kind: prodCloneFlagString}
}

func prodCloneOptionalStringFlag(name, defaultValue, usage string) prodCloneFlagSpec {
	return prodCloneStringFlag(name, defaultValue, usage)
}

func prodCloneRequiredStringFlag(name, usage string) prodCloneFlagSpec {
	return prodCloneFlagSpec{name: name, usage: usage, kind: prodCloneFlagString, required: true}
}

func prodCloneBoolFlag(name string, defaultValue bool, usage string) prodCloneFlagSpec {
	return prodCloneFlagSpec{name: name, defaultBool: defaultValue, usage: usage, kind: prodCloneFlagBool}
}

func prodCloneForwardCommand(name, short string, stdout, stderr io.Writer, specs ...prodCloneFlagSpec) *cobra.Command {
	stringValues := make(map[string]*string, len(specs))
	boolValues := make(map[string]*bool, len(specs))
	cmd := configureCommand(&cobra.Command{
		Use:   name + " [options]",
		Short: short,
		Args: func(cmd *cobra.Command, args []string) error {
			if len(args) > 0 {
				return commandUsageError(cmd, "unexpected argument %q", args[0])
			}
			for _, spec := range specs {
				if spec.required && (!cmd.Flags().Changed(spec.name) || strings.TrimSpace(*stringValues[spec.name]) == "") {
					return commandUsageError(cmd, "--%s is required", spec.name)
				}
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			forwarded := make([]string, 0, len(args)+1)
			forwarded = append(forwarded, name)
			forwarded = appendProdCloneChangedFlags(forwarded, cmd.Flags(), specs, stringValues, boolValues)
			code := prodclone.Run("conbench admin prod-clone", forwarded, stdout, stderr)
			if code != 0 {
				return suppressedExitError{code: code}
			}
			return nil
		},
	})
	for _, spec := range specs {
		switch spec.kind {
		case prodCloneFlagString:
			stringValues[spec.name] = cmd.Flags().String(spec.name, spec.defaultString, spec.usage)
		case prodCloneFlagBool:
			boolValues[spec.name] = cmd.Flags().Bool(spec.name, spec.defaultBool, spec.usage)
		}
	}
	return cmd
}

func appendProdCloneChangedFlags(
	args []string,
	flags *pflag.FlagSet,
	specs []prodCloneFlagSpec,
	stringValues map[string]*string,
	boolValues map[string]*bool,
) []string {
	for _, spec := range specs {
		if !flags.Changed(spec.name) {
			continue
		}
		switch spec.kind {
		case prodCloneFlagString:
			args = append(args, "--"+spec.name, *stringValues[spec.name])
		case prodCloneFlagBool:
			args = append(args, fmt.Sprintf("--%s=%t", spec.name, *boolValues[spec.name]))
		}
	}
	return args
}

func serveCommand() *cobra.Command {
	return configureCommand(&cobra.Command{
		Use:   "serve",
		Short: "Run the Conbench API and dashboard server.",
		Args: func(cmd *cobra.Command, args []string) error {
			if len(args) != 0 {
				return commandUsageError(cmd, "unexpected argument %q", args[0])
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return serveRunner(cmd.Context())
		},
	})
}

func groupCommand(use string, short string) *cobra.Command {
	return configureCommand(&cobra.Command{
		Use:   use,
		Short: short,
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) > 0 {
				return commandUsageError(cmd, "unknown command %q", args[0])
			}
			return commandUsageError(cmd, "missing command")
		},
	})
}

func isCobraUsageError(err error) bool {
	var notExist *pflag.NotExistError
	var valueRequired *pflag.ValueRequiredError
	var invalidValue *pflag.InvalidValueError
	if errors.As(err, &notExist) || errors.As(err, &valueRequired) || errors.As(err, &invalidValue) {
		return true
	}

	msg := err.Error()
	return strings.HasPrefix(msg, "unknown command")
}
