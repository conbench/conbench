package db

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestSelectSeriesPageSQLStartsFromResultBearingCommitWindow(t *testing.T) {
	query := strings.ToLower(selectSeriesPage)

	assert.Contains(t, query, "recent_commit_seed as materialized")
	assert.Contains(t, query, "exists (")
	assert.Contains(t, query, "from benchmark_result br")
	assert.Contains(t, query, "br.commit_id = c.id")
	assert.Regexp(t, `limit \$[0-9]+::integer`, query)
	assert.Contains(t, query, "(select min_commit_timestamp from recent_commit_boundary) is not null")
	assert.NotContains(t, query, "(select min_commit_timestamp from recent_commit_boundary) is null")
	assert.NotContains(t, query, "newer_candidate")

	seedStart := strings.Index(query, "recent_commit_seed as materialized")
	require.NotEqual(t, -1, seedStart)
	seedLimit := strings.Index(query[seedStart:], "limit $")
	require.NotEqual(t, -1, seedLimit)
	seed := query[seedStart : seedStart+seedLimit]
	assert.NotContains(t, seed, "not exists")
	assert.NotContains(t, seed, "newer.history_fingerprint")
}
