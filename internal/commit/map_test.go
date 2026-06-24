package commit_test

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit"
)

var _ commit.Provider = commit.MapProvider{}

func TestMapProviderResolvesKnownCommit(t *testing.T) {
	ts := time.Date(2024, 1, 3, 9, 0, 0, 0, time.UTC)
	p := commit.MapProvider{Commits: map[string]commit.Info{
		"sha-1": {Message: "Optimize pivot", Timestamp: &ts},
	}}

	info, err := p.Resolve(context.Background(), commit.Request{
		Commit:     "sha-1",
		Repository: "https://github.com/org/repo/",
	})
	require.NoError(t, err)
	require.NotNil(t, info)
	assert.Equal(t, "sha-1", info.Sha)
	assert.Equal(t, "Optimize pivot", info.Message)
	if assert.NotNil(t, info.Timestamp) {
		assert.True(t, info.Timestamp.Equal(ts), "timestamp = %v, want %v", info.Timestamp, ts)
	}
	// Repository is normalized (trailing slash stripped).
	assert.Equal(t, "https://github.com/org/repo", info.Repository)
	// A default-branch entry (no explicit fork point) is on its own fork point.
	if assert.NotNil(t, info.ForkPointSha) {
		assert.Equal(t, "sha-1", *info.ForkPointSha)
	}
}

func TestMapProviderPreservesOffBranchForkPoint(t *testing.T) {
	forkPoint := "sha-base"
	p := commit.MapProvider{Commits: map[string]commit.Info{
		"sha-feature": {Message: "WIP", ForkPointSha: &forkPoint},
	}}

	info, err := p.Resolve(context.Background(), commit.Request{Commit: "sha-feature", Repository: "https://github.com/org/repo"})
	require.NoError(t, err)
	if assert.NotNil(t, info.ForkPointSha) {
		assert.Equal(t, "sha-base", *info.ForkPointSha, "off branch")
	}
}

func TestMapProviderEmptyAndUnknown(t *testing.T) {
	p := commit.MapProvider{Commits: map[string]commit.Info{"known": {}}}

	for _, sha := range []string{"", "unknown"} {
		info, err := p.Resolve(context.Background(), commit.Request{Commit: sha, Repository: "https://github.com/org/repo"})
		require.NoError(t, err, "Resolve(%q)", sha)
		assert.Nil(t, info, "Resolve(%q) want nil (no commit)", sha)
	}
}
