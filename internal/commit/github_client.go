package commit

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"math"
	"net/http"
	"net/url"
	"strings"
	"sync/atomic"
	"time"
)

// defaultGitHubBaseURL is the live API; tests inject an httptest URL.
const defaultGitHubBaseURL = "https://api.github.com"

// maxResponseBytes caps response reads; commit-list pages are well under this.
const maxResponseBytes = 8 << 20

// GitHubClient is a minimal GitHub HTTP API client: the five endpoints the
// commit provider and the ancestry backfill need, with the legacy token-pool
// rotation and bounded retry behavior (commit.py:836-995). Stdlib only.
// Safe for concurrent use: the rotating token index is atomic.
type GitHubClient struct {
	baseURL string
	httpc   *http.Client
	tokens  []string
	cur     atomic.Int64 // rotating index into tokens
}

// errQuotaExhausted is the permanent failure after every token in the pool hit
// its hourly quota (legacy commit.py:973).
var errQuotaExhausted = errors.New("github API quota exhausted across token pool")

// NewGitHubClient builds a client from the GITHUB_API_TOKEN env value
// (comma-separated tokens, whitespace-trimmed, length-sanity-filtered like
// legacy commit.py:575-631; empty means unauthenticated). baseURL "" means the
// live GitHub API; tests pass an httptest URL.
func NewGitHubClient(tokenEnv, baseURL string) *GitHubClient {
	if baseURL == "" {
		baseURL = defaultGitHubBaseURL
	}
	return &GitHubClient{
		baseURL: baseURL,
		httpc:   &http.Client{Timeout: 30 * time.Second},
		tokens:  parseTokenEnv(tokenEnv),
	}
}

// parseTokenEnv splits the comma-separated token list, trims whitespace, and
// drops entries with implausible lengths (legacy: 5 <= len <= 130).
func parseTokenEnv(env string) []string {
	var out []string
	for raw := range strings.SplitSeq(env, ",") {
		tok := strings.TrimSpace(raw)
		if len(tok) < 5 || len(tok) > 130 {
			if tok != "" {
				slog.Info("github: ignoring token with unexpected length", "length", len(tok))
			}
			continue
		}
		out = append(out, tok)
	}
	return out
}

// parsedCommit is the subset of a GitHub commit object the commit table needs,
// matching legacy _parse_commit (commit.py:812-834).
type parsedCommit struct {
	Parent       *string
	Timestamp    time.Time
	Message      string
	AuthorName   string
	AuthorLogin  *string
	AuthorAvatar *string
}

// commitJSON mirrors the GitHub commit-object fields we read. The top-level
// author can be JSON null (github_commit_no_author.json).
type commitJSON struct {
	Sha    string `json:"sha"`
	Commit struct {
		Author struct {
			Name string `json:"name"`
			Date string `json:"date"`
		} `json:"author"`
		Message string `json:"message"`
	} `json:"commit"`
	Author *struct {
		Login     string `json:"login"`
		AvatarURL string `json:"avatar_url"`
	} `json:"author"`
	Parents []struct {
		Sha string `json:"sha"`
	} `json:"parents"`
}

// parseCommit converts a GitHub commit object to the column subset: first
// parent, author date (the authored-at time, not the commit date), first
// message line truncated to 240 characters, and the author identity (login and
// avatar are null when GitHub cannot associate a user account).
func parseCommit(cj commitJSON) (parsedCommit, error) {
	ts, err := time.Parse(time.RFC3339, cj.Commit.Author.Date)
	if err != nil {
		return parsedCommit{}, fmt.Errorf("parse commit author date %q: %w", cj.Commit.Author.Date, err)
	}
	p := parsedCommit{
		Timestamp:  ts.UTC(),
		Message:    firstLine240(cj.Commit.Message),
		AuthorName: cj.Commit.Author.Name,
	}
	if len(cj.Parents) > 0 {
		p.Parent = &cj.Parents[0].Sha
	}
	if cj.Author != nil {
		p.AuthorLogin = &cj.Author.Login
		p.AuthorAvatar = &cj.Author.AvatarURL
	}
	return p, nil
}

