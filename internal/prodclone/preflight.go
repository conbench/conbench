package prodclone

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"maps"
	"slices"
	"sort"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	defaultTargetPort            = 5432
	defaultTargetDevelopmentRole = "conbench_dev"
)

var requiredSchemaTables = []string{
	"benchmark_result",
	"case",
	"context",
	"info",
	"hardware",
	"commit",
	"user",
}

var writableTableSpecs = []writableTableSpec{
	{name: "public.benchmark_result", schemaName: "benchmark_result", regclass: "public.benchmark_result", required: true},
	{name: `public."case"`, schemaName: "case", regclass: `public."case"`, countSQL: `SELECT count(*) FROM public."case"`, required: true},
	{name: "public.context", schemaName: "context", regclass: "public.context", countSQL: "SELECT count(*) FROM public.context", required: true},
	{name: "public.info", schemaName: "info", regclass: "public.info", countSQL: "SELECT count(*) FROM public.info", required: true},
	{name: "public.hardware", schemaName: "hardware", regclass: "public.hardware", countSQL: "SELECT count(*) FROM public.hardware", required: true},
	{name: "public.commit", schemaName: "commit", regclass: "public.commit", countSQL: "SELECT count(*) FROM public.commit", required: true},
	{name: "public.api_token", schemaName: "api_token", regclass: "public.api_token", countSQL: "SELECT count(*) FROM public.api_token"},
	{name: `public."user"`, schemaName: "user", regclass: `public."user"`, countSQL: `SELECT count(*) FROM public."user"`, required: true},
}

var writablePrivileges = []string{"INSERT", "UPDATE", "DELETE", "TRUNCATE"}

type writableTableSpec struct {
	name       string
	schemaName string
	regclass   string
	countSQL   string
	required   bool
}

type TargetInfo struct {
	Database                   string              `json:"database"`
	User                       string              `json:"user"`
	Host                       string              `json:"host"`
	Port                       int                 `json:"port"`
	Superuser                  bool                `json:"superuser"`
	DefaultTransactionReadOnly bool                `json:"default_transaction_read_only"`
	SchemaTables               []string            `json:"schema_tables"`
	WritableTableCounts        map[string]int64    `json:"writable_table_counts"`
	WritableTablePrivileges    map[string][]string `json:"writable_table_privileges"`
}

type TargetPolicy struct {
	ExpectedDatabase     string   `json:"expected_database"`
	ExpectedHosts        []string `json:"expected_hosts"`
	ExpectedPort         int      `json:"expected_port"`
	DevelopmentRole      string   `json:"development_role"`
	ExpectedReadOnlyRole string   `json:"expected_read_only_role,omitempty"`
	RequireReadOnlyRole  bool     `json:"require_read_only_role"`
	AllowDevRole         bool     `json:"allow_dev_role"`
}

type CountSnapshot struct {
	WritableTableCounts map[string]int64 `json:"writable_table_counts"`
}

type CountComparison struct {
	Changed bool              `json:"changed"`
	Tables  []TableCountDelta `json:"tables"`
}

type TableCountDelta struct {
	Table         string `json:"table"`
	Before        int64  `json:"before"`
	After         int64  `json:"after"`
	Delta         int64  `json:"delta"`
	BeforePresent bool   `json:"before_present"`
	AfterPresent  bool   `json:"after_present"`
}

func DefaultTargetPolicy() TargetPolicy {
	return TargetPolicy{
		ExpectedPort:        defaultTargetPort,
		DevelopmentRole:     defaultTargetDevelopmentRole,
		RequireReadOnlyRole: true,
	}
}

