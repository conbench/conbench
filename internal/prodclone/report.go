package prodclone

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"
)

type LogScanArtifact struct {
	Passed   bool         `json:"passed"`
	Error    string       `json:"error,omitempty"`
	Findings []LogFinding `json:"findings"`
}

type reportPreflightArtifact struct {
	Target             TargetInfo   `json:"target"`
	Policy             TargetPolicy `json:"policy"`
	Valid              bool         `json:"valid"`
	AcceptanceEligible bool         `json:"acceptance_eligible"`
	ValidationError    string       `json:"validation_error,omitempty"`
}

type reportArtifacts struct {
	preflight        reportPreflightArtifact
	havePreflight    bool
	samples          SampleManifest
	haveSamples      bool
	apiProbes        CompatibilityProbeArtifact
	haveAPIProbes    bool
	cliProbes        CompatibilityProbeArtifact
	haveCLIProbes    bool
	sdkProbes        CompatibilityProbeArtifact
	haveSDKProbes    bool
	logScan          LogScanArtifact
	haveLogScan      bool
	countComparison  CountComparison
	haveCounts       bool
	countsBefore     CountSnapshot
	haveCountsBefore bool
	countsAfter      CountSnapshot
	haveCountsAfter  bool
	httpTimings      []HTTPProbeTiming
	sqlTimings       []SQLProfileTiming
	relationSizes    []RelationSize
	haveRelationSize bool
}

type ReportValidationOptions struct {
	RequireProfile bool
}

func RenderCompatibilityReport(outDir string) ([]byte, error) {
	artifacts, err := loadReportArtifacts(outDir)
	if err != nil {
		return nil, err
	}

	var b strings.Builder
	b.WriteString("# Conbench Prod Clone Compatibility Report\n\n")
	renderEnvironmentSection(&b, artifacts)
	renderConnectionSafetySection(&b, artifacts)
	renderSampleSection(&b, artifacts)
	renderCompatibilitySection(&b, artifacts)
	renderBlockedWriteSection(&b, artifacts)
	renderLatencySection(&b, artifacts)
	renderPlansAndRisksSections(&b, artifacts)
	return []byte(b.String()), nil
}

func MissingMandatoryReportArtifacts(outDir string) ([]string, error) {
	artifacts, err := loadReportArtifacts(outDir)
	if err != nil {
		return nil, err
	}
	return missingMandatoryArtifacts(artifacts), nil
}

func ReportValidationIssues(outDir string) ([]string, error) {
	return ReportValidationIssuesWithOptions(outDir, ReportValidationOptions{})
}

func ReportValidationIssuesWithOptions(outDir string, opts ReportValidationOptions) ([]string, error) {
	artifacts, err := loadReportArtifacts(outDir)
	if err != nil {
		return nil, err
	}
	return reportValidationIssues(artifacts, opts), nil
}

func loadReportArtifacts(outDir string) (reportArtifacts, error) {
	var artifacts reportArtifacts
	var err error

	artifacts.havePreflight, err = readOptionalJSON(filepath.Join(outDir, "preflight.json"), &artifacts.preflight)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveSamples, err = readOptionalJSON(filepath.Join(outDir, "samples.json"), &artifacts.samples)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveAPIProbes, err = readOptionalJSON(filepath.Join(outDir, "api-probes.json"), &artifacts.apiProbes)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveCLIProbes, err = readOptionalJSON(filepath.Join(outDir, "cli-probes.json"), &artifacts.cliProbes)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveSDKProbes, err = readOptionalJSON(filepath.Join(outDir, "sdk-smoke.json"), &artifacts.sdkProbes)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveLogScan, err = readOptionalJSON(filepath.Join(outDir, "log-scan.json"), &artifacts.logScan)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveCounts, err = readOptionalJSON(filepath.Join(outDir, "count-delta.json"), &artifacts.countComparison)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveCountsBefore, err = readOptionalJSON(filepath.Join(outDir, "counts-before.json"), &artifacts.countsBefore)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveCountsAfter, err = readOptionalJSON(filepath.Join(outDir, "counts-after.json"), &artifacts.countsAfter)
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.httpTimings, err = readOptionalHTTPProbeTimings(filepath.Join(outDir, "timings", "http.jsonl"))
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.sqlTimings, err = readOptionalSQLProfileTimings(filepath.Join(outDir, "timings", "sql.jsonl"))
	if err != nil {
		return reportArtifacts{}, err
	}
	artifacts.haveRelationSize, err = readOptionalJSON(filepath.Join(outDir, "relation-sizes.json"), &artifacts.relationSizes)
	if err != nil {
		return reportArtifacts{}, err
	}
	return artifacts, nil
}

