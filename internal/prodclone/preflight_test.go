package prodclone

import (
	"testing"

	"github.com/conbench/conbench/internal/dbtest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func validTargetInfo() TargetInfo {
	return TargetInfo{
		Database:                   "conbench_prod",
		User:                       "conbench_readonly",
		Host:                       "192.0.2.10",
		Port:                       5432,
		Superuser:                  false,
		DefaultTransactionReadOnly: true,
		SchemaTables:               []string{"benchmark_result", "case", "context", "info", "hardware", "commit", "api_token", "user"},
		WritableTablePrivileges:    map[string][]string{},
	}
}

func validTargetPolicy() TargetPolicy {
	policy := DefaultTargetPolicy()
	policy.ExpectedDatabase = "conbench_prod"
	policy.ExpectedHosts = []string{"clone-db.example", "192.0.2.10"}
	return policy
}

func TestValidateTargetRejectsWrongDatabase(t *testing.T) {
	info := validTargetInfo()
	info.Database = "postgres"

	err := ValidateTarget(info, validTargetPolicy())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "conbench_prod")
}

func TestValidateTargetAcceptsDedicatedReadOnlyRole(t *testing.T) {
	info := validTargetInfo()

	require.NoError(t, ValidateTarget(info, validTargetPolicy()))
}

func TestValidateTargetAcceptsMissingOptionalAPITokenTable(t *testing.T) {
	info := validTargetInfo()
	info.SchemaTables = []string{"benchmark_result", "case", "context", "info", "hardware", "commit", "user"}

	require.NoError(t, ValidateTarget(info, validTargetPolicy()))
}

func TestValidateTargetRejectsUnexpectedReadOnlyRole(t *testing.T) {
	info := validTargetInfo()
	info.User = "conbench_other_ro"
	policy := validTargetPolicy()
	policy.ExpectedReadOnlyRole = "conbench_readonly"

	err := ValidateTarget(info, policy)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "conbench_readonly")
	assert.Contains(t, err.Error(), "conbench_other_ro")
}

func TestValidateTargetAcceptsExpectedReadOnlyRole(t *testing.T) {
	info := validTargetInfo()
	policy := validTargetPolicy()
	policy.ExpectedReadOnlyRole = "conbench_readonly"

	require.NoError(t, ValidateTarget(info, policy))
}

func TestValidateTargetAcceptsCIDRFormattedServerAddress(t *testing.T) {
	info := validTargetInfo()
	info.Host = "192.0.2.10/32"

	require.NoError(t, ValidateTarget(info, validTargetPolicy()))
}

func TestValidateTargetZeroPolicyRequiresReadOnlyRole(t *testing.T) {
	info := validTargetInfo()
	info.User = "conbench_dev"

	err := ValidateTarget(info, TargetPolicy{})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "read-only")
}

func TestValidateTargetRejectsWritablePrivilegeForReadOnlyRole(t *testing.T) {
	for _, privilege := range []string{"INSERT", "UPDATE"} {
		t.Run(privilege, func(t *testing.T) {
			info := validTargetInfo()
			info.WritableTablePrivileges = map[string][]string{"public.benchmark_result": {privilege}}

			err := ValidateTarget(info, validTargetPolicy())
			require.Error(t, err)
			assert.Contains(t, err.Error(), "read-only")
			assert.Contains(t, err.Error(), "public.benchmark_result")
			assert.Contains(t, err.Error(), privilege)
		})
	}
}

func TestValidateTargetRejectsWrongHost(t *testing.T) {
	info := validTargetInfo()
	info.Host = "127.0.0.1"

	err := ValidateTarget(info, validTargetPolicy())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "clone-db.example")
	assert.Contains(t, err.Error(), "192.0.2.10")
}

func TestValidateTargetRejectsWrongPort(t *testing.T) {
	info := validTargetInfo()
	info.Port = 15432

	err := ValidateTarget(info, validTargetPolicy())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "5432")
}

func TestValidateTargetRejectsSuperuser(t *testing.T) {
	info := validTargetInfo()
	info.Superuser = true

	err := ValidateTarget(info, validTargetPolicy())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "superuser")
}

