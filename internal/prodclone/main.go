package prodclone

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	defaultCommandName = "conbench admin prod-clone"
	defaultOutputDir   = "var/prod-clone-compat"
)

var (
	openPGPool                 = pgxpool.New
	probeTarget                = ProbeTargetSafety
	selectSampleManifest       = SelectSampleManifest
	beginSampleReadOnlyQueryer = func(ctx context.Context, pool *pgxpool.Pool) (SampleQueryer, func(context.Context) error, error) {
		tx, err := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
		if err != nil {
			return nil, nil, err
		}
		return tx, tx.Rollback, nil
	}
	sampleManifestGeneratedAt = func() time.Time {
		return time.Now().UTC()
	}
)

type preflightArtifact struct {
	Target             TargetInfo   `json:"target"`
	Policy             TargetPolicy `json:"policy"`
	Valid              bool         `json:"valid"`
	AcceptanceEligible bool         `json:"acceptance_eligible"`
	ValidationError    string       `json:"validation_error,omitempty"`
}

// Run executes the production-clone compatibility harness using commandName in
// usage output. It returns a process-style exit code and writes all diagnostics
// itself.
func Run(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	if strings.TrimSpace(commandName) == "" {
		commandName = defaultCommandName
	}
	return runWithName(commandName, args, stdout, stderr)
}

func run(args []string, stdout io.Writer, stderr io.Writer) int {
	return Run(defaultCommandName, args, stdout, stderr)
}

