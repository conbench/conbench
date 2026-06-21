package commit

import "context"

// MapProvider resolves commits from a fixed map keyed by sha, for deterministic
// seeding and tests. It lets a caller attach real messages, timestamps, and fork
// points to specific shas (richer than LocalProvider's synthesized metadata)
// without a network. An empty sha or one absent from the map yields (nil, nil),
// i.e. no commit — the result is then stored with a NULL commit_id.
type MapProvider struct {
	Commits map[string]Info
}

// Resolve implements Provider. The mapped Info's message, timestamp, and fork
// point are kept as given; the sha is taken from the request and the repository
// is normalized so it matches the fingerprint's repo. A map entry without a fork
// point defaults to the default branch (fork_point_sha == sha).
func (p MapProvider) Resolve(_ context.Context, req Request) (*Info, error) {
	if req.Commit == "" {
		return nil, nil
	}
	info, ok := p.Commits[req.Commit]
	if !ok {
		return nil, nil
	}
	out := info
	out.Sha = req.Commit
	out.Repository = NormalizeRepoURL(req.Repository)
	if out.ForkPointSha == nil {
		sha := req.Commit
		out.ForkPointSha = &sha
	}
	return &out, nil
}
