// Package serverapp runs the Conbench backend: it connects to Postgres,
// optionally applies the schema and seeds demo data (for `make dev`), and serves
// the write, read, and health endpoints. Configuration is via environment:
//
//	CONBENCH_DB_URL        Postgres URL (or DATABASE_URL). Required.
//	CONBENCH_ADDR          Listen address. Default ":8080".
//	CONBENCH_INIT_SCHEMA   "true" applies the embedded schema if missing (dev).
//	CONBENCH_SEED          "true" seeds deterministic demo data (idempotent).
//	CONBENCH_SEED_DEV_TOKEN When set, get-or-creates a dev user and a user-attributed
//	                       api_token whose hash is HashToken(value), so dev/e2e can
//	                       exercise user-attributed endpoints. Independent of CONBENCH_SEED.
//	                       Idempotent; only the 8-char prefix is logged, never the value.
//	CONBENCH_API_TOKEN     Static operator bearer token accepted on writes.
//	                       User-attributed api_token rows also authenticate writes.
//	CONBENCH_AUTH_DISABLED "true" disables write auth (dev only).
//	GITHUB_API_TOKEN          GitHub API token(s), comma-separated. When set, commit
//	                          metadata is fetched from the GitHub API and default-branch
//	                          ancestry is backfilled asynchronously; when unset, commits
//	                          are synthesized locally (dev/e2e).
//	CONBENCH_GITHUB_TIMEOUT   In-request GitHub enrichment budget (Go duration). Default 5s.
//	CONBENCH_OIDC_ISSUER_URL  OIDC issuer URL. When any OIDC var is set, all three
//	                          plus CONBENCH_INTENDED_BASE_URL and
//	                          CONBENCH_SESSION_SECRET are required; enables /api/auth login.
//	CONBENCH_OIDC_CLIENT_ID   OIDC relying-party client id.
//	CONBENCH_OIDC_CLIENT_SECRET OIDC relying-party client secret.
//	CONBENCH_INTENDED_BASE_URL Public base URL; the OIDC redirect and post-login
//	                          target derive from it, and cookies are non-Secure only
//	                          when its host is localhost/127.0.0.1/::1.
//	CONBENCH_SESSION_SECRET   HMAC key for the session and pending-login cookies. When
//	                          set, a valid session cookie authenticates writes.
package serverapp

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/oidcauth"
	"github.com/conbench/conbench/internal/seed"
	"github.com/conbench/conbench/internal/server"
)

