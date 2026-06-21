package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"runtime"
	"time"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/sdk/go/conbench"
	"github.com/spf13/cobra"
)

// loopbackTimeout bounds how long `auth login` waits for the browser to round
// trip through the IdP and land on the loopback callback.
const loopbackTimeout = 3 * time.Minute

// browserOpener launches the user's browser at the login URL. It is a package
// var so tests can inject a programmatic browser that drives the redirect chain.
var browserOpener = openBrowser

// openBrowser opens target in the platform default browser.
func openBrowser(target string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", target)
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", target)
	default:
		cmd = exec.Command("xdg-open", target)
	}
	return cmd.Start()
}

// runAuthLogin performs the OIDC loopback login: it stands up a loopback
// listener, opens the browser at cli-start, waits for the one-time code on the
// callback, exchanges it for an API token, and persists the token for the
// server. On success it prints exactly one line to stdout — the server and the
// token prefix, never the plaintext token. All diagnostics go to stderr. It
// returns the process exit code.
func runAuthLogin(serverURL string, stdout, stderr io.Writer) int {
	loop, err := startLoopback()
	if err != nil {
		fmt.Fprintln(stderr, "conbench: start loopback listener:", err)
		return 1
	}
	defer loop.shutdown()

	startURL := serverURL + "/api/auth/cli-start?redirect_uri=" +
		url.QueryEscape(loop.redirectURI) + "&state=" + url.QueryEscape(loop.state)
	if err := browserOpener(startURL); err != nil {
		fmt.Fprintln(stderr, "conbench: open browser:", err)
	}
	fmt.Fprintln(stderr, "If your browser did not open, visit:", startURL)

	var code string
	select {
	case code = <-loop.codeCh:
	case err := <-loop.errCh:
		fmt.Fprintln(stderr, "conbench: login:", err)
		return 1
	case <-time.After(loopbackTimeout):
		fmt.Fprintln(stderr, "conbench: login timed out waiting for the browser")
		return 1
	}

	token, prefix, err := exchangeCode(serverURL, code)
	if err != nil {
		fmt.Fprintln(stderr, "conbench:", err)
		return 1
	}

	path, err := credentialsPathFn()
	if err != nil {
		fmt.Fprintln(stderr, "conbench:", err)
		return 1
	}
	if err := saveToken(path, serverURL, token); err != nil {
		fmt.Fprintln(stderr, "conbench:", err)
		return 1
	}

	fmt.Fprintf(stdout, "Logged in to %s. Token prefix: %s\n", serverURL, prefix)
	return 0
}

// loopback is a running in-process loopback HTTP server that captures the
// one-time code from the callback redirect.
type loopback struct {
	redirectURI string
	state       string
	codeCh      chan string
	errCh       chan error
	shutdown    func()
}

// startLoopback binds 127.0.0.1 on a free port and serves a /callback handler
// that validates the state and reports the code (or an error) over channels.
func startLoopback() (*loopback, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, err
	}
	port := listener.Addr().(*net.TCPAddr).Port
	loop := &loopback{
		redirectURI: fmt.Sprintf("http://127.0.0.1:%d/callback", port),
		state:       auth.RandomToken(),
		codeCh:      make(chan string, 1),
		errCh:       make(chan error, 1),
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/callback", loop.handleCallback)
	httpSrv := &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	go func() { _ = httpSrv.Serve(listener) }()
	loop.shutdown = func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = httpSrv.Shutdown(ctx)
	}
	return loop, nil
}

