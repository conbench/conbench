package commit

import "context"

// LocalProvider synthesizes a commit from the result payload with no network.
// It marks the commit as on the default branch (fork_point_sha == sha) so the
// result satisfies the history membership filter, uses the result's timestamp as
// the commit timestamp, and leaves message and author empty. Real metadata and
// fork points are GitHubProvider's job (phase 4). It is the skeleton default and
// is also used by the seed script and e2e.
type LocalProvider struct{}

// Resolve implements Provider. It returns (nil, nil) when no commit sha is given.
func (LocalProvider) Resolve(_ context.Context, req Request) (*Info, error) {
	if req.Commit == "" {
		return nil, nil
	}
	sha := req.Commit
	ts := req.ResultTimestamp
	return &Info{
		Sha:          sha,
		Repository:   NormalizeRepoURL(req.Repository),
		ForkPointSha: &sha,
		Timestamp:    &ts,
	}, nil
}
