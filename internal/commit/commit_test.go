package commit_test

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
)

// LocalProvider must satisfy the Provider interface.
var _ commit.Provider = commit.LocalProvider{}

func TestLocalProviderSynthesizesDefaultBranchCommit(t *testing.T) {
	ts := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	info, err := commit.LocalProvider{}.Resolve(context.Background(), commit.Request{
		Commit:          "abc123",
		Repository:      "https://github.com/org/repo",
		ResultTimestamp: ts,
	})
	require.NoError(t, err)
	require.NotNil(t, info)
	assert.Equal(t, "abc123", info.Sha)
	assert.Equal(t, "https://github.com/org/repo", info.Repository)
	// sha == fork_point_sha is what makes the commit count as on the default
	// branch, so the result passes the history membership filter.
	if assert.NotNil(t, info.ForkPointSha) {
		assert.Equal(t, "abc123", *info.ForkPointSha)
	}
	if assert.NotNil(t, info.Timestamp) {
		assert.True(t, info.Timestamp.Equal(ts), "Timestamp = %v, want %v", info.Timestamp, ts)
	}
	assert.Empty(t, info.Message, "expected empty message")
	assert.Empty(t, info.AuthorName, "expected empty author")
}

func TestLocalProviderStripsTrailingSlash(t *testing.T) {
	info, err := commit.LocalProvider{}.Resolve(context.Background(), commit.Request{
		Commit:          "x",
		Repository:      "https://github.com/org/repo///",
		ResultTimestamp: time.Unix(0, 0).UTC(),
	})
	require.NoError(t, err)
	assert.Equal(t, "https://github.com/org/repo", info.Repository, "want trailing slashes stripped")
}

func TestLocalProviderNoCommitHashYieldsNil(t *testing.T) {
	info, err := commit.LocalProvider{}.Resolve(context.Background(), commit.Request{
		Commit:          "",
		Repository:      "https://github.com/org/repo",
		ResultTimestamp: time.Unix(0, 0).UTC(),
	})
	require.NoError(t, err)
	assert.Nil(t, info, "expected nil info for empty commit hash")
}

func TestNormalizeRepoURL(t *testing.T) {
	cases := map[string]string{
		"https://github.com/org/repo":    "https://github.com/org/repo",
		"https://github.com/org/repo/":   "https://github.com/org/repo",
		"https://github.com/org/repo///": "https://github.com/org/repo",
		"":                               "",
		// Legacy rewrites git@ remotes to https URLs before any other
		// normalization (benchmark_result.py:1495), so the two spellings
		// cannot split history fingerprints.
		"git@github.com:org/repo":  "https://github.com/org/repo",
		"git@github.com:org/repo/": "https://github.com/org/repo",
		"git@gitlab.com:org/repo":  "git@gitlab.com:org/repo", // only github.com is rewritten
	}
	for in, want := range cases {
		assert.Equal(t, want, commit.NormalizeRepoURL(in), "NormalizeRepoURL(%q)", in)
	}
}