// firstLine240 keeps the first message line truncated to 240 characters
// (runes, matching Python's [:240] slice; the column is varchar(250)).
func firstLine240(msg string) string {
	line, _, _ := strings.Cut(msg, "\n")
	r := []rune(line)
	if len(r) > 240 {
		r = r[:240]
	}
	return string(r)
}

// commitInfo fetches and parses GET /repos/{spec}/commits/{sha}.
func (c *GitHubClient) commitInfo(ctx context.Context, spec, sha string) (parsedCommit, error) {
	var cj commitJSON
	if err := c.getJSON(ctx, fmt.Sprintf("%s/repos/%s/commits/%s", c.baseURL, spec, sha), &cj); err != nil {
		return parsedCommit{}, err
	}
	return parseCommit(cj)
}

// defaultBranch returns the repo's default branch in "org:branch" form,
// following source when the repo is a fork (legacy commit.py:657-674).
func (c *GitHubClient) defaultBranch(ctx context.Context, spec string) (string, error) {
	var repo struct {
		Fork          bool   `json:"fork"`
		DefaultBranch string `json:"default_branch"`
		Owner         struct {
			Login string `json:"login"`
		} `json:"owner"`
		Source *struct {
			DefaultBranch string `json:"default_branch"`
			Owner         struct {
				Login string `json:"login"`
			} `json:"owner"`
		} `json:"source"`
	}
	if err := c.getJSON(ctx, fmt.Sprintf("%s/repos/%s", c.baseURL, spec), &repo); err != nil {
		return "", err
	}
	if repo.Fork && repo.Source != nil {
		return repo.Source.Owner.Login + ":" + repo.Source.DefaultBranch, nil
	}
	return repo.Owner.Login + ":" + repo.DefaultBranch, nil
}

// prBranch returns the head label ("org:branch") of a pull request.
func (c *GitHubClient) prBranch(ctx context.Context, spec string, pr int) (string, error) {
	var pull struct {
		Head struct {
			Label string `json:"label"`
		} `json:"head"`
	}
	if err := c.getJSON(ctx, fmt.Sprintf("%s/repos/%s/pulls/%d", c.baseURL, spec, pr), &pull); err != nil {
		return "", err
	}
	return pull.Head.Label, nil
}

// mergeBase returns the fork point: the merge base between base (default
// branch, org:branch form) and sha (legacy get_fork_point_sha).
func (c *GitHubClient) mergeBase(ctx context.Context, spec, base, sha string) (string, error) {
	var cmp struct {
		MergeBaseCommit struct {
			Sha string `json:"sha"`
		} `json:"merge_base_commit"`
	}
	if err := c.getJSON(ctx, fmt.Sprintf("%s/repos/%s/compare/%s...%s", c.baseURL, spec, url.PathEscape(base), sha), &cmp); err != nil {
		return "", err
	}
	return cmp.MergeBaseCommit.Sha, nil
}

// commitsOnBranch pages GET /repos/{spec}/commits for the branch between since
// and until (both inclusive, per the GitHub API; the backfill trims the bounds).
// The branch's "org:" prefix is stripped for the query (legacy commit.py:707).
func (c *GitHubClient) commitsOnBranch(ctx context.Context, spec, branch string, since, until time.Time) ([]commitJSON, error) {
	if _, b, found := strings.Cut(branch, ":"); found {
		branch = b
	}
	base := fmt.Sprintf("%s/repos/%s/commits?per_page=100&sha=%s&since=%s&until=%s",
		c.baseURL, spec, url.QueryEscape(branch), isoZ(since), isoZ(until))
	// A deadline-bearing ctx (the provider's per-resolve budget) stays
	// authoritative. A deadline-less ctx (the backfiller's root context) would
	// let getJSON's retry loop spin on a persistently failing page forever, so
	// bound each page fetch.
	_, hasDeadline := ctx.Deadline()
	var all []commitJSON
	for page := 1; ; page++ {
		var batch []commitJSON
		err := c.fetchPage(ctx, fmt.Sprintf("%s&page=%d", base, page), hasDeadline, &batch)
		if err != nil {
			return nil, err
		}
		all = append(all, batch...)
		if len(batch) < 100 {
			return all, nil
		}
	}
}