// Run starts the Conbench backend and blocks until it exits or ctx is canceled.
func Run(ctx context.Context) error {
	cfg, err := loadConfig()
	if err != nil {
		return err
	}

	ctx, stop := signal.NotifyContext(ctx, syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	pool, err := pgxpool.New(ctx, cfg.databaseURL)
	if err != nil {
		return fmt.Errorf("connect db: %w", err)
	}
	defer pool.Close()

	if err := pool.Ping(ctx); err != nil {
		return fmt.Errorf("ping db: %w", err)
	}

	if cfg.initSchema {
		if err := server.EnsureSchema(ctx, pool); err != nil {
			return err
		}
		log.Printf("schema ready")
	}

	store := db.NewStore(pool)

	var sessionSigner *auth.SessionSigner
	if cfg.sessionSecret != "" {
		sessionSigner = auth.NewSessionSigner(cfg.sessionSecret)
	}
	authn := auth.New(cfg.apiToken, cfg.authDisabled, store, sessionSigner)

	var oidcClient *oidcauth.Client
	if cfg.oidcIssuerURL != "" {
		oidcClient, err = oidcauth.New(ctx, oidcauth.Config{
			IssuerURL:    cfg.oidcIssuerURL,
			ClientID:     cfg.oidcClientID,
			ClientSecret: cfg.oidcClientSecret,
			RedirectURL:  strings.TrimRight(cfg.baseURL, "/") + "/api/auth/callback",
		})
		if err != nil {
			return fmt.Errorf("init oidc: %w", err)
		}
		log.Printf("oidc login enabled (issuer %s)", cfg.oidcIssuerURL)
	}
	authHandler := api.NewAuthHandler(oidcClient, store, sessionSigner, auth.NewSigner(cfg.sessionSecret), cfg.secureCookies, strings.TrimRight(cfg.baseURL, "/"), api.NewDBCodeStore(store), cfg.authDisabled)

	if cfg.seed {
		summary, err := seed.Run(ctx, store)
		if err != nil {
			return fmt.Errorf("seed: %w", err)
		}
		if summary.Skipped {
			log.Printf("seed: skipped (database already has results)")
		} else {
			log.Printf("seed: inserted %d results; history fingerprint %s", summary.Inserted, summary.Fingerprint)
		}
	}

	if v := os.Getenv("CONBENCH_SEED_DEV_TOKEN"); v != "" {
		prefix, err := seed.DevToken(ctx, store, v)
		if err != nil {
			return fmt.Errorf("seed dev token: %w", err)
		}
		log.Printf("seed: dev token ready (prefix %s)", prefix)
	}

	var provider commit.Provider = commit.LocalProvider{}
	var backfiller *commit.Backfiller
	if cfg.githubToken != "" {
		client := commit.NewGitHubClient(cfg.githubToken, "")
		backfiller = commit.NewBackfiller(client, store)
		provider = commit.NewGitHubProvider(client, cfg.githubTimeout, backfiller)
		log.Printf("github commit provider enabled (budget %s)", cfg.githubTimeout)
	}

	srv := &http.Server{
		Addr:              cfg.addr,
		Handler:           server.New(store, authn, provider, authHandler, cfg.baseURL),
		ReadHeaderTimeout: 10 * time.Second,
	}

	errc := make(chan error, 1)
	go func() {
		log.Printf("listening on %s (auth disabled: %t)", cfg.addr, authn.Disabled())
		errc <- srv.ListenAndServe()
	}()

	select {
	case err := <-errc:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		log.Printf("shutting down")
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		err := srv.Shutdown(shutdownCtx)
		if backfiller != nil {
			backfiller.Shutdown(shutdownCtx)
		}
		return err
	}
}

type config struct {
	addr             string
	databaseURL      string
	seed             bool
	initSchema       bool
	apiToken         string
	authDisabled     bool
	githubToken      string
	githubTimeout    time.Duration
	oidcIssuerURL    string
	oidcClientID     string
	oidcClientSecret string
	baseURL          string
	sessionSecret    string
	secureCookies    bool
}

func loadConfig() (config, error) {
	dbURL := os.Getenv("CONBENCH_DB_URL")
	if dbURL == "" {
		dbURL = os.Getenv("DATABASE_URL")
	}
	if dbURL == "" {
		return config{}, errors.New("CONBENCH_DB_URL (or DATABASE_URL) is required")
	}
	addr := os.Getenv("CONBENCH_ADDR")
	if addr == "" {
		addr = ":8080"
	}
	githubTimeout := 5 * time.Second
	if v := os.Getenv("CONBENCH_GITHUB_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil {
			return config{}, fmt.Errorf("parse CONBENCH_GITHUB_TIMEOUT %q: %w", v, err)
		}
		githubTimeout = d
	}

	oidcIssuerURL := os.Getenv("CONBENCH_OIDC_ISSUER_URL")
	oidcClientID := os.Getenv("CONBENCH_OIDC_CLIENT_ID")
	oidcClientSecret := os.Getenv("CONBENCH_OIDC_CLIENT_SECRET")
	baseURL := os.Getenv("CONBENCH_INTENDED_BASE_URL")
	sessionSecret := os.Getenv("CONBENCH_SESSION_SECRET")
	if err := validateOIDCConfig(oidcIssuerURL, oidcClientID, oidcClientSecret, baseURL, sessionSecret); err != nil {
		return config{}, err
	}
	if err := validateSessionSecret(sessionSecret); err != nil {
		return config{}, err
	}

	return config{
		addr:             addr,
		databaseURL:      dbURL,
		seed:             os.Getenv("CONBENCH_SEED") == "true",
		initSchema:       os.Getenv("CONBENCH_INIT_SCHEMA") == "true",
		apiToken:         os.Getenv("CONBENCH_API_TOKEN"),
		authDisabled:     os.Getenv("CONBENCH_AUTH_DISABLED") == "true",
		githubToken:      os.Getenv("GITHUB_API_TOKEN"),
		githubTimeout:    githubTimeout,
		oidcIssuerURL:    oidcIssuerURL,
		oidcClientID:     oidcClientID,
		oidcClientSecret: oidcClientSecret,
		baseURL:          baseURL,
		sessionSecret:    sessionSecret,
		secureCookies:    secureFromBaseURL(baseURL),
	}, nil
}

// validateOIDCConfig enforces all-or-nothing OIDC configuration: if any OIDC
// variable is set, the full set (issuer, client id, client secret, base URL,
// and session secret) is required, and a missing one is a named startup error.
func validateOIDCConfig(issuerURL, clientID, clientSecret, baseURL, sessionSecret string) error {
	if issuerURL == "" && clientID == "" && clientSecret == "" {
		return nil
	}
	required := []struct {
		name  string
		value string
	}{
		{"CONBENCH_OIDC_ISSUER_URL", issuerURL},
		{"CONBENCH_OIDC_CLIENT_ID", clientID},
		{"CONBENCH_OIDC_CLIENT_SECRET", clientSecret},
		{"CONBENCH_INTENDED_BASE_URL", baseURL},
		{"CONBENCH_SESSION_SECRET", sessionSecret},
	}
	for _, r := range required {
		if r.value == "" {
			return fmt.Errorf("OIDC is partially configured: %s is required", r.name)
		}
	}
	return nil
}

// minSessionSecretLen is the floor for CONBENCH_SESSION_SECRET. The signed
// session cookie is a bearer write credential whose HMAC input and signature
// are exposed to the client, so a short or low-entropy secret would let an
// attacker forge sessions by offline guessing. 32 bytes is a 256-bit floor.
const minSessionSecretLen = 32

// validateSessionSecret rejects a configured-but-weak session secret at
// startup. An empty secret is allowed (session auth is simply disabled); any
// non-empty secret must clear the entropy floor.
func validateSessionSecret(secret string) error {
	if secret == "" {
		return nil
	}
	if len(secret) < minSessionSecretLen {
		return fmt.Errorf("CONBENCH_SESSION_SECRET must be at least %d characters", minSessionSecretLen)
	}
	return nil
}

// secureFromBaseURL decides whether cookies carry the Secure attribute: true
// for any real host, false only for localhost loopback dev addresses. An
// unparseable URL defaults to secure.
func secureFromBaseURL(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil {
		return true
	}
	host := u.Hostname()
	return host != "localhost" && host != "127.0.0.1" && host != "::1"
}
