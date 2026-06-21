package api

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/url"
	"time"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/oidcauth"
	"github.com/conbench/conbench/internal/storage"
)

// pendingCookieName is the short-lived cookie carrying the in-flight login's
// state, nonce, and PKCE verifier (signed, not encrypted — these are not
// secrets, but they must not be forgeable).
const pendingCookieName = "conbench_pending"

// pendingMaxAge bounds an in-flight login.
const pendingMaxAge = 10 * time.Minute

// pendingLogin is the payload of the pending-login cookie.
type pendingLogin struct {
	State    string `json:"state"`
	Nonce    string `json:"nonce"`
	Verifier string `json:"verifier"`
	// CLIRedirect and CLIState are set only when the pending login originated
	// from cli-start without an existing session: after OIDC establishes the
	// session, the callback completes the loopback redirect instead of going to
	// the app root.
	CLIRedirect string `json:"cli_redirect,omitempty"`
	CLIState    string `json:"cli_state,omitempty"`
}

// UserStore is the slice of the data layer the auth handlers need: match or
// create the OIDC user, and load identity for /users/me. *db.Store satisfies it.
type UserStore interface {
	GetOrCreateUserByEmail(ctx context.Context, email, name, password string) (string, error)
	GetUserByID(ctx context.Context, id string) (storage.User, error)
	CreateAPIToken(ctx context.Context, p storage.InsertAPITokenParams) (string, error)
}

// oidcMarkerPassword is the unusable value stored in the NOT NULL password
// column for OIDC users; password login is retired, so it is never checked.
const oidcMarkerPassword = "!"

// AuthHandler serves the OIDC login flow and session identity endpoints. A nil
// oidc client means OIDC is not configured: login/callback return 501, while
// logout and users/me still work off the session cookie alone.
type AuthHandler struct {
	oidc         *oidcauth.Client
	users        UserStore
	sessions     *auth.SessionSigner
	pending      *auth.Signer
	codes        CLICodeStore
	secure       bool
	baseURL      string
	authDisabled bool
}

// NewAuthHandler builds the auth handler. baseURL is the post-login redirect
// target; secure controls the cookie Secure attribute (false for localhost
// dev). codes mints the one-time CLI login codes for the loopback flow.
// authDisabled mirrors the write authenticator's local-dev bypass so the SPA
// can expose write controls only when writes are actually possible.
func NewAuthHandler(oidcClient *oidcauth.Client, users UserStore, sessions *auth.SessionSigner, pending *auth.Signer, secure bool, baseURL string, codes CLICodeStore, authDisabled bool) *AuthHandler {
	return &AuthHandler{oidc: oidcClient, users: users, sessions: sessions, pending: pending, codes: codes, secure: secure, baseURL: baseURL, authDisabled: authDisabled}
}

// Register wires the auth operations onto a huma API.
func (h *AuthHandler) Register(api huma.API) {
	huma.Register(api, huma.Operation{
		OperationID: "auth-login", Summary: "Begin OIDC login",
		Method: http.MethodGet, Path: "/api/auth/login", DefaultStatus: http.StatusFound,
	}, h.login)
	huma.Register(api, huma.Operation{
		OperationID: "auth-callback", Summary: "OIDC callback",
		Method: http.MethodGet, Path: "/api/auth/callback", DefaultStatus: http.StatusFound,
	}, h.callback)
	huma.Register(api, huma.Operation{
		OperationID: "auth-cli-start", Summary: "Begin CLI loopback login",
		Method: http.MethodGet, Path: "/api/auth/cli-start", DefaultStatus: http.StatusFound,
	}, h.cliStart)
	huma.Register(api, huma.Operation{
		OperationID: "auth-cli-exchange", Summary: "Exchange a CLI login code for an API token",
		Method: http.MethodPost, Path: "/api/auth/cli-exchange",
	}, h.cliExchange)
	huma.Register(api, huma.Operation{
		OperationID: "auth-logout", Summary: "Log out",
		Method: http.MethodPost, Path: "/api/auth/logout", DefaultStatus: http.StatusNoContent,
	}, h.logout)
	huma.Register(api, huma.Operation{
		OperationID: "auth-capabilities", Summary: "Browser-visible auth capabilities",
		Method: http.MethodGet, Path: "/api/auth/capabilities",
	}, h.capabilities)
	huma.Register(api, huma.Operation{
		OperationID: "users-me", Summary: "Current session identity",
		Method: http.MethodGet, Path: "/api/users/me",
	}, h.me)
}

// --- login ---

type loginOutput struct {
	Status    int
	Location  string      `header:"Location"`
	SetCookie http.Cookie `header:"Set-Cookie"`
}

func (h *AuthHandler) login(_ context.Context, _ *struct{}) (*loginOutput, error) {
	if h.oidc == nil {
		return nil, huma.Error501NotImplemented("OIDC is not configured")
	}
	return h.beginOIDC(pendingLogin{
		State: auth.RandomToken(), Nonce: auth.RandomToken(), Verifier: auth.GeneratePKCEVerifier(),
	})
}

