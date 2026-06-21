package commit

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/commit/githubtest"
)

func TestParseTokenEnv(t *testing.T) {
	cases := map[string][]string{
		"":                          nil,
		"x":                         nil,            // too short (<5), dropped like legacy
		"ghp_aaaaaa":                {"ghp_aaaaaa"}, // single token
		" ghp_aaaaaa , ghp_bbbbbb ": {"ghp_aaaaaa", "ghp_bbbbbb"},
		"ghp_aaaaaa,x":              {"ghp_aaaaaa"},
		strings.Repeat("a", 131):    nil, // too long (>130), dropped
	}
	for in, want := range cases {
		assert.Equal(t, want, parseTokenEnv(in), "parseTokenEnv(%q)", in)
	}
}

func TestClientCommitInfoParsesFixture(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo/commits/02addad336ba19a654f9c857ede546331be7b631",
		githubtest.Fixture(t, "github_child.json"))
	c := NewGitHubClient("", srv.URL)

	got, err := c.commitInfo(context.Background(), "org/repo", "02addad336ba19a654f9c857ede546331be7b631")
	require.NoError(t, err)
	assert.Equal(t, "Diana Clarke", got.AuthorName)
	require.NotNil(t, got.Parent)
	assert.Equal(t, "4beb514d071c9beec69b8917b5265e77ade22fb3", *got.Parent)
	assert.True(t, got.Timestamp.Equal(time.Date(2021, 2, 25, 1, 2, 51, 0, time.UTC)))
	// First line only, and the legacy 240-char truncation.
	assert.Equal(t, "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)", got.Message)
	require.NotNil(t, got.AuthorLogin)
	assert.Equal(t, "dianaclarke", *got.AuthorLogin)
	require.NotNil(t, got.AuthorAvatar)
}

func TestClientCommitInfoNullAuthor(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo/commits/sha1", githubtest.Fixture(t, "github_commit_no_author.json"))
	c := NewGitHubClient("", srv.URL)

	got, err := c.commitInfo(context.Background(), "org/repo", "sha1")
	require.NoError(t, err)
	assert.Nil(t, got.AuthorLogin, "top-level author is JSON null in this fixture")
	assert.Nil(t, got.AuthorAvatar)
	assert.NotEmpty(t, got.AuthorName, "commit.author.name is still present")
}

func TestClientMessageTruncatedTo240Runes(t *testing.T) {
	long := strings.Repeat("ä", 300) // multibyte: truncation must count runes
	body := fmt.Sprintf(`{"sha":"s","commit":{"author":{"name":"a","date":"2021-01-01T00:00:00Z"},"message":%q},"author":null,"parents":[]}`, long+"\nsecond line")
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo/commits/s", []byte(body))
	c := NewGitHubClient("", srv.URL)

	got, err := c.commitInfo(context.Background(), "org/repo", "s")
	require.NoError(t, err)
	assert.Equal(t, strings.Repeat("ä", 240), got.Message)
	assert.Nil(t, got.Parent, "no parents -> nil parent")
}

func TestClientDefaultBranchForkAware(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo", []byte(`{"fork":false,"owner":{"login":"org"},"default_branch":"main"}`))
	srv.HandleJSON("/repos/fork/repo", []byte(`{"fork":true,"owner":{"login":"fork"},"default_branch":"main","source":{"owner":{"login":"upstream"},"default_branch":"trunk"}}`))
	c := NewGitHubClient("", srv.URL)

	b, err := c.defaultBranch(context.Background(), "org/repo")
	require.NoError(t, err)
	assert.Equal(t, "org:main", b)

	b, err = c.defaultBranch(context.Background(), "fork/repo")
	require.NoError(t, err)
	assert.Equal(t, "upstream:trunk", b, "forks follow source")
}

func TestClientPRBranchAndMergeBase(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleJSON("/repos/org/repo/pulls/7", []byte(`{"head":{"label":"someuser:feature"}}`))
	srv.HandleJSON("/repos/org/repo/compare/org:main...abc", []byte(`{"merge_base_commit":{"sha":"forkpoint"}}`))
	c := NewGitHubClient("", srv.URL)

	b, err := c.prBranch(context.Background(), "org/repo", 7)
	require.NoError(t, err)
	assert.Equal(t, "someuser:feature", b)

	fp, err := c.mergeBase(context.Background(), "org/repo", "org:main", "abc")
	require.NoError(t, err)
	assert.Equal(t, "forkpoint", fp)
}