func ValidateTarget(info TargetInfo, policy TargetPolicy) error {
	policy = normalizeTargetPolicy(policy)

	var errs []error
	if policy.ExpectedDatabase != "" && info.Database != policy.ExpectedDatabase {
		errs = append(errs, fmt.Errorf("target database must be %q, got %q", policy.ExpectedDatabase, info.Database))
	}
	if len(policy.ExpectedHosts) > 0 && !matchesExpectedHost(info.Host, policy.ExpectedHosts) {
		errs = append(errs, fmt.Errorf("target host must be one of %s, got %q", strings.Join(policy.ExpectedHosts, ", "), info.Host))
	}
	if info.Port != policy.ExpectedPort {
		errs = append(errs, fmt.Errorf("target port must be %d, got %d", policy.ExpectedPort, info.Port))
	}
	if info.User == "" {
		errs = append(errs, errors.New("target user must be set"))
	}
	devRoleDryRun := policy.AllowDevRole && info.User == policy.DevelopmentRole
	if policy.RequireReadOnlyRole && info.User == policy.DevelopmentRole && !policy.AllowDevRole {
		errs = append(errs, fmt.Errorf("target user must be a dedicated read-only role, got development role %q", info.User))
	}
	if policy.RequireReadOnlyRole && !devRoleDryRun && policy.ExpectedReadOnlyRole != "" && info.User != policy.ExpectedReadOnlyRole {
		errs = append(errs, fmt.Errorf("target user must be expected read-only role %q, got %q", policy.ExpectedReadOnlyRole, info.User))
	}
	if policy.RequireReadOnlyRole && !devRoleDryRun {
		for table, privileges := range info.WritableTablePrivileges {
			if len(privileges) > 0 {
				errs = append(errs, fmt.Errorf("target user must be read-only; %q has writable privileges on %s: %s", info.User, table, strings.Join(privileges, ", ")))
			}
		}
	}
	if info.Superuser {
		errs = append(errs, fmt.Errorf("target user %q must not be a superuser", info.User))
	}
	if !info.DefaultTransactionReadOnly {
		errs = append(errs, errors.New("default_transaction_read_only must be on"))
	}
	for _, table := range missingRequiredTables(info.SchemaTables) {
		errs = append(errs, fmt.Errorf("required schema table %q is missing", table))
	}

	return errors.Join(errs...)
}

func ProbeTarget(ctx context.Context, pool *pgxpool.Pool) (TargetInfo, error) {
	tx, err := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
	if err != nil {
		return TargetInfo{}, fmt.Errorf("begin read-only probe transaction: %w", err)
	}
	defer func() {
		_ = tx.Rollback(ctx)
	}()

	info, err := probeTargetIdentity(ctx, tx)
	if err != nil {
		return TargetInfo{}, err
	}
	if err := probeSchemaTables(ctx, tx, &info); err != nil {
		return TargetInfo{}, err
	}
	if err := probeWritableTableCounts(ctx, tx, &info); err != nil {
		return TargetInfo{}, err
	}
	if err := probeWritableTablePrivileges(ctx, tx, &info); err != nil {
		return TargetInfo{}, err
	}
	return info, nil
}

func ProbeTargetSafety(ctx context.Context, pool *pgxpool.Pool) (TargetInfo, error) {
	tx, err := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
	if err != nil {
		return TargetInfo{}, fmt.Errorf("begin read-only probe transaction: %w", err)
	}
	defer func() {
		_ = tx.Rollback(ctx)
	}()

	info, err := probeTargetIdentity(ctx, tx)
	if err != nil {
		return TargetInfo{}, err
	}
	if err := probeSchemaTables(ctx, tx, &info); err != nil {
		return TargetInfo{}, err
	}
	if err := probeWritableTablePrivileges(ctx, tx, &info); err != nil {
		return TargetInfo{}, err
	}
	return info, nil
}

func CountSnapshotFromTarget(info TargetInfo) CountSnapshot {
	return CountSnapshot{WritableTableCounts: cloneCounts(info.WritableTableCounts)}
}