func renderEnvironmentSection(b *strings.Builder, artifacts reportArtifacts) {
	b.WriteString("## Environment and Clone\n\n")
	if !artifacts.havePreflight {
		b.WriteString("No preflight artifact found.\n\n")
		return
	}

	target := artifacts.preflight.Target
	fmt.Fprintf(b, "- Database: `%s`\n", target.Database)
	fmt.Fprintf(b, "- Host: `%s:%d`\n", target.Host, target.Port)
	fmt.Fprintf(b, "- User: `%s`\n", target.User)
	fmt.Fprintf(b, "- Schema tables observed: %d\n", len(target.SchemaTables))
	fmt.Fprintf(b, "- Preflight valid: %s\n", passFail(artifacts.preflight.Valid))
	fmt.Fprintf(b, "- Acceptance eligible: %s\n\n", passFail(artifacts.preflight.AcceptanceEligible))
	if artifacts.preflight.ValidationError != "" {
		fmt.Fprintf(b, "- Validation error: `%s`\n\n", sanitizeInline(artifacts.preflight.ValidationError))
	}
}

func renderConnectionSafetySection(b *strings.Builder, artifacts reportArtifacts) {
	b.WriteString("## Read-only Role and Connection Safety\n\n")
	if !artifacts.havePreflight {
		b.WriteString("No connection-safety artifact found.\n\n")
		return
	}

	target := artifacts.preflight.Target
	policy := artifacts.preflight.Policy
	fmt.Fprintf(b, "- Current role: `%s`\n", target.User)
	fmt.Fprintf(b, "- Expected read-only role: `%s`\n", emptyAsUnavailable(policy.ExpectedReadOnlyRole))
	fmt.Fprintf(b, "- Development role allowed: %t\n", policy.AllowDevRole)
	fmt.Fprintf(b, "- Superuser: %t\n", target.Superuser)
	fmt.Fprintf(b, "- default_transaction_read_only: %t\n", target.DefaultTransactionReadOnly)
	if len(target.WritableTablePrivileges) == 0 {
		b.WriteString("- Writable table privileges: none reported\n")
	} else {
		b.WriteString("- Writable table privileges: present\n")
	}
	if artifacts.haveCounts {
		fmt.Fprintf(b, "- Before/after writable-table count delta: %s\n", passFail(!artifacts.countComparison.Changed))
	}
	b.WriteString("\n")
}