func runWithName(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	if len(args) == 0 {
		printTopLevelUsage(commandName, stderr)
		return 2
	}

	switch args[0] {
	case "safe-db-url":
		return runSafeDBURL(commandName, args[1:], stdout, stderr)
	case "preflight":
		return runPreflight(commandName, args[1:], stdout, stderr)
	case "compare-counts":
		return runCompareCounts(commandName, args[1:], stdout, stderr)
	case "samples":
		return runSamples(commandName, args[1:], stdout, stderr)
	case "api-probe":
		return runAPIProbe(commandName, args[1:], stdout, stderr)
	case "profile":
		return runProfile(commandName, args[1:], stdout, stderr)
	case "log-scan":
		return runLogScan(commandName, args[1:], stdout, stderr)
	case "report":
		return runReport(commandName, args[1:], stdout, stderr)
	case "-h", "--help", "help":
		printTopLevelUsage(commandName, stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown command %q\n", args[0])
		printTopLevelUsage(commandName, stderr)
		return 2
	}
}

func runSafeDBURL(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	fs := newCommandFlagSet("safe-db-url", fmt.Sprintf("usage: %s safe-db-url\n", commandName), args, stdout, stderr)
	if err := fs.Parse(args); err != nil {
		return flagParseExitCode(err)
	}
	if fs.NArg() != 0 {
		fs.Usage()
		return 2
	}

	cfg, err := LoadConfig()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	safeDBURL, err := SafeDBURL(cfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	fmt.Fprintln(stdout, safeDBURL)
	return 0
}

func runPreflight(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	_ = stdout
	cfg, err := parsePreflightArgs(commandName, args, stdout, stderr)
	if err != nil {
		return flagParseExitCode(err)
	}

	prodCfg, err := LoadConfig()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	policy, err := preflightPolicy(prodCfg, cfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	safeDBURL, err := SafeDBURL(prodCfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	pool, err := pgxpool.New(ctx, safeDBURL)
	if err != nil {
		fmt.Fprintf(stderr, "open target database: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}
	defer pool.Close()

	info, err := ProbeTarget(ctx, pool)
	if err != nil {
		fmt.Fprintf(stderr, "probe target database: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}

	validationErr := ValidateTarget(info, policy)
	artifact := newPreflightArtifact(info, policy, validationErr)

	if err := writeJSONFile(cfg.jsonOut, artifact); err != nil {
		fmt.Fprintf(stderr, "write preflight artifact: %v\n", err)
		return 1
	}
	if err := writeJSONFile(cfg.countsOut, CountSnapshotFromTarget(info)); err != nil {
		fmt.Fprintf(stderr, "write counts artifact: %v\n", err)
		return 1
	}

	if validationErr != nil {
		fmt.Fprintf(stderr, "preflight failed: %v\n", validationErr)
		return 1
	}
	return 0
}

func runCompareCounts(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	_ = stdout
	cfg, err := parseCompareCountsArgs(commandName, args, stdout, stderr)
	if err != nil {
		return flagParseExitCode(err)
	}

	before, err := readCountSnapshot(cfg.before)
	if err != nil {
		fmt.Fprintf(stderr, "read before counts: %v\n", err)
		return 1
	}
	after, err := readCountSnapshot(cfg.after)
	if err != nil {
		fmt.Fprintf(stderr, "read after counts: %v\n", err)
		return 1
	}
	comparison, compareErr := CompareCountSnapshots(before, after)
	if err := writeJSONFile(cfg.out, comparison); err != nil {
		fmt.Fprintf(stderr, "write count delta artifact: %v\n", err)
		return 1
	}
	if compareErr != nil {
		fmt.Fprintln(stderr, compareErr)
		return 1
	}
	return 0
}

func runSamples(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	_ = stdout
	cfg, err := parseSamplesArgs(commandName, args, stdout, stderr)
	if err != nil {
		return flagParseExitCode(err)
	}

	prodCfg, err := LoadConfig()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	policy, err := samplesPolicy(prodCfg, cfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	safeDBURL, err := SafeDBURL(prodCfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}

	probeCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	pool, err := openPGPool(probeCtx, safeDBURL)
	if err != nil {
		fmt.Fprintf(stderr, "open target database: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}
	if pool != nil {
		defer pool.Close()
	}

	info, err := probeTarget(probeCtx, pool)
	if err != nil {
		fmt.Fprintf(stderr, "probe target database: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}
	if err := ValidateTarget(info, policy); err != nil {
		fmt.Fprintf(stderr, "samples preflight failed: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}
	cancel()

	sampleCtx, sampleCancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer sampleCancel()
	sampleDB, rollbackSampleDB, err := beginSampleReadOnlyQueryer(sampleCtx, pool)
	if err != nil {
		fmt.Fprintf(stderr, "begin read-only sample transaction: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}
	if rollbackSampleDB != nil {
		defer func() {
			_ = rollbackSampleDB(context.Background())
		}()
	}

	manifest, err := selectSampleManifest(sampleCtx, sampleDB, sampleManifestGeneratedAt())
	if err != nil {
		fmt.Fprintf(stderr, "select samples: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}
	if err := writeJSONFile(cfg.jsonOut, manifest); err != nil {
		fmt.Fprintf(stderr, "write samples artifact: %v\n", err)
		return 1
	}
	for _, warning := range manifest.Warnings {
		fmt.Fprintf(stderr, "warning: %s\n", warning)
	}
	return 0
}

func runAPIProbe(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	_ = stdout
	cfg, err := parseAPIProbeArgs(commandName, args, stdout, stderr)
	if err != nil {
		return flagParseExitCode(err)
	}

	manifest, err := readSampleManifest(cfg.samples)
	if err != nil {
		if writeErr := writeAPIProbeFailureArtifact(cfg.outDir, "ReadSampleManifest", "read samples artifact", "read samples artifact failed"); writeErr != nil {
			fmt.Fprintf(stderr, "write API probe artifact: %v\n", writeErr)
			return 1
		}
		if writeErr := writeJSONLinesFile(filepath.Join(cfg.outDir, "timings", "http.jsonl"), nil); writeErr != nil {
			fmt.Fprintf(stderr, "write HTTP timings: %v\n", writeErr)
			return 1
		}
		fmt.Fprintf(stderr, "read samples artifact: %v\n", err)
		return 1
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	artifact, timings, probeErr := RunAPIProbes(ctx, APIProbeConfig{
		ServerURL: cfg.server,
		Samples:   manifest,
	})
	if err := writeJSONFile(filepath.Join(cfg.outDir, "api-probes.json"), artifact); err != nil {
		fmt.Fprintf(stderr, "write API probe artifact: %v\n", err)
		return 1
	}
	if err := writeJSONLinesFile(filepath.Join(cfg.outDir, "timings", "http.jsonl"), timings); err != nil {
		fmt.Fprintf(stderr, "write HTTP timings: %v\n", err)
		return 1
	}
	if probeErr != nil {
		fmt.Fprintln(stderr, probeErr)
		return 1
	}
	return 0
}

func runLogScan(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	_ = stdout
	cfg, err := parseLogScanArgs(commandName, args, stdout, stderr)
	if err != nil {
		return flagParseExitCode(err)
	}

	file, err := os.Open(cfg.logPath)
	if err != nil {
		if writeErr := writeLogScanFailureArtifact(cfg.outDir, "open server log failed"); writeErr != nil {
			fmt.Fprintf(stderr, "write log-scan artifact: %v\n", writeErr)
			return 1
		}
		fmt.Fprintf(stderr, "open server log: %v\n", err)
		return 1
	}
	defer file.Close()

	findings, err := ScanServerLog(file)
	if err != nil {
		if writeErr := writeLogScanFailureArtifact(cfg.outDir, "scan server log failed"); writeErr != nil {
			fmt.Fprintf(stderr, "write log-scan artifact: %v\n", writeErr)
			return 1
		}
		fmt.Fprintf(stderr, "scan server log: %v\n", err)
		return 1
	}
	artifact := LogScanArtifact{
		Passed:   len(findings) == 0,
		Findings: findings,
	}
	if err := writeJSONFile(filepath.Join(cfg.outDir, "log-scan.json"), artifact); err != nil {
		fmt.Fprintf(stderr, "write log-scan artifact: %v\n", err)
		return 1
	}
	if len(findings) > 0 {
		fmt.Fprintf(stderr, "%d blocked-write findings found\n", len(findings))
		return 1
	}
	return 0
}

func runProfile(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	_ = stdout
	cfg, err := parseProfileArgs(commandName, args, stdout, stderr)
	if err != nil {
		return flagParseExitCode(err)
	}

	manifest, err := readSampleManifest(cfg.samples)
	if err != nil {
		fmt.Fprintf(stderr, "read samples artifact: %v\n", err)
		return 1
	}
	prodCfg, err := LoadConfig()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	safeDBURL, err := SafeDBURL(prodCfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()
	pool, err := openPGPool(ctx, safeDBURL)
	if err != nil {
		fmt.Fprintf(stderr, "open target database: %s\n", redactSensitiveError(err, prodCfg, safeDBURL))
		return 1
	}
	if pool != nil {
		defer pool.Close()
	}

	result, profileErr := RunProfile(ctx, ProfileConfig{
		ServerURL: cfg.server,
		Samples:   manifest,
		DB:        pool,
	})
	if err := writeJSONLinesFile(filepath.Join(cfg.outDir, "timings", "http.jsonl"), result.HTTPTimings); err != nil {
		fmt.Fprintf(stderr, "write HTTP profile timings: %v\n", err)
		return 1
	}
	if err := writeSQLProfileTimingsFile(filepath.Join(cfg.outDir, "timings", "sql.jsonl"), result.SQLTimings); err != nil {
		fmt.Fprintf(stderr, "write SQL profile timings: %v\n", err)
		return 1
	}
	if err := writeExplainPlanFiles(filepath.Join(cfg.outDir, "explain"), result.Plans); err != nil {
		fmt.Fprintf(stderr, "write SQL explain plans: %v\n", err)
		return 1
	}
	if err := writeJSONFile(filepath.Join(cfg.outDir, "relation-sizes.json"), result.RelationSizes); err != nil {
		fmt.Fprintf(stderr, "write relation sizes: %v\n", err)
		return 1
	}
	if profileErr != nil {
		fmt.Fprintln(stderr, profileErr)
		return 1
	}
	return 0
}

func writeAPIProbeFailureArtifact(outDir string, name string, operation string, message string) error {
	artifact := CompatibilityProbeArtifact{
		Passed: false,
		Probes: []CompatibilityProbeResult{
			{
				Surface:   "API",
				Name:      name,
				Operation: operation,
				Passed:    false,
				Error:     message,
			},
		},
	}
	return writeJSONFile(filepath.Join(outDir, "api-probes.json"), artifact)
}

func writeLogScanFailureArtifact(outDir string, message string) error {
	return writeJSONFile(filepath.Join(outDir, "log-scan.json"), LogScanArtifact{
		Passed:   false,
		Error:    message,
		Findings: []LogFinding{},
	})
}

func runReport(commandName string, args []string, stdout io.Writer, stderr io.Writer) int {
	_ = stdout
	cfg, err := parseReportArgs(commandName, args, stdout, stderr)
	if err != nil {
		return flagParseExitCode(err)
	}

	report, err := RenderCompatibilityReport(cfg.outDir)
	if err != nil {
		fmt.Fprintf(stderr, "render compatibility report: %v\n", err)
		return 1
	}
	if err := writeFile0600(filepath.Join(cfg.outDir, "compat-report.md"), report); err != nil {
		fmt.Fprintf(stderr, "write compatibility report: %v\n", err)
		return 1
	}
	issues, err := ReportValidationIssuesWithOptions(cfg.outDir, ReportValidationOptions{
		RequireProfile: cfg.requireProfile,
	})
	if err != nil {
		fmt.Fprintf(stderr, "validate compatibility report artifacts: %v\n", err)
		return 1
	}
	if len(issues) > 0 {
		fmt.Fprintf(stderr, "report validation failed: %s\n", strings.Join(issues, "; "))
		return 1
	}
	return 0
}

type preflightConfig struct {
	outDir       string
	jsonOut      string
	countsOut    string
	allowDevRole bool
}

func preflightPolicy(prodCfg Config, cliCfg preflightConfig) (TargetPolicy, error) {
	return targetPolicy(prodCfg, cliCfg.allowDevRole)
}

func samplesPolicy(prodCfg Config, cliCfg samplesConfig) (TargetPolicy, error) {
	return targetPolicy(prodCfg, cliCfg.allowDevRole)
}

func targetPolicy(prodCfg Config, allowDevRole bool) (TargetPolicy, error) {
	if !allowDevRole && prodCfg.ReadOnlyRole == "" {
		return TargetPolicy{}, fmt.Errorf("%s must be set unless --allow-dev-role is used", EnvReadOnlyRole)
	}
	return TargetPolicyFromConfig(prodCfg, allowDevRole)
}

func newPreflightArtifact(info TargetInfo, policy TargetPolicy, validationErr error) preflightArtifact {
	artifact := preflightArtifact{
		Target: info,
		Policy: policy,
		Valid:  validationErr == nil,
		AcceptanceEligible: validationErr == nil &&
			policy.ExpectedReadOnlyRole != "" &&
			info.User == policy.ExpectedReadOnlyRole &&
			info.User != policy.DevelopmentRole,
	}
	if validationErr != nil {
		artifact.ValidationError = validationErr.Error()
	}
	return artifact
}

func parsePreflightArgs(commandName string, args []string, stdout io.Writer, stderr io.Writer) (preflightConfig, error) {
	cfg := preflightConfig{outDir: defaultOutputDir}
	fs := newCommandFlagSet("preflight", fmt.Sprintf("usage: %s preflight [--out DIR] [--json-out FILE] [--counts-out FILE] [--allow-dev-role]\n", commandName), args, stdout, stderr)
	fs.StringVar(&cfg.outDir, "out", defaultOutputDir, "artifact output directory")
	fs.StringVar(&cfg.jsonOut, "json-out", "", "preflight JSON artifact path")
	fs.StringVar(&cfg.countsOut, "counts-out", "", "counts JSON artifact path")
	fs.BoolVar(&cfg.allowDevRole, "allow-dev-role", false, "allow the development role for non-acceptance dry runs")
	if err := fs.Parse(args); err != nil {
		return preflightConfig{}, err
	}
	if fs.NArg() != 0 {
		fs.Usage()
		return preflightConfig{}, errUsage
	}
	if cfg.jsonOut == "" {
		cfg.jsonOut = filepath.Join(cfg.outDir, "preflight.json")
	}
	if cfg.countsOut == "" {
		cfg.countsOut = filepath.Join(cfg.outDir, "counts-before.json")
	}
	return cfg, nil
}

type samplesConfig struct {
	outDir       string
	jsonOut      string
	allowDevRole bool
}

func parseSamplesArgs(commandName string, args []string, stdout io.Writer, stderr io.Writer) (samplesConfig, error) {
	cfg := samplesConfig{outDir: defaultOutputDir}
	fs := newCommandFlagSet("samples", fmt.Sprintf("usage: %s samples [--out DIR] [--json-out FILE] [--allow-dev-role]\n", commandName), args, stdout, stderr)
	fs.StringVar(&cfg.outDir, "out", defaultOutputDir, "artifact output directory")
	fs.StringVar(&cfg.jsonOut, "json-out", "", "samples JSON artifact path")
	fs.BoolVar(&cfg.allowDevRole, "allow-dev-role", false, "allow the development role for non-acceptance dry runs")
	if err := fs.Parse(args); err != nil {
		return samplesConfig{}, err
	}
	if fs.NArg() != 0 {
		fs.Usage()
		return samplesConfig{}, errUsage
	}
	if cfg.jsonOut == "" {
		cfg.jsonOut = filepath.Join(cfg.outDir, "samples.json")
	}
	return cfg, nil
}

type compareCountsConfig struct {
	before string
	after  string
	out    string
}

type apiProbeConfig struct {
	server  string
	samples string
	outDir  string
}

type profileConfig struct {
	server  string
	samples string
	outDir  string
}

type logScanConfig struct {
	logPath string
	outDir  string
}

type reportConfig struct {
	outDir         string
	requireProfile bool
}

func parseCompareCountsArgs(commandName string, args []string, stdout io.Writer, stderr io.Writer) (compareCountsConfig, error) {
	cfg := compareCountsConfig{}
	fs := newCommandFlagSet("compare-counts", fmt.Sprintf("usage: %s compare-counts --before FILE --after FILE --out FILE\n", commandName), args, stdout, stderr)
	fs.StringVar(&cfg.before, "before", "", "before counts JSON path")
	fs.StringVar(&cfg.after, "after", "", "after counts JSON path")
	fs.StringVar(&cfg.out, "out", "", "count delta JSON output path")
	if err := fs.Parse(args); err != nil {
		return compareCountsConfig{}, err
	}
	if fs.NArg() != 0 || cfg.before == "" || cfg.after == "" || cfg.out == "" {
		fs.Usage()
		return compareCountsConfig{}, errUsage
	}
	return cfg, nil
}

func parseAPIProbeArgs(commandName string, args []string, stdout io.Writer, stderr io.Writer) (apiProbeConfig, error) {
	cfg := apiProbeConfig{outDir: defaultOutputDir}
	fs := newCommandFlagSet("api-probe", fmt.Sprintf("usage: %s api-probe --server URL --samples FILE [--out DIR]\n", commandName), args, stdout, stderr)
	fs.StringVar(&cfg.server, "server", "", "server base URL")
	fs.StringVar(&cfg.samples, "samples", "", "sample manifest JSON path")
	fs.StringVar(&cfg.outDir, "out", defaultOutputDir, "artifact output directory")
	if err := fs.Parse(args); err != nil {
		return apiProbeConfig{}, err
	}
	if fs.NArg() != 0 || cfg.server == "" || cfg.samples == "" {
		fs.Usage()
		return apiProbeConfig{}, errUsage
	}
	return cfg, nil
}

func parseProfileArgs(commandName string, args []string, stdout io.Writer, stderr io.Writer) (profileConfig, error) {
	cfg := profileConfig{outDir: defaultOutputDir}
	fs := newCommandFlagSet("profile", fmt.Sprintf("usage: %s profile --server URL --samples FILE [--out DIR]\n", commandName), args, stdout, stderr)
	fs.StringVar(&cfg.server, "server", "", "server base URL")
	fs.StringVar(&cfg.samples, "samples", "", "sample manifest JSON path")
	fs.StringVar(&cfg.outDir, "out", defaultOutputDir, "artifact output directory")
	if err := fs.Parse(args); err != nil {
		return profileConfig{}, err
	}
	if fs.NArg() != 0 || cfg.server == "" || cfg.samples == "" {
		fs.Usage()
		return profileConfig{}, errUsage
	}
	return cfg, nil
}

func parseLogScanArgs(commandName string, args []string, stdout io.Writer, stderr io.Writer) (logScanConfig, error) {
	cfg := logScanConfig{outDir: defaultOutputDir}
	fs := newCommandFlagSet("log-scan", fmt.Sprintf("usage: %s log-scan --log FILE [--out DIR]\n", commandName), args, stdout, stderr)
	fs.StringVar(&cfg.logPath, "log", "", "server log path")
	fs.StringVar(&cfg.outDir, "out", defaultOutputDir, "artifact output directory")
	if err := fs.Parse(args); err != nil {
		return logScanConfig{}, err
	}
	if fs.NArg() != 0 || cfg.logPath == "" {
		fs.Usage()
		return logScanConfig{}, errUsage
	}
	return cfg, nil
}

func parseReportArgs(commandName string, args []string, stdout io.Writer, stderr io.Writer) (reportConfig, error) {
	cfg := reportConfig{outDir: defaultOutputDir}
	fs := newCommandFlagSet("report", fmt.Sprintf("usage: %s report [--out DIR] [--require-profile]\n", commandName), args, stdout, stderr)
	fs.StringVar(&cfg.outDir, "out", defaultOutputDir, "artifact output directory")
	fs.BoolVar(&cfg.requireProfile, "require-profile", false, "require SQL profile artifacts")
	if err := fs.Parse(args); err != nil {
		return reportConfig{}, err
	}
	if fs.NArg() != 0 {
		fs.Usage()
		return reportConfig{}, errUsage
	}
	return cfg, nil
}

var errUsage = errors.New("usage error")

func flagParseExitCode(err error) int {
	if err == nil {
		return 0
	}
	if errors.Is(err, flag.ErrHelp) {
		return 0
	}
	return 2
}

func newCommandFlagSet(name string, usage string, args []string, stdout io.Writer, stderr io.Writer) *flag.FlagSet {
	output := stderr
	if hasHelpFlag(args) {
		output = stdout
	}
	fs := flag.NewFlagSet(name, flag.ContinueOnError)
	fs.SetOutput(output)
	fs.Usage = func() {
		fmt.Fprint(output, usage)
	}
	return fs
}

func hasHelpFlag(args []string) bool {
	for _, arg := range args {
		if arg == "-h" || arg == "--help" {
			return true
		}
	}
	return false
}

func printTopLevelUsage(commandName string, w io.Writer) {
	fmt.Fprintf(w, "usage: %s <safe-db-url|preflight|compare-counts|samples|api-probe|profile|log-scan|report> [options]\n", commandName)
}

func readSampleManifest(path string) (SampleManifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return SampleManifest{}, err
	}
	var manifest SampleManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return SampleManifest{}, err
	}
	return manifest, nil
}

func readCountSnapshot(path string) (CountSnapshot, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return CountSnapshot{}, err
	}
	var snapshot CountSnapshot
	if err := json.Unmarshal(data, &snapshot); err != nil {
		return CountSnapshot{}, err
	}
	return snapshot, nil
}

func writeJSONFile(path string, value any) error {
	if path == "" {
		return errors.New("output path is required")
	}
	dir := filepath.Dir(path)
	if dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return writeFile0600(path, data)
}

func writeJSONLinesFile(path string, values []HTTPProbeTiming) error {
	if path == "" {
		return errors.New("output path is required")
	}
	dir := filepath.Dir(path)
	if dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	defer file.Close()
	if err := file.Chmod(0o600); err != nil {
		return err
	}

	for _, value := range values {
		data, err := json.Marshal(value)
		if err != nil {
			return err
		}
		if _, err := file.Write(data); err != nil {
			return err
		}
		if _, err := file.Write([]byte("\n")); err != nil {
			return err
		}
	}
	return nil
}

func writeSQLProfileTimingsFile(path string, values []SQLProfileTiming) error {
	if path == "" {
		return errors.New("output path is required")
	}
	dir := filepath.Dir(path)
	if dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	defer file.Close()
	if err := file.Chmod(0o600); err != nil {
		return err
	}

	for _, value := range values {
		data, err := json.Marshal(value)
		if err != nil {
			return err
		}
		if _, err := file.Write(data); err != nil {
			return err
		}
		if _, err := file.Write([]byte("\n")); err != nil {
			return err
		}
	}
	return nil
}

func writeExplainPlanFiles(dir string, plans []ExplainPlanArtifact) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	for _, plan := range plans {
		data := append([]byte(nil), plan.PlanJSON...)
		data = append(data, '\n')
		if err := writeFile0600(filepath.Join(dir, plan.Filename), data); err != nil {
			return err
		}
	}
	return nil
}

func writeFile0600(path string, data []byte) error {
	if path == "" {
		return errors.New("output path is required")
	}
	dir := filepath.Dir(path)
	if dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	if _, err := os.Stat(path); err == nil {
		if err := os.Chmod(path, 0o600); err != nil {
			return err
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	defer file.Close()
	if err := file.Chmod(0o600); err != nil {
		return err
	}
	if _, err := file.Write(data); err != nil {
		return err
	}
	return nil
}

func redactSensitiveError(err error, cfg Config, safeDBURL string) string {
	message := err.Error()
	for _, secret := range dbURLSecrets(cfg.RawDBURL, safeDBURL) {
		message = strings.ReplaceAll(message, secret, "<redacted>")
	}
	return message
}

func dbURLSecrets(rawDBURL string, safeDBURL string) []string {
	candidates := []string{rawDBURL, safeDBURL}
	for _, value := range []string{rawDBURL, safeDBURL} {
		parsed, err := url.Parse(value)
		if err != nil || parsed.User == nil {
			continue
		}
		if password, ok := parsed.User.Password(); ok && password != "" {
			candidates = append(candidates, password)
		}
	}

	secrets := candidates[:0]
	seen := map[string]struct{}{}
	for _, candidate := range candidates {
		if candidate == "" {
			continue
		}
		if _, ok := seen[candidate]; ok {
			continue
		}
		seen[candidate] = struct{}{}
		secrets = append(secrets, candidate)
	}
	return secrets
}
