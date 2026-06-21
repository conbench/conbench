package githubapi

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const defaultBaseURL = "https://api.github.com"

// Config describes how to authenticate to the GitHub REST API. Token is used
// directly when set; otherwise AppID and AppPrivateKey are exchanged for an
// installation token.
type Config struct {
	Token         string
	AppID         string
	AppPrivateKey string
	BaseURL       string
	HTTPClient    *http.Client
}

// Client is the small subset of the GitHub REST API needed for Conbench CI
// report publication.
type Client struct {
	token   string
	baseURL string
	httpc   *http.Client
}

// CheckRunRequest is the payload for POST /repos/{owner}/{repo}/check-runs.
type CheckRunRequest struct {
	Name        string         `json:"name"`
	HeadSHA     string         `json:"head_sha"`
	Status      string         `json:"status,omitempty"`
	Conclusion  string         `json:"conclusion,omitempty"`
	CompletedAt string         `json:"completed_at,omitempty"`
	DetailsURL  string         `json:"details_url,omitempty"`
	ExternalID  string         `json:"external_id,omitempty"`
	Output      CheckRunOutput `json:"output"`
}

// CheckRunOutput is the Markdown output block attached to a GitHub Check Run.
type CheckRunOutput struct {
	Title   string `json:"title"`
	Summary string `json:"summary"`
	Text    string `json:"text,omitempty"`
}

// CheckRun is the subset of the GitHub response that Conbench consumes.
type CheckRun struct {
	HTMLURL string `json:"html_url"`
}

// PullRequest is the subset of a PR returned by GET /commits/{sha}/pulls.
type PullRequest struct {
	Number int `json:"number"`
}

// IssueComment is the subset of the GitHub issue-comment response that
// Conbench consumes.
type IssueComment struct {
	HTMLURL string `json:"html_url"`
}

// NewClient returns a GitHub API client authenticated by a token or GitHub App.
func NewClient(ctx context.Context, cfg Config) (*Client, error) {
	baseURL := strings.TrimRight(cfg.BaseURL, "/")
	if baseURL == "" {
		baseURL = defaultBaseURL
	}
	httpc := cfg.HTTPClient
	if httpc == nil {
		httpc = http.DefaultClient
	}
	token := strings.TrimSpace(cfg.Token)
	client := &Client{token: token, baseURL: baseURL, httpc: httpc}
	if token != "" {
		return client, nil
	}
	if strings.TrimSpace(cfg.AppID) == "" && strings.TrimSpace(cfg.AppPrivateKey) == "" {
		return nil, errors.New("github token or app credentials are required")
	}
	if strings.TrimSpace(cfg.AppID) == "" {
		return nil, errors.New("github app id is required")
	}
	if strings.TrimSpace(cfg.AppPrivateKey) == "" {
		return nil, errors.New("github app private key is required")
	}
	jwt, err := encodeAppJWT(cfg.AppID, cfg.AppPrivateKey, time.Now().UTC())
	if err != nil {
		return nil, err
	}
	appClient := &Client{token: jwt, baseURL: baseURL, httpc: httpc}
	installationToken, err := appClient.installationToken(ctx)
	if err != nil {
		return nil, err
	}
	client.token = installationToken
	return client, nil
}

// Token returns the bearer token currently used by the client. It exists for
// tests and diagnostics; callers should not log it.
func (c *Client) Token() string {
	return c.token
}

// CreateCheckRun creates a GitHub Check Run on a repository commit.
func (c *Client) CreateCheckRun(ctx context.Context, repository string, body CheckRunRequest) (CheckRun, error) {
	spec, err := RepositorySpec(repository)
	if err != nil {
		return CheckRun{}, err
	}
	var out CheckRun
	if err := c.doJSON(ctx, http.MethodPost, "/repos/"+spec+"/check-runs", body, &out); err != nil {
		return CheckRun{}, err
	}
	return out, nil
}