// beginOIDC issues the pending-login cookie and 302s to the IdP. The pending
// payload carries the state/nonce/PKCE verifier and, for the CLI flow, the
// loopback redirect context so the callback can complete it.
func (h *AuthHandler) beginOIDC(pend pendingLogin) (*loginOutput, error) {
	blob, _ := json.Marshal(pend)
	return &loginOutput{
		Status:    http.StatusFound,
		Location:  h.oidc.AuthCodeURL(pend.State, pend.Nonce, pend.Verifier),
		SetCookie: h.cookie(pendingCookieName, h.pending.Sign(blob), int(pendingMaxAge.Seconds()), "/api/auth"),
	}, nil
}

// --- cli-start ---

type cliStartInput struct {
	RedirectURI string `query:"redirect_uri"`
	State       string `query:"state"`
	Session     string `cookie:"conbench_session"`
}

func (h *AuthHandler) cliStart(ctx context.Context, in *cliStartInput) (*loginOutput, error) {
	if err := validateLoopbackRedirect(in.RedirectURI); err != nil {
		return nil, huma.Error400BadRequest(err.Error())
	}
	if uid, ok := h.sessionUser(in.Session); ok {
		return h.redirectToLoopback(ctx, in.RedirectURI, in.State, uid)
	}
	if h.oidc == nil {
		return nil, huma.Error501NotImplemented("OIDC is not configured")
	}
	return h.beginOIDC(pendingLogin{
		State: auth.RandomToken(), Nonce: auth.RandomToken(), Verifier: auth.GeneratePKCEVerifier(),
		CLIRedirect: in.RedirectURI, CLIState: in.State,
	})
}

func (h *AuthHandler) sessionUser(session string) (string, bool) {
	if h.sessions == nil || session == "" {
		return "", false
	}
	uid, err := h.sessions.Verify(session, time.Now().UTC())
	return uid, err == nil
}

// redirectToLoopback issues a one-time code and 302s to the CLI's loopback
// callback with code+state. It also clears any stale pending cookie.
func (h *AuthHandler) redirectToLoopback(ctx context.Context, redirectURI, state, userID string) (*loginOutput, error) {
	code, err := h.codes.Issue(ctx, userID)
	if err != nil {
		return nil, err
	}
	return &loginOutput{
		Status:    http.StatusFound,
		Location:  appendQuery(redirectURI, code, state),
		SetCookie: h.expire(pendingCookieName, "/api/auth"),
	}, nil
}

// validateLoopbackRedirect enforces RFC 8252 loopback: http scheme + a literal
// 127.0.0.1 or ::1 host (never "localhost", which can resolve elsewhere).
func validateLoopbackRedirect(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return errors.New("invalid redirect_uri")
	}
	if u.Scheme != "http" {
		return errors.New("redirect_uri must use http on loopback")
	}
	if host := u.Hostname(); host != "127.0.0.1" && host != "::1" {
		return errors.New("redirect_uri must be a loopback address")
	}
	return nil
}

// appendQuery adds code and state to a loopback redirect URI.
func appendQuery(redirectURI, code, state string) string {
	u, _ := url.Parse(redirectURI)
	q := u.Query()
	q.Set("code", code)
	q.Set("state", state)
	u.RawQuery = q.Encode()
	return u.String()
}

// --- cli-exchange ---

type cliExchangeInput struct {
	Body struct {
		Code string `json:"code"`
		Name string `json:"name"`
	}
}

type cliExchangeOutput struct {
	Body struct {
		ID        string    `json:"id"`
		Name      string    `json:"name"`
		Token     string    `json:"token" doc:"The plaintext secret. Shown once."`
		Prefix    string    `json:"prefix"`
		CreatedAt time.Time `json:"created_at"`
	}
}

func (h *AuthHandler) cliExchange(ctx context.Context, in *cliExchangeInput) (*cliExchangeOutput, error) {
	userID, ok, err := h.codes.Redeem(ctx, in.Body.Code)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, huma.Error400BadRequest("invalid or expired code")
	}
	name := in.Body.Name
	if name == "" {
		name = "cli token"
	}
	tok, err := auth.GenerateToken()
	if err != nil {
		return nil, err
	}
	now := time.Now().UTC()
	id, err := h.users.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: userID, Name: name, TokenHash: tok.Hash, TokenPrefix: tok.Prefix, CreatedAt: now,
	})
	if err != nil {
		return nil, err
	}
	out := &cliExchangeOutput{}
	out.Body.ID, out.Body.Name, out.Body.Token = id, name, tok.Plaintext
	out.Body.Prefix, out.Body.CreatedAt = tok.Prefix, now
	return out, nil
}

// --- callback ---

type callbackInput struct {
	State   string `query:"state"`
	Code    string `query:"code"`
	Pending string `cookie:"conbench_pending"`
}

type callbackOutput struct {
	Status    int
	Location  string        `header:"Location"`
	SetCookie []http.Cookie `header:"Set-Cookie"`
}