func CompareCountSnapshots(before CountSnapshot, after CountSnapshot) (CountComparison, error) {
	comparison := compareCountSnapshotShape(before, after)
	if comparison.Changed {
		return comparison, fmt.Errorf("count snapshot malformed: %d table issue(s)", len(comparison.Tables))
	}

	for _, table := range expectedCountedTableNames() {
		beforeCount, beforePresent := before.WritableTableCounts[table]
		afterCount, afterPresent := after.WritableTableCounts[table]
		if !beforePresent && !afterPresent {
			continue
		}
		if beforePresent == afterPresent && beforeCount == afterCount {
			continue
		}
		comparison.Tables = append(comparison.Tables, TableCountDelta{
			Table:         table,
			Before:        beforeCount,
			After:         afterCount,
			Delta:         afterCount - beforeCount,
			BeforePresent: beforePresent,
			AfterPresent:  afterPresent,
		})
	}
	comparison.Changed = len(comparison.Tables) > 0
	if comparison.Changed {
		return comparison, fmt.Errorf("count mismatch for %d writable table(s)", len(comparison.Tables))
	}
	return comparison, nil
}

func normalizeTargetPolicy(policy TargetPolicy) TargetPolicy {
	defaults := DefaultTargetPolicy()
	if policy.ExpectedPort == 0 {
		policy.ExpectedPort = defaults.ExpectedPort
	}
	if policy.DevelopmentRole == "" {
		policy.DevelopmentRole = defaults.DevelopmentRole
	}
	policy.RequireReadOnlyRole = true
	return policy
}

func compareCountSnapshotShape(before CountSnapshot, after CountSnapshot) CountComparison {
	expected := expectedCountedTableSet()
	comparison := CountComparison{Tables: []TableCountDelta{}}

	for _, table := range writableTableSpecs {
		if table.countSQL == "" {
			continue
		}
		beforeCount, beforePresent := before.WritableTableCounts[table.name]
		afterCount, afterPresent := after.WritableTableCounts[table.name]
		if beforePresent && afterPresent {
			continue
		}
		if !table.required && !beforePresent && !afterPresent {
			continue
		}
		comparison.Tables = append(comparison.Tables, TableCountDelta{
			Table:         table.name,
			Before:        beforeCount,
			After:         afterCount,
			Delta:         afterCount - beforeCount,
			BeforePresent: beforePresent,
			AfterPresent:  afterPresent,
		})
	}

	for _, table := range unknownCountTables(before, after, expected) {
		beforeCount, beforePresent := before.WritableTableCounts[table]
		afterCount, afterPresent := after.WritableTableCounts[table]
		comparison.Tables = append(comparison.Tables, TableCountDelta{
			Table:         table,
			Before:        beforeCount,
			After:         afterCount,
			Delta:         afterCount - beforeCount,
			BeforePresent: beforePresent,
			AfterPresent:  afterPresent,
		})
	}

	comparison.Changed = len(comparison.Tables) > 0
	return comparison
}

func expectedCountedTableNames() []string {
	names := make([]string, 0, len(writableTableSpecs))
	for _, table := range writableTableSpecs {
		if table.countSQL == "" {
			continue
		}
		names = append(names, table.name)
	}
	return names
}

func requiredCountedTableNames() []string {
	names := make([]string, 0, len(writableTableSpecs))
	for _, table := range writableTableSpecs {
		if table.countSQL == "" {
			continue
		}
		if table.required {
			names = append(names, table.name)
		}
	}
	return names
}

func expectedCountedTableSet() map[string]struct{} {
	expected := make(map[string]struct{}, len(writableTableSpecs))
	for _, table := range writableTableSpecs {
		if table.countSQL == "" {
			continue
		}
		expected[table.name] = struct{}{}
	}
	return expected
}

func unknownCountTables(before CountSnapshot, after CountSnapshot, expected map[string]struct{}) []string {
	unknown := make(map[string]struct{})
	for table := range before.WritableTableCounts {
		if _, ok := expected[table]; !ok {
			unknown[table] = struct{}{}
		}
	}
	for table := range after.WritableTableCounts {
		if _, ok := expected[table]; !ok {
			unknown[table] = struct{}{}
		}
	}

	names := make([]string, 0, len(unknown))
	for table := range unknown {
		names = append(names, table)
	}
	sort.Strings(names)
	return names
}