func TestValidateTargetRejectsMissingRequiredTable(t *testing.T) {
	info := validTargetInfo()
	info.SchemaTables = []string{"benchmark_result", "case", "context", "info", "hardware", "commit", "api_token"}

	err := ValidateTarget(info, validTargetPolicy())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "user")
}

func TestValidateTargetRejectsDevelopmentRoleByDefault(t *testing.T) {
	info := validTargetInfo()
	info.User = "conbench_dev"

	err := ValidateTarget(info, validTargetPolicy())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "read-only")
}

func TestValidateTargetAcceptsDevelopmentRoleOnlyWhenAllowed(t *testing.T) {
	info := validTargetInfo()
	info.User = "conbench_dev"
	info.WritableTablePrivileges = map[string][]string{"public.benchmark_result": {"INSERT", "UPDATE"}}
	policy := validTargetPolicy()
	policy.AllowDevRole = true

	require.NoError(t, ValidateTarget(info, policy))
}

func TestValidateTargetRejectsDefaultTransactionReadOnlyFalse(t *testing.T) {
	info := validTargetInfo()
	info.DefaultTransactionReadOnly = false

	err := ValidateTarget(info, validTargetPolicy())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "default_transaction_read_only")
}

func TestCompareCountSnapshotsAcceptsEqualCounts(t *testing.T) {
	before := completePreflightCountSnapshot()
	after := completePreflightCountSnapshot()

	delta, err := CompareCountSnapshots(before, after)
	require.NoError(t, err)
	assert.False(t, delta.Changed)
	assert.Empty(t, delta.Tables)
}

func TestCompareCountSnapshotsAcceptsMissingOptionalAPITokenTable(t *testing.T) {
	before := completePreflightCountSnapshot()
	after := completePreflightCountSnapshot()
	delete(before.WritableTableCounts, "public.api_token")
	delete(after.WritableTableCounts, "public.api_token")

	delta, err := CompareCountSnapshots(before, after)

	require.NoError(t, err)
	assert.False(t, delta.Changed)
	assert.Empty(t, delta.Tables)
}

func TestCompareCountSnapshotsRejectsPartialExpectedTableSet(t *testing.T) {
	before := CountSnapshot{
		WritableTableCounts: map[string]int64{`public."case"`: 10},
	}
	after := CountSnapshot{
		WritableTableCounts: map[string]int64{`public."case"`: 10},
	}

	delta, err := CompareCountSnapshots(before, after)
	require.Error(t, err)
	assert.True(t, delta.Changed)
}

func TestCompareCountSnapshotsRejectsUnknownTable(t *testing.T) {
	before := completePreflightCountSnapshot()
	after := completePreflightCountSnapshot()
	before.WritableTableCounts["public.unknown"] = 1
	after.WritableTableCounts["public.unknown"] = 1

	delta, err := CompareCountSnapshots(before, after)
	require.Error(t, err)
	assert.True(t, delta.Changed)
	require.NotEmpty(t, delta.Tables)
	assert.Equal(t, "public.unknown", delta.Tables[0].Table)
}

func TestCompareCountSnapshotsReportsChangedTable(t *testing.T) {
	before := completePreflightCountSnapshot()
	after := completePreflightCountSnapshot()
	after.WritableTableCounts[`public."case"`] = before.WritableTableCounts[`public."case"`] + 1

	delta, err := CompareCountSnapshots(before, after)
	require.Error(t, err)
	assert.True(t, delta.Changed)
	require.Len(t, delta.Tables, 1)
	assert.Equal(t, `public."case"`, delta.Tables[0].Table)
	assert.Equal(t, int64(1), delta.Tables[0].Delta)
}