func (h *AuthHandler) callback(ctx context.Context, in *callbackInput) (*callbackOutput, error) {
	if h.oidc == nil {
		return nil, huma.Error501NotImplemented("OIDC is not configured")
	}
	pend, err := h.readPending(in.Pending)
	if err != nil {
		return nil, huma.Error400BadRequest("invalid login state")
	}
	if in.State == "" || in.State != pend.State {
		return nil, huma.Error400BadRequest("state mismatch")
	}
	identity, err := h.oidc.Exchange(ctx, in.Code, pend.Verifier)
	if err != nil {
		slog.Warn("auth: oidc exchange failed", "error", err)
		return nil, huma.Error400BadRequest("login failed")
	}
	if identity.Nonce != pend.Nonce {
		return nil, huma.Error400BadRequest("nonce mismatch")
	}
	if !identity.EmailVerified || identity.Email == "" {
		return nil, huma.Error400BadRequest("email not verified")
	}
	name := identity.Name
	if name == "" {
		name = identity.Email
	}
	userID, err := h.users.GetOrCreateUserByEmail(ctx, identity.Email, name, oidcMarkerPassword)
	if err != nil {
		return nil, err // unexpected: huma maps to 500
	}
	session := h.sessions.Sign(userID, time.Now().UTC().Add(auth.SessionMaxAge))
	sessionCookie := h.cookie(auth.SessionCookieName, session, int(auth.SessionMaxAge.Seconds()), "/")
	if pend.CLIRedirect != "" {
		code, err := h.codes.Issue(ctx, userID)
		if err != nil {
			return nil, err
		}
		return &callbackOutput{
			Status:    http.StatusFound,
			Location:  appendQuery(pend.CLIRedirect, code, pend.CLIState),
			SetCookie: []http.Cookie{sessionCookie, h.expire(pendingCookieName, "/api/auth")},
		}, nil
	}
	return &callbackOutput{
		Status:    http.StatusFound,
		Location:  h.baseURL + "/",
		SetCookie: []http.Cookie{sessionCookie, h.expire(pendingCookieName, "/api/auth")},
	}, nil
}

// --- logout ---

type logoutOutput struct {
	SetCookie http.Cookie `header:"Set-Cookie"`
}

func (h *AuthHandler) logout(_ context.Context, _ *struct{}) (*logoutOutput, error) {
	return &logoutOutput{SetCookie: h.expire(auth.SessionCookieName, "/")}, nil
}

// --- auth capabilities ---

type capabilitiesInput struct {
	Session string `cookie:"conbench_session"`
}

type capabilitiesOutput struct {
	Body struct {
		SignedIn        bool `json:"signed_in"`
		AuthDisabled    bool `json:"auth_disabled"`
		CanWriteResults bool `json:"can_write_results"`
	}
}

func (h *AuthHandler) capabilities(_ context.Context, in *capabilitiesInput) (*capabilitiesOutput, error) {
	_, signedIn := h.sessionUser(in.Session)
	out := &capabilitiesOutput{}
	out.Body.SignedIn = signedIn
	out.Body.AuthDisabled = h.authDisabled
	out.Body.CanWriteResults = h.authDisabled || signedIn
	return out, nil
}

// --- users/me ---

type meInput struct {
	Session string `cookie:"conbench_session"`
}

type meOutput struct {
	Body struct {
		ID    string `json:"id"`
		Email string `json:"email"`
		Name  string `json:"name"`
	}
}

func (h *AuthHandler) me(ctx context.Context, in *meInput) (*meOutput, error) {
	if h.sessions == nil || in.Session == "" {
		return nil, huma.Error401Unauthorized("authentication required")
	}
	userID, err := h.sessions.Verify(in.Session, time.Now().UTC())
	if err != nil {
		return nil, huma.Error401Unauthorized("authentication required")
	}
	user, err := h.users.GetUserByID(ctx, userID)
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return nil, huma.Error401Unauthorized("authentication required")
		}
		return nil, err
	}
	out := &meOutput{}
	out.Body.ID = user.ID
	out.Body.Email = user.Email
	out.Body.Name = user.Name
	return out, nil
}

// --- cookie helpers ---

func (h *AuthHandler) cookie(name, value string, maxAge int, path string) http.Cookie {
	return http.Cookie{
		Name: name, Value: value, Path: path,
		MaxAge: maxAge, HttpOnly: true, Secure: h.secure, SameSite: http.SameSiteLaxMode,
	}
}

func (h *AuthHandler) expire(name, path string) http.Cookie {
	c := h.cookie(name, "", -1, path)
	return c
}

func (h *AuthHandler) readPending(value string) (pendingLogin, error) {
	if h.pending == nil || value == "" {
		return pendingLogin{}, errors.New("no pending login")
	}
	raw, err := h.pending.Verify(value)
	if err != nil {
		return pendingLogin{}, err
	}
	var p pendingLogin
	if err := json.Unmarshal(raw, &p); err != nil {
		return pendingLogin{}, err
	}
	return p, nil
}