func renderSampleSection(b *strings.Builder, artifacts reportArtifacts) {
	b.WriteString("## Sample Manifest\n\n")
	if !artifacts.haveSamples {
		b.WriteString("No sample manifest found.\n\n")
		return
	}

	if !artifacts.samples.GeneratedAt.IsZero() {
		fmt.Fprintf(b, "- Generated at: `%s`\n", artifacts.samples.GeneratedAt.UTC().Format("2006-01-02T15:04:05Z"))
	}
	if artifacts.samples.Compare != nil {
		fmt.Fprintf(
			b,
			"- Compare sample: `%s` vs `%s` on `%s`\n",
			artifacts.samples.Compare.BaselineResultID,
			artifacts.samples.Compare.ContenderResultID,
			artifacts.samples.Compare.HistoryFingerprint,
		)
	} else {
		b.WriteString("- Compare sample: not available\n")
	}
	if len(artifacts.samples.Warnings) > 0 {
		fmt.Fprintf(b, "- Warnings: %d\n", len(artifacts.samples.Warnings))
	}
	b.WriteString("\n")
	b.WriteString("| Category | Result ID | History fingerprint | Points | Note |\n")
	b.WriteString("| --- | --- | --- | ---: | --- |\n")
	for _, name := range sortedSampleCategoryNames(artifacts.samples.Categories) {
		category := artifacts.samples.Categories[name]
		fmt.Fprintf(
			b,
			"| %s | %s | %s | %d | %s |\n",
			mdCell(name),
			mdCell(category.ResultID),
			mdCell(category.HistoryFingerprint),
			category.PointCount,
			mdCell(category.Note),
		)
	}
	b.WriteString("\n")
}

func renderCompatibilitySection(b *strings.Builder, artifacts reportArtifacts) {
	b.WriteString("## Compatibility Results\n\n")
	probes := combinedProbeResults(artifacts)
	if len(probes) == 0 {
		b.WriteString("No API, CLI, or SDK probe artifacts found.\n\n")
		return
	}

	b.WriteString("| Surface | Probe | Result | Status | Operation | Error |\n")
	b.WriteString("| --- | --- | --- | ---: | --- | --- |\n")
	for _, probe := range probes {
		status := ""
		if probe.StatusCode != 0 {
			status = fmt.Sprintf("%d", probe.StatusCode)
		}
		fmt.Fprintf(
			b,
			"| %s | %s | %s | %s | %s | %s |\n",
			mdCell(probe.Surface),
			mdCell(probe.Name),
			passFail(probe.Passed),
			mdCell(status),
			mdCell(probe.Operation),
			mdCell(sanitizeReportMessage(probe.Error)),
		)
	}
	b.WriteString("\n")
}

func renderBlockedWriteSection(b *strings.Builder, artifacts reportArtifacts) {
	b.WriteString("## Blocked-write Log Scan\n\n")
	if !artifacts.haveLogScan {
		b.WriteString("No log-scan artifact found.\n\n")
		return
	}

	count := len(artifacts.logScan.Findings)
	fmt.Fprintf(b, "%d blocked-write %s found.\n\n", count, plural(count, "finding", "findings"))
	if artifacts.logScan.Error != "" {
		fmt.Fprintf(b, "Log-scan error: %s\n\n", mdCell(sanitizeReportMessage(artifacts.logScan.Error)))
	}
	if count == 0 {
		return
	}
	b.WriteString("| Line | Pattern | Excerpt |\n")
	b.WriteString("| ---: | --- | --- |\n")
	for _, finding := range artifacts.logScan.Findings {
		pattern := safeBlockedWritePattern(finding.Pattern)
		fmt.Fprintf(
			b,
			"| line %d | %s | %s |\n",
			finding.LineNumber,
			mdCell(pattern),
			mdCell(safeLogFindingLine(pattern)),
		)
	}
	b.WriteString("\n")
}

func renderLatencySection(b *strings.Builder, artifacts reportArtifacts) {
	b.WriteString("## Latency\n\n")
	if len(artifacts.httpTimings) == 0 {
		b.WriteString("No HTTP latency timings found.\n\n")
		return
	}

	b.WriteString("| Surface | Probe | Method | Path | Status | Duration ms | Result |\n")
	b.WriteString("| --- | --- | --- | --- | ---: | ---: | --- |\n")
	for _, timing := range artifacts.httpTimings {
		fmt.Fprintf(
			b,
			"| %s | %s | %s | %s | %d | %.2f | %s |\n",
			mdCell(timing.Surface),
			mdCell(timing.Name),
			mdCell(timing.Method),
			mdCell(timing.Path),
			timing.StatusCode,
			timing.DurationMS,
			passFail(timing.Passed),
		)
	}
	b.WriteString("\n")
}