func (l *loopback) handleCallback(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	if q.Get("state") != l.state {
		select {
		case l.errCh <- errors.New("state mismatch on loopback callback"):
		default:
		}
		http.Error(w, "state mismatch", http.StatusBadRequest)
		return
	}
	if idpErr := q.Get("error"); idpErr != "" {
		detail := idpErr
		if desc := q.Get("error_description"); desc != "" {
			detail = idpErr + ": " + desc
		}
		select {
		case l.errCh <- fmt.Errorf("identity provider returned an error: %s", detail):
		default:
		}
		http.Error(w, "login failed", http.StatusBadRequest)
		return
	}
	select {
	case l.codeCh <- q.Get("code"):
	default:
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = io.WriteString(w, "Login complete; you can close this tab.")
}

// exchangeCode posts the one-time code to cli-exchange and returns the minted
// token plaintext and its prefix.
func exchangeCode(serverURL, code string) (token, prefix string, err error) {
	client, err := conbench.NewClientWithResponses(serverURL)
	if err != nil {
		return "", "", fmt.Errorf("create client: %w", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	resp, err := client.AuthCliExchangeWithResponse(ctx, conbench.AuthCliExchangeJSONRequestBody{
		Code: code,
		Name: tokenName(),
	})
	if err != nil {
		return "", "", fmt.Errorf("exchange login code: %w", err)
	}
	if resp.HTTPResponse.StatusCode != http.StatusOK {
		return "", "", fmt.Errorf("exchange returned %s: %s",
			resp.HTTPResponse.Status, bytes.TrimSpace(resp.Body))
	}
	if resp.JSON200 == nil {
		return "", "", errors.New("exchange response missing token body")
	}
	if resp.JSON200.Token == "" {
		return "", "", errors.New("exchange response missing token")
	}
	if resp.JSON200.Prefix == "" {
		return "", "", errors.New("exchange response missing token prefix")
	}
	return resp.JSON200.Token, resp.JSON200.Prefix, nil
}

// tokenName labels a CLI-minted token by host and date for later identification
// in `auth token list`.
func tokenName() string {
	host, err := os.Hostname()
	if err != nil || host == "" {
		host = "cli"
	}
	return fmt.Sprintf("cli %s %s", host, time.Now().UTC().Format("2006-01-02"))
}

// authTokenConfig is a parsed `auth token <sub>` invocation.
type authTokenConfig struct {
	server string
	token  string
	id     string
}

func authLoginCommand(stdout, stderr io.Writer) *cobra.Command {
	var server string
	cmd := configureCommand(&cobra.Command{
		Use:   "login",
		Short: "Run loopback browser login.",
		Args: func(cmd *cobra.Command, args []string) error {
			switch {
			case len(args) > 0:
				return commandUsageError(cmd, "auth login does not accept positional arguments")
			case server == "":
				return commandUsageError(cmd, "--server is required")
			}
			return nil
		},
		RunE: func(_ *cobra.Command, _ []string) error {
			if rc := runAuthLogin(server, stdout, stderr); rc != 0 {
				return errLoginFailed
			}
			return nil
		},
	})
	cmd.Flags().StringVar(&server, "server", "", "Conbench server base URL (required)")
	return cmd
}

func authTokenListCommand(stdout io.Writer) *cobra.Command {
	return newAuthTokenCommand("list", "list", "List API tokens.", stdout, runAuthTokenConfig)
}

func authTokenRevokeCommand(stdout io.Writer) *cobra.Command {
	return newAuthTokenCommand("revoke", "revoke <id>", "Revoke an API token.", stdout, runAuthTokenConfig)
}

func newAuthTokenCommand(
	sub string,
	use string,
	short string,
	stdout io.Writer,
	run func(context.Context, string, authTokenConfig, io.Writer) error,
) *cobra.Command {
	var cfg authTokenConfig
	cmd := configureCommand(&cobra.Command{
		Use:   use,
		Short: short,
		Args: func(cmd *cobra.Command, args []string) error {
			if cfg.server == "" {
				return commandUsageError(cmd, "--server is required")
			}
			switch sub {
			case "list":
				if len(args) != 0 {
					return commandUsageError(cmd, "list takes no positional arguments")
				}
			case "revoke":
				if len(args) != 1 {
					return commandUsageError(cmd, "revoke takes exactly one token id")
				}
				cfg.id = args[0]
			default:
				return commandUsageError(cmd, "unknown auth token subcommand %q", sub)
			}

			resolved, err := resolveTokenFromSources(cfg.token, cfg.server)
			if err != nil {
				return err
			}
			cfg.token = resolved
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), sub, cfg, stdout)
		},
	})
	cmd.Flags().StringVar(&cfg.server, "server", "", "Conbench server base URL (required)")
	cmd.Flags().StringVar(&cfg.token, "token", "", "bearer token for authentication")
	return cmd
}

func runAuthTokenConfig(ctx context.Context, sub string, cfg authTokenConfig, stdout io.Writer) error {
	bearer := ""
	if cfg.token != "" {
		bearer = "Bearer " + cfg.token
	}
	client, err := conbench.NewClientWithResponses(cfg.server)
	if err != nil {
		return fmt.Errorf("create client: %w", err)
	}
	switch sub {
	case "list":
		return listTokens(ctx, client, bearer, stdout)
	case "revoke":
		return revokeToken(ctx, client, cfg.id, bearer, stdout)
	default:
		return usageError(fmt.Sprintf("unknown auth token subcommand %q", sub))
	}
}

func listTokens(ctx context.Context, client *conbench.ClientWithResponses, bearer string, stdout io.Writer) error {
	params := &conbench.ListTokensParams{}
	if bearer != "" {
		params.Authorization = &bearer
	}
	resp, err := client.ListTokensWithResponse(ctx, params)
	if err != nil {
		return fmt.Errorf("list tokens: %w", err)
	}
	if resp.JSON200 == nil {
		return fmt.Errorf("server returned %s: %s", resp.HTTPResponse.Status, bytes.TrimSpace(resp.Body))
	}
	out, err := json.Marshal(resp.JSON200)
	if err != nil {
		return fmt.Errorf("encode tokens: %w", err)
	}
	fmt.Fprintln(stdout, string(out))
	return nil
}

func revokeToken(ctx context.Context, client *conbench.ClientWithResponses, id, bearer string, stdout io.Writer) error {
	params := &conbench.DeleteTokenParams{}
	if bearer != "" {
		params.Authorization = &bearer
	}
	resp, err := client.DeleteTokenWithResponse(ctx, id, params)
	if err != nil {
		return fmt.Errorf("revoke token: %w", err)
	}
	switch resp.HTTPResponse.StatusCode {
	case http.StatusNoContent:
		return writeJSONLine(stdout, struct {
			Revoked bool   `json:"revoked"`
			ID      string `json:"id"`
		}{Revoked: true, ID: id})
	case http.StatusNotFound:
		return errors.New("token not found")
	default:
		return fmt.Errorf("server returned %s: %s", resp.HTTPResponse.Status, bytes.TrimSpace(resp.Body))
	}
}