func TestCompareCountSnapshotsRejectsMalformedSnapshots(t *testing.T) {
	tests := []struct {
		name   string
		before CountSnapshot
		after  CountSnapshot
	}{
		{
			name:   "nil before",
			before: CountSnapshot{},
			after:  CountSnapshot{WritableTableCounts: map[string]int64{`public."case"`: 1}},
		},
		{
			name:   "nil after",
			before: CountSnapshot{WritableTableCounts: map[string]int64{`public."case"`: 1}},
			after:  CountSnapshot{},
		},
		{
			name:   "empty before and after",
			before: CountSnapshot{WritableTableCounts: map[string]int64{}},
			after:  CountSnapshot{WritableTableCounts: map[string]int64{}},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			delta, err := CompareCountSnapshots(tt.before, tt.after)
			require.Error(t, err)
			assert.True(t, delta.Changed)
		})
	}
}

func TestCompareCountSnapshotsReportsMissingBeforeKey(t *testing.T) {
	before := completePreflightCountSnapshot()
	after := completePreflightCountSnapshot()
	delete(before.WritableTableCounts, `public."case"`)

	delta, err := CompareCountSnapshots(before, after)
	require.Error(t, err)
	assert.True(t, delta.Changed)
	require.Len(t, delta.Tables, 1)
	assert.Equal(t, `public."case"`, delta.Tables[0].Table)
	assert.False(t, delta.Tables[0].BeforePresent)
	assert.True(t, delta.Tables[0].AfterPresent)
}

func TestCompareCountSnapshotsReportsMissingAfterKey(t *testing.T) {
	before := completePreflightCountSnapshot()
	after := completePreflightCountSnapshot()
	delete(after.WritableTableCounts, `public."case"`)

	delta, err := CompareCountSnapshots(before, after)
	require.Error(t, err)
	assert.True(t, delta.Changed)
	require.Len(t, delta.Tables, 1)
	assert.Equal(t, `public."case"`, delta.Tables[0].Table)
	assert.True(t, delta.Tables[0].BeforePresent)
	assert.False(t, delta.Tables[0].AfterPresent)
}

func completePreflightCountSnapshot() CountSnapshot {
	return CountSnapshot{
		WritableTableCounts: map[string]int64{
			`public."case"`:    1,
			"public.context":   2,
			"public.info":      3,
			"public.hardware":  4,
			"public.commit":    5,
			"public.api_token": 6,
			`public."user"`:    7,
		},
	}
}

func TestProbeTargetCollectsSchemaCountsAndPrivileges(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)

	info, err := ProbeTarget(ctx, pool)
	require.NoError(t, err)

	assert.Equal(t, "conbench", info.Database)
	assert.NotEmpty(t, info.User)
	assert.ElementsMatch(t, []string{"benchmark_result", "case", "context", "info", "hardware", "commit", "api_token", "user"}, info.SchemaTables)
	assert.NotContains(t, info.WritableTableCounts, "public.benchmark_result")
	assert.Contains(t, info.WritableTableCounts, `public."case"`)
	require.Contains(t, info.WritableTablePrivileges, "public.benchmark_result")
	assert.Contains(t, info.WritableTablePrivileges["public.benchmark_result"], "INSERT")
}

func TestProbeTargetSkipsCountsForMissingTables(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	_, err := pool.Exec(ctx, `DROP TABLE public."user" CASCADE`)
	require.NoError(t, err)

	info, err := ProbeTarget(ctx, pool)
	require.NoError(t, err)

	assert.NotContains(t, info.SchemaTables, "user")
	assert.NotContains(t, info.WritableTableCounts, `public."user"`)
	assert.NotContains(t, info.WritableTablePrivileges, `public."user"`)
	assert.NotContains(t, info.WritableTableCounts, "public.benchmark_result")
	assert.Contains(t, info.WritableTableCounts, `public."case"`)
}

func TestProbeTargetSafetySkipsCounts(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)

	info, err := ProbeTargetSafety(ctx, pool)
	require.NoError(t, err)

	assert.Equal(t, "conbench", info.Database)
	assert.NotEmpty(t, info.User)
	assert.ElementsMatch(t, []string{"benchmark_result", "case", "context", "info", "hardware", "commit", "api_token", "user"}, info.SchemaTables)
	assert.Empty(t, info.WritableTableCounts)
	require.Contains(t, info.WritableTablePrivileges, "public.benchmark_result")
	assert.Contains(t, info.WritableTablePrivileges["public.benchmark_result"], "INSERT")
}