func renderPlansAndRisksSections(b *strings.Builder, artifacts reportArtifacts) {
	b.WriteString("## Slowest SQL Plans\n\n")
	if len(artifacts.sqlTimings) == 0 {
		b.WriteString("SQL plan profiling has not been collected for this run.\n\n")
	} else {
		b.WriteString("| Query | Duration ms | Rows | Result | Plan |\n")
		b.WriteString("| --- | ---: | ---: | --- | --- |\n")
		for _, timing := range slowestSQLTimings(artifacts.sqlTimings, 10) {
			plan := ""
			if timing.ExplainFile != "" {
				plan = fmt.Sprintf("[`%s`](explain/%s)", mdCell(timing.ExplainFile), mdCell(timing.ExplainFile))
			}
			fmt.Fprintf(
				b,
				"| %s | %.2f | %d | %s | %s |\n",
				mdCell(timing.Name),
				timing.DurationMS,
				timing.RowCount,
				passFail(timing.Passed),
				plan,
			)
		}
		b.WriteString("\n")
	}
	if len(artifacts.relationSizes) > 0 {
		b.WriteString("### Relation Sizes\n\n")
		b.WriteString("| Table | Total bytes | Table bytes | Index bytes |\n")
		b.WriteString("| --- | ---: | ---: | ---: |\n")
		for _, size := range largestRelationSizes(artifacts.relationSizes, 12) {
			fmt.Fprintf(
				b,
				"| %s | %d | %d | %d |\n",
				mdCell(size.Table),
				size.TotalBytes,
				size.TableBytes,
				size.IndexBytes,
			)
		}
		b.WriteString("\n")
	}
	b.WriteString("## Risks for Phase 5\n\n")
	risks := reportRisks(artifacts)
	if len(risks) == 0 {
		b.WriteString("- No compatibility-report risk entries were generated by Task 4 artifacts.\n")
	} else {
		for _, risk := range risks {
			fmt.Fprintf(b, "- %s.\n", risk)
		}
	}
	b.WriteString("\n")
	b.WriteString("## Candidate Phase 6 Work Items\n\n")
	b.WriteString("- Revisit after profiling artifacts are collected.\n")
}

func reportRisks(artifacts reportArtifacts) []string {
	risks := reportValidationIssues(artifacts, ReportValidationOptions{})
	if artifacts.haveSamples && len(artifacts.samples.Warnings) > 0 {
		risks = append(risks, "Review sample manifest warnings before Phase 5")
	}
	return risks
}