func TestClientRetriesOn5xx(t *testing.T) {
	srv := githubtest.NewServer(t)
	var calls int
	srv.Mux.HandleFunc("/repos/org/repo", func(w http.ResponseWriter, _ *http.Request) {
		calls++
		if calls == 1 {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		_, _ = w.Write([]byte(`{"fork":false,"owner":{"login":"org"},"default_branch":"main"}`))
	})
	c := NewGitHubClient("", srv.URL)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	b, err := c.defaultBranch(ctx, "org/repo")
	require.NoError(t, err)
	assert.Equal(t, "org:main", b)
	assert.Equal(t, 2, calls)
}

func TestClientPermanentErrorNoRetry(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleStatus("/repos/org/repo/commits/gone", http.StatusNotFound)
	c := NewGitHubClient("", srv.URL)

	_, err := c.commitInfo(context.Background(), "org/repo", "gone")
	require.Error(t, err)
	assert.Len(t, srv.Requests(), 1, "404 is permanent, no retry")
}

func TestClientBudgetExceeded(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.HandleStatus("/repos/org/repo", http.StatusBadGateway) // always retryable
	c := NewGitHubClient("", srv.URL)

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	_, err := c.defaultBranch(ctx, "org/repo")
	require.Error(t, err)
	assert.ErrorIs(t, err, context.DeadlineExceeded)
}

func TestClientRotatesTokenOnQuotaExhaustion(t *testing.T) {
	srv := githubtest.NewServer(t)
	var seen []string
	srv.Mux.HandleFunc("/repos/org/repo", func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Header.Get("Authorization"))
		if len(seen) == 1 {
			w.Header().Set("x-ratelimit-remaining", "0")
			w.WriteHeader(http.StatusForbidden)
			return
		}
		_, _ = w.Write([]byte(`{"fork":false,"owner":{"login":"org"},"default_branch":"main"}`))
	})
	c := NewGitHubClient("ghp_aaaaaa,ghp_bbbbbb", srv.URL)

	b, err := c.defaultBranch(context.Background(), "org/repo")
	require.NoError(t, err)
	assert.Equal(t, "org:main", b)
	require.Len(t, seen, 2)
	assert.NotEqual(t, seen[0], seen[1], "token must rotate after quota-exhausted 403")
}

func TestClientQuotaExhaustedAcrossPoolFails(t *testing.T) {
	srv := githubtest.NewServer(t)
	srv.Mux.HandleFunc("/repos/org/repo", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("x-ratelimit-remaining", "0")
		w.WriteHeader(http.StatusForbidden)
	})
	c := NewGitHubClient("ghp_aaaaaa,ghp_bbbbbb", srv.URL)

	_, err := c.defaultBranch(context.Background(), "org/repo")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "quota")
	// pool size 2: initial try + one try per rotation, capped like legacy
	// (rotations <= pool size), so at most 3 requests.
	assert.LessOrEqual(t, len(srv.Requests()), 3)
}

func TestClientCommitsOnBranchPagesAndStripsOrgPrefix(t *testing.T) {
	srv := githubtest.NewServer(t)
	var commits []json.RawMessage
	require.NoError(t, json.Unmarshal(githubtest.Fixture(t, "github_commits.json"), &commits))
	page1, err := json.Marshal(commits[:25])
	require.NoError(t, err)
	srv.Mux.HandleFunc("/repos/org/repo/commits", func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "main", r.URL.Query().Get("sha"), "org: prefix must be stripped")
		assert.Equal(t, "100", r.URL.Query().Get("per_page"))
		assert.Equal(t, "2021-01-01T00:00:00Z", r.URL.Query().Get("since"))
		assert.Equal(t, "2021-02-01T00:00:00Z", r.URL.Query().Get("until"))
		_, _ = w.Write(page1) // 25 < 100 -> single page
	})
	c := NewGitHubClient("", srv.URL)

	got, err := c.commitsOnBranch(context.Background(), "org/repo", "org:main",
		time.Date(2021, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2021, 2, 1, 0, 0, 0, 0, time.UTC))
	require.NoError(t, err)
	assert.Len(t, got, 25)
	assert.Len(t, srv.Requests(), 1)
}