func matchesExpectedHost(host string, expected []string) bool {
	host = normalizePostgresHost(host)
	for _, candidate := range expected {
		if strings.EqualFold(host, normalizePostgresHost(candidate)) {
			return true
		}
	}
	return false
}

func normalizePostgresHost(host string) string {
	value, _, found := strings.Cut(host, "/")
	if found {
		return value
	}
	return host
}

func missingRequiredTables(schemaTables []string) []string {
	present := make(map[string]struct{}, len(schemaTables))
	for _, table := range schemaTables {
		present[table] = struct{}{}
	}

	var missing []string
	for _, table := range requiredSchemaTables {
		if _, ok := present[table]; !ok {
			missing = append(missing, table)
		}
	}
	return missing
}

func probeTargetIdentity(ctx context.Context, tx pgx.Tx) (TargetInfo, error) {
	var readOnlySetting string
	info := TargetInfo{}
	err := tx.QueryRow(ctx, `
SELECT
	current_database(),
	current_user,
	COALESCE(inet_server_addr()::text, ''),
	COALESCE(inet_server_port(), 0),
	current_setting('default_transaction_read_only'),
	pg_roles.rolsuper
FROM pg_roles
WHERE pg_roles.rolname = current_user
`).Scan(&info.Database, &info.User, &info.Host, &info.Port, &readOnlySetting, &info.Superuser)
	if err != nil {
		return TargetInfo{}, fmt.Errorf("probe target identity: %w", err)
	}
	info.DefaultTransactionReadOnly = parsePostgresBoolSetting(readOnlySetting)
	return info, nil
}

func probeSchemaTables(ctx context.Context, tx pgx.Tx, info *TargetInfo) error {
	for _, table := range writableTableSpecs {
		var regclass sql.NullString
		if err := tx.QueryRow(ctx, `SELECT to_regclass($1)::text`, table.regclass).Scan(&regclass); err != nil {
			return fmt.Errorf("probe schema table %s: %w", table.name, err)
		}
		if regclass.Valid {
			info.SchemaTables = append(info.SchemaTables, table.schemaName)
		}
	}
	slices.Sort(info.SchemaTables)
	return nil
}

func probeWritableTableCounts(ctx context.Context, tx pgx.Tx, info *TargetInfo) error {
	info.WritableTableCounts = make(map[string]int64, len(writableTableSpecs))
	for _, table := range writableTableSpecs {
		if !schemaTablePresent(info.SchemaTables, table.schemaName) {
			continue
		}
		if table.countSQL == "" {
			continue
		}
		var count int64
		if err := tx.QueryRow(ctx, table.countSQL).Scan(&count); err != nil {
			return fmt.Errorf("count writable table %s: %w", table.name, err)
		}
		info.WritableTableCounts[table.name] = count
	}
	return nil
}

func probeWritableTablePrivileges(ctx context.Context, tx pgx.Tx, info *TargetInfo) error {
	info.WritableTablePrivileges = make(map[string][]string, len(writableTableSpecs))
	for _, table := range writableTableSpecs {
		if !schemaTablePresent(info.SchemaTables, table.schemaName) {
			continue
		}
		for _, privilege := range writablePrivileges {
			var allowed bool
			if err := tx.QueryRow(ctx, `SELECT has_table_privilege(current_user, $1::regclass, $2)`, table.regclass, privilege).Scan(&allowed); err != nil {
				return fmt.Errorf("probe writable privilege %s on %s: %w", privilege, table.name, err)
			}
			if allowed {
				info.WritableTablePrivileges[table.name] = append(info.WritableTablePrivileges[table.name], privilege)
			}
		}
	}
	return nil
}

func schemaTablePresent(schemaTables []string, table string) bool {
	return slices.Contains(schemaTables, table)
}

func parsePostgresBoolSetting(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "on", "true", "t", "1", "yes":
		return true
	default:
		return false
	}
}

func cloneCounts(counts map[string]int64) map[string]int64 {
	if counts == nil {
		return nil
	}
	cloned := make(map[string]int64, len(counts))
	maps.Copy(cloned, counts)
	return cloned
}