func reportValidationIssues(artifacts reportArtifacts, opts ReportValidationOptions) []string {
	var issues []string
	if missing := missingMandatoryArtifacts(artifacts); len(missing) > 0 {
		issues = append(issues, "Collect mandatory compatibility artifacts: "+strings.Join(missing, ", "))
	}
	if artifacts.havePreflight {
		if !artifacts.preflight.Valid {
			issues = append(issues, "Resolve preflight validation failures before Phase 5")
		}
		if !artifacts.preflight.AcceptanceEligible {
			issues = append(issues, "Run the acceptance gate with the dedicated read-only role before Phase 5")
		}
	}
	if artifacts.haveSamples {
		if len(artifacts.samples.Categories) == 0 {
			issues = append(issues, "Collect a non-empty sample manifest before Phase 5")
		}
		if artifacts.samples.Compare == nil {
			issues = append(issues, "Restore or triage compare coverage before Phase 5")
		}
	}
	issues = append(issues, probeArtifactIssues("API", artifacts.haveAPIProbes, artifacts.apiProbes, expectedAPIProbeNames(artifacts))...)
	issues = append(issues, probeArtifactIssues("CLI", artifacts.haveCLIProbes, artifacts.cliProbes, expectedCLIProbeNames(artifacts))...)
	issues = append(issues, probeArtifactIssues("SDK", artifacts.haveSDKProbes, artifacts.sdkProbes, []string{"pytest sdk smoke"})...)
	if artifacts.haveLogScan {
		if !artifacts.logScan.Passed || len(artifacts.logScan.Findings) > 0 {
			issues = append(issues, "Investigate blocked write attempts before Phase 5")
		}
		if artifacts.logScan.Error != "" {
			issues = append(issues, "Investigate log-scan execution failures before Phase 5")
		}
	}
	if artifacts.haveCounts {
		if artifacts.countComparison.Tables == nil {
			issues = append(issues, "Collect count-delta evidence before Phase 5")
		}
		if artifacts.countComparison.Changed {
			issues = append(issues, "Investigate writable-table count deltas before Phase 5")
		}
	}
	if artifacts.haveCountsBefore && !completeCountSnapshotArtifact(artifacts.countsBefore) {
		issues = append(issues, "Collect complete before-count evidence before Phase 5")
	}
	if artifacts.haveCountsAfter && !completeCountSnapshotArtifact(artifacts.countsAfter) {
		issues = append(issues, "Collect complete after-count evidence before Phase 5")
	}
	if failedHTTPProbeTiming(artifacts.httpTimings) {
		issues = append(issues, "Investigate failed HTTP timing probes before Phase 5")
	}
	if failedSQLProfileTiming(artifacts.sqlTimings) {
		issues = append(issues, "Investigate failed SQL profile probes before Phase 5")
	}
	if opts.RequireProfile {
		if len(artifacts.sqlTimings) == 0 {
			issues = append(issues, "Collect SQL profile timing artifacts before accepting the profiled production-clone run")
		}
		if !hasExplainPlanTiming(artifacts.sqlTimings) {
			issues = append(issues, "Collect SQL EXPLAIN plan artifacts before accepting the profiled production-clone run")
		}
		if !artifacts.haveRelationSize || len(artifacts.relationSizes) == 0 {
			issues = append(issues, "Collect relation size artifacts before accepting the profiled production-clone run")
		}
	}
	return issues
}

func hasExplainPlanTiming(timings []SQLProfileTiming) bool {
	for _, timing := range timings {
		if timing.ExplainFile != "" && timing.Passed {
			return true
		}
	}
	return false
}

func missingMandatoryArtifacts(artifacts reportArtifacts) []string {
	var missing []string
	if !artifacts.havePreflight {
		missing = append(missing, "preflight.json")
	}
	if !artifacts.haveSamples {
		missing = append(missing, "samples.json")
	}
	if !artifacts.haveAPIProbes {
		missing = append(missing, "api-probes.json")
	}
	if !artifacts.haveCLIProbes {
		missing = append(missing, "cli-probes.json")
	}
	if !artifacts.haveSDKProbes {
		missing = append(missing, "sdk-smoke.json")
	}
	if !artifacts.haveLogScan {
		missing = append(missing, "log-scan.json")
	}
	if !artifacts.haveCounts {
		missing = append(missing, "count-delta.json")
	}
	if !artifacts.haveCountsBefore {
		missing = append(missing, "counts-before.json")
	}
	if !artifacts.haveCountsAfter {
		missing = append(missing, "counts-after.json")
	}
	if len(artifacts.httpTimings) == 0 {
		missing = append(missing, "timings/http.jsonl")
	}
	return missing
}

func probeArtifactIssues(surface string, haveArtifact bool, artifact CompatibilityProbeArtifact, expectedNames []string) []string {
	if !haveArtifact {
		return nil
	}
	var issues []string
	if len(artifact.Probes) == 0 {
		issues = append(issues, "Collect non-empty "+surface+" probe evidence before Phase 5")
	}
	if !artifact.Passed {
		issues = append(issues, "Investigate failed API, CLI, or SDK compatibility probes")
	}
	for _, probe := range artifact.Probes {
		if !probe.Passed {
			issues = append(issues, "Investigate failed API, CLI, or SDK compatibility probes")
			break
		}
	}
	if missing := missingProbeNames(artifact.Probes, expectedNames); len(missing) > 0 {
		issues = append(issues, "Collect complete "+surface+" probe evidence before Phase 5: missing "+strings.Join(missing, ", "))
	}
	return uniqueStrings(issues)
}