// PullRequestsForCommit returns PRs associated with a commit.
func (c *Client) PullRequestsForCommit(ctx context.Context, repository, sha string) ([]PullRequest, error) {
	spec, err := RepositorySpec(repository)
	if err != nil {
		return nil, err
	}
	var out []PullRequest
	if err := c.doJSON(ctx, http.MethodGet, "/repos/"+spec+"/commits/"+url.PathEscape(sha)+"/pulls", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// CreatePullRequestComment posts an issue comment to a PR.
func (c *Client) CreatePullRequestComment(ctx context.Context, repository string, number int, body string) (IssueComment, error) {
	spec, err := RepositorySpec(repository)
	if err != nil {
		return IssueComment{}, err
	}
	var out IssueComment
	payload := map[string]string{"body": body}
	path := "/repos/" + spec + "/issues/" + strconv.Itoa(number) + "/comments"
	if err := c.doJSON(ctx, http.MethodPost, path, payload, &out); err != nil {
		return IssueComment{}, err
	}
	return out, nil
}

// RepositorySpec normalizes a GitHub repository URL or owner/repo string to
// owner/repo form for REST paths.
func RepositorySpec(raw string) (string, error) {
	raw = strings.TrimSpace(strings.TrimSuffix(raw, ".git"))
	if raw == "" {
		return "", errors.New("github repository is required")
	}
	if !strings.Contains(raw, "://") && !strings.HasPrefix(raw, "git@") {
		parts := strings.Split(strings.Trim(raw, "/"), "/")
		if len(parts) == 2 && parts[0] != "" && parts[1] != "" {
			return url.PathEscape(parts[0]) + "/" + url.PathEscape(parts[1]), nil
		}
	}
	if rest, ok := strings.CutPrefix(raw, "git@github.com:"); ok {
		raw = "https://github.com/" + strings.TrimSuffix(rest, ".git")
	}
	u, err := url.Parse(strings.TrimRight(raw, "/"))
	if err != nil || u.Scheme != "https" || u.Host != "github.com" {
		return "", errors.New("github repository must be a github.com repository URL")
	}
	parts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", errors.New("github repository must be a github.com repository URL")
	}
	return url.PathEscape(parts[0]) + "/" + url.PathEscape(strings.TrimSuffix(parts[1], ".git")), nil
}

func (c *Client) installationToken(ctx context.Context) (string, error) {
	var installations []struct {
		ID int64 `json:"id"`
	}
	if err := c.doJSON(ctx, http.MethodGet, "/app/installations", nil, &installations); err != nil {
		return "", fmt.Errorf("list github app installations: %w", err)
	}
	if len(installations) == 0 {
		return "", errors.New("github app has no installations")
	}
	var token struct {
		Token string `json:"token"`
	}
	path := "/app/installations/" + strconv.FormatInt(installations[0].ID, 10) + "/access_tokens"
	if err := c.doJSON(ctx, http.MethodPost, path, map[string]any{}, &token); err != nil {
		return "", fmt.Errorf("create github app installation token: %w", err)
	}
	if token.Token == "" {
		return "", errors.New("github app installation token response was empty")
	}
	return token.Token, nil
}

func (c *Client) doJSON(ctx context.Context, method, path string, in any, out any) error {
	var body io.Reader
	if in != nil {
		encoded, err := json.Marshal(in)
		if err != nil {
			return fmt.Errorf("encode github request: %w", err)
		}
		body = bytes.NewReader(encoded)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return fmt.Errorf("build github request: %w", err)
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("User-Agent", "conbench")
	if in != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.httpc.Do(req)
	if err != nil {
		return fmt.Errorf("github request failed: %w", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return fmt.Errorf("read github response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("github %s %s returned HTTP %d: %s", method, path, resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	if out == nil {
		return nil
	}
	if err := json.Unmarshal(raw, out); err != nil {
		return fmt.Errorf("decode github response: %w", err)
	}
	return nil
}

func encodeAppJWT(appID string, privateKey string, now time.Time) (string, error) {
	key, err := parseRSAPrivateKey(privateKey)
	if err != nil {
		return "", err
	}
	header := map[string]string{"alg": "RS256", "typ": "JWT"}
	claims := map[string]any{
		"iss": strings.TrimSpace(appID),
		"iat": now.Add(-1 * time.Minute).Unix(),
		"exp": now.Add(3 * time.Minute).Unix(),
	}
	headerJSON, err := json.Marshal(header)
	if err != nil {
		return "", err
	}
	claimsJSON, err := json.Marshal(claims)
	if err != nil {
		return "", err
	}
	unsigned := base64.RawURLEncoding.EncodeToString(headerJSON) + "." + base64.RawURLEncoding.EncodeToString(claimsJSON)
	sum := sha256.Sum256([]byte(unsigned))
	sig, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, sum[:])
	if err != nil {
		return "", fmt.Errorf("sign github app jwt: %w", err)
	}
	return unsigned + "." + base64.RawURLEncoding.EncodeToString(sig), nil
}

func parseRSAPrivateKey(raw string) (*rsa.PrivateKey, error) {
	raw = strings.ReplaceAll(raw, `\n`, "\n")
	block, _ := pem.Decode([]byte(raw))
	if block == nil {
		return nil, errors.New("parse github app private key: no PEM block found")
	}
	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}
	parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse github app private key: %w", err)
	}
	key, ok := parsed.(*rsa.PrivateKey)
	if !ok {
		return nil, errors.New("parse github app private key: key is not RSA")
	}
	return key, nil
}
