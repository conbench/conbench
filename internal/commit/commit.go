// Package commit resolves the commit metadata associated with a benchmark
// result. The walking skeleton uses LocalProvider, which synthesizes a commit
// from the result payload with no network. GitHubProvider (phase 4) will fetch
// real metadata, fork points, and ancestry.
package commit

import (
	"context"
	"strings"
	"time"
)

// Info is the commit metadata for a result, ready to be persisted by the data
// layer. Its fields mirror the commit table columns (minus the generated id).
type Info struct {
	Sha          string
	Repository   string
	Parent       *string
	Message      string
	AuthorName   string
	AuthorLogin  *string
	AuthorAvatar *string
	Timestamp    *time.Time
	Branch       *string
	ForkPointSha *string
}

// Request carries the commit inputs available from the result payload without
// contacting GitHub: the github.commit sha (optional), the github.repository
// URL, the result's own timestamp, and the user's branch/PR hints. An empty
// Branch means "not given" (legacy treats null, absent, and "" identically);
// a non-empty Branch beats PRNumber, which beats the default branch.
type Request struct {
	Commit          string
	Repository      string
	ResultTimestamp time.Time
	Branch          string
	PRNumber        *int
}

// Provider resolves commit metadata for a result.
type Provider interface {
	// Resolve returns the commit metadata, or (nil, nil) when the request has no
	// commit sha — the result is then stored with a NULL commit_id and excluded
	// from history.
	Resolve(ctx context.Context, req Request) (*Info, error)
}

// NormalizeRepoURL canonicalizes a repository URL the way legacy ingestion
// does: rewrite git@github.com: remotes to https URLs
// (benchmark_result.py:1495) and strip trailing slashes
// (benchmark_result.py:1522). The same normalized value feeds the commit row,
// the result's commit_repo_url, and the history fingerprint, so it must be
// applied consistently across all three.
func NormalizeRepoURL(raw string) string {
	if rest, ok := strings.CutPrefix(raw, "git@github.com:"); ok {
		raw = "https://github.com/" + rest
	}
	return strings.TrimRight(raw, "/")
}