func expectedAPIProbeNames(artifacts reportArtifacts) []string {
	names := []string{
		"ListSeries",
		"ListBenchmarkResults",
		"GetBenchmarkResult",
		"GetHistoryForResult",
		"GetHistory",
	}
	if artifacts.haveSamples && artifacts.samples.Compare != nil {
		names = append(names, "CompareBenchmarkResults")
	}
	if artifacts.haveSamples && artifacts.samples.CIReport != nil {
		names = append(names, "CIReportByCommitRun")
	}
	return names
}

func expectedCLIProbeNames(artifacts reportArtifacts) []string {
	names := []string{
		"conbench results get",
		"conbench series list",
	}
	if artifacts.haveSamples && artifacts.samples.Compare != nil {
		names = append(names, "conbench compare")
	}
	return names
}

func missingProbeNames(probes []CompatibilityProbeResult, expectedNames []string) []string {
	seen := make(map[string]struct{}, len(probes))
	for _, probe := range probes {
		seen[probe.Name] = struct{}{}
	}
	var missing []string
	for _, name := range expectedNames {
		if _, ok := seen[name]; !ok {
			missing = append(missing, name)
		}
	}
	return missing
}

func completeCountSnapshotArtifact(snapshot CountSnapshot) bool {
	for _, table := range requiredCountedTableNames() {
		if _, ok := snapshot.WritableTableCounts[table]; !ok {
			return false
		}
	}
	return true
}

func failedHTTPProbeTiming(timings []HTTPProbeTiming) bool {
	for _, timing := range timings {
		if !timing.Passed {
			return true
		}
	}
	return false
}

func failedSQLProfileTiming(timings []SQLProfileTiming) bool {
	for _, timing := range timings {
		if !timing.Passed {
			return true
		}
	}
	return false
}

func uniqueStrings(values []string) []string {
	seen := map[string]struct{}{}
	result := make([]string, 0, len(values))
	for _, value := range values {
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		result = append(result, value)
	}
	return result
}

func readOptionalJSON(path string, dest any) (bool, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("read %s: %w", path, err)
	}
	if err := json.Unmarshal(data, dest); err != nil {
		return false, fmt.Errorf("decode %s: %w", path, err)
	}
	return true, nil
}

func readOptionalHTTPProbeTimings(path string) ([]HTTPProbeTiming, error) {
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	defer file.Close()

	var timings []HTTPProbeTiming
	scanner := bufio.NewScanner(file)
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var timing HTTPProbeTiming
		if err := json.Unmarshal([]byte(line), &timing); err != nil {
			return nil, fmt.Errorf("decode %s line %d: %w", path, lineNumber, err)
		}
		timings = append(timings, timing)
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	return timings, nil
}

func readOptionalSQLProfileTimings(path string) ([]SQLProfileTiming, error) {
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	defer file.Close()

	var timings []SQLProfileTiming
	scanner := bufio.NewScanner(file)
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var timing SQLProfileTiming
		if err := json.Unmarshal([]byte(line), &timing); err != nil {
			return nil, fmt.Errorf("decode %s line %d: %w", path, lineNumber, err)
		}
		timings = append(timings, timing)
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	return timings, nil
}

func slowestSQLTimings(timings []SQLProfileTiming, limit int) []SQLProfileTiming {
	filtered := make([]SQLProfileTiming, 0, len(timings))
	for _, timing := range timings {
		if strings.HasSuffix(timing.Name, " Explain") {
			continue
		}
		filtered = append(filtered, timing)
	}
	sort.SliceStable(filtered, func(i, j int) bool {
		return filtered[i].DurationMS > filtered[j].DurationMS
	})
	if len(filtered) > limit {
		return filtered[:limit]
	}
	return filtered
}