// fetchPage fetches one commits-list page, applying a per-page timeout only
// when the caller's context carries no deadline of its own.
func (c *GitHubClient) fetchPage(ctx context.Context, u string, hasDeadline bool, out *[]commitJSON) error {
	if hasDeadline {
		return c.getJSON(ctx, u, out)
	}
	pageCtx, cancel := context.WithTimeout(ctx, backfillCallTimeout)
	defer cancel()
	return c.getJSON(pageCtx, u, out)
}

// isoZ formats a timestamp the way the GitHub list API expects (legacy
// commit.py:709-710: tz-naive ISO 8601 plus "Z").
func isoZ(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05Z")
}

// getJSON fetches url, retrying retryable failures (network errors, 5xx,
// rate-limit 403s) with the legacy backoff curve until ctx expires, and decodes
// the 200 body into out. Token rotation on quota exhaustion follows
// commit.py:944-973: rotate and retry until rotations exceed the pool size.
func (c *GitHubClient) getJSON(ctx context.Context, u string, out any) error {
	rotations := 0
	for attempt := 1; ; attempt++ {
		body, retryable, err := c.attempt(ctx, u, &rotations)
		if err == nil {
			if uerr := json.Unmarshal(body, out); uerr != nil {
				return fmt.Errorf("decode github response for %s: %w", u, uerr)
			}
			return nil
		}
		if !retryable {
			return err
		}
		// Legacy backoff: 0.66, 1.33, 2.66, 5.33, 5.5, 5.5, ... seconds.
		wait := time.Duration(math.Min(math.Exp2(float64(attempt))/3.0, 5.5) * float64(time.Second))
		select {
		case <-ctx.Done():
			return fmt.Errorf("github request budget exceeded for %s (last error: %w): %w", u, err, ctx.Err())
		case <-time.After(wait):
		}
	}
}

// attempt performs one GET. It returns the body on 200; otherwise an error and
// whether the failure is retryable.
func (c *GitHubClient) attempt(ctx context.Context, u string, rotations *int) (body []byte, retryable bool, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, false, fmt.Errorf("build github request: %w", err)
	}
	if tok := c.token(); tok != "" {
		req.Header.Set("Authorization", "Bearer "+tok)
	}
	resp, err := c.httpc.Do(req)
	if err != nil {
		return nil, true, fmt.Errorf("github request: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err = io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		return nil, true, fmt.Errorf("read github response: %w", err)
	}

	switch {
	case resp.StatusCode == http.StatusOK:
		return body, false, nil
	case resp.StatusCode == http.StatusForbidden:
		retryable, ferr := c.handle403(resp, rotations)
		return nil, retryable, ferr
	case resp.StatusCode >= 500:
		return nil, true, fmt.Errorf("github %d for %s", resp.StatusCode, u)
	default:
		return nil, false, fmt.Errorf("unexpected github response %d for %s: %.150s", resp.StatusCode, u, string(body))
	}
}

// token returns the current auth token, or "" when unauthenticated.
func (c *GitHubClient) token() string {
	if len(c.tokens) == 0 {
		return ""
	}
	return c.tokens[int(c.cur.Load())%len(c.tokens)]
}

// handle403 decides whether a 403 is retryable. Quota exhausted (remaining: 0)
// rotates the token pool and retries until every token has been tried once,
// then fails permanently with errQuotaExhausted (legacy commit.py:944-973).
// Other 403s are transient rate limiting; the backoff loop absorbs them.
func (c *GitHubClient) handle403(resp *http.Response, rotations *int) (bool, error) {
	if resp.Header.Get("x-ratelimit-remaining") != "0" {
		return true, errors.New("github 403 (rate limited, quota remaining)")
	}
	if len(c.tokens) > 1 {
		c.cur.Add(1)
		*rotations++
		if *rotations <= len(c.tokens) {
			slog.Info("github: quota exhausted, rotated auth token")
			return true, errors.New("github 403 (quota exhausted, token rotated)")
		}
	}
	return false, errQuotaExhausted
}