func largestRelationSizes(sizes []RelationSize, limit int) []RelationSize {
	sorted := append([]RelationSize(nil), sizes...)
	sort.SliceStable(sorted, func(i, j int) bool {
		return sorted[i].TotalBytes > sorted[j].TotalBytes
	})
	if len(sorted) > limit {
		return sorted[:limit]
	}
	return sorted
}

func combinedProbeResults(artifacts reportArtifacts) []CompatibilityProbeResult {
	var probes []CompatibilityProbeResult
	if artifacts.haveAPIProbes {
		probes = append(probes, withDefaultSurface(artifacts.apiProbes.Probes, "API")...)
	}
	if artifacts.haveCLIProbes {
		probes = append(probes, withDefaultSurface(artifacts.cliProbes.Probes, "CLI")...)
	}
	if artifacts.haveSDKProbes {
		probes = append(probes, withDefaultSurface(artifacts.sdkProbes.Probes, "SDK")...)
	}
	return probes
}

func withDefaultSurface(probes []CompatibilityProbeResult, surface string) []CompatibilityProbeResult {
	result := make([]CompatibilityProbeResult, 0, len(probes))
	for _, probe := range probes {
		if probe.Surface == "" {
			probe.Surface = surface
		}
		result = append(result, probe)
	}
	return result
}

func sortedSampleCategoryNames(categories map[string]SampleCategory) []string {
	names := make([]string, 0, len(categories))
	for name := range categories {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func passFail(ok bool) string {
	if ok {
		return "PASS"
	}
	return "FAIL"
}

func plural(count int, singular string, multiple string) string {
	if count == 1 {
		return singular
	}
	return multiple
}

func emptyAsUnavailable(value string) string {
	if value == "" {
		return "not set"
	}
	return value
}

func mdCell(value string) string {
	value = strings.ReplaceAll(value, "\n", " ")
	value = strings.ReplaceAll(value, "\r", " ")
	value = strings.ReplaceAll(value, "|", "\\|")
	if value == "" {
		return ""
	}
	return value
}

var (
	reportURLUserinfoPattern  = regexp.MustCompile(`([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@`)
	reportSensitiveKVPattern  = regexp.MustCompile(`(?i)(authorization|password|passwd|secret|token)(\s*[:=]\s*)("[^"]*"|'[^']*'|[^,\s|;]+)`)
	reportBearerTokenPattern  = regexp.MustCompile(`(?i)Bearer\s+[A-Za-z0-9._~+/\-]+=*`)
	reportWhitespacePattern   = regexp.MustCompile(`\s+`)
	maxReportMessageByteCount = 240
)

func sanitizeReportMessage(value string) string {
	value = strings.ReplaceAll(value, "\n", " ")
	value = strings.ReplaceAll(value, "\r", " ")
	value = reportURLUserinfoPattern.ReplaceAllString(value, "${1}<redacted>@")
	value = reportSensitiveKVPattern.ReplaceAllString(value, "${1}${2}<redacted>")
	value = reportBearerTokenPattern.ReplaceAllString(value, "Bearer <redacted>")
	value = reportWhitespacePattern.ReplaceAllString(value, " ")
	value = strings.TrimSpace(value)
	return truncateReportMessage(value, maxReportMessageByteCount)
}

func truncateReportMessage(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	cut := limit
	for cut > 0 && !utf8.RuneStart(value[cut]) {
		cut--
	}
	if cut == 0 {
		cut = limit
	}
	return value[:cut] + "..."
}

func sanitizeInline(value string) string {
	value = strings.ReplaceAll(value, "`", "'")
	value = strings.ReplaceAll(value, "\n", " ")
	value = strings.ReplaceAll(value, "\r", " ")
	return value
}
