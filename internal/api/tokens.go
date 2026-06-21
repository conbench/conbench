package api

import (
	"context"
	"errors"
	"net/http"
	"time"

	"github.com/danielgtaylor/huma/v2"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/storage"
)

// TokenAdminStore is the slice of the data layer the token CRUD handler needs.
// *db.Store satisfies it.
type TokenAdminStore interface {
	CreateAPIToken(ctx context.Context, p storage.InsertAPITokenParams) (string, error)
	ListAPITokensByUser(ctx context.Context, userID string) ([]storage.APIToken, error)
	GetAPITokenByID(ctx context.Context, id string) (storage.APIToken, error)
	RevokeAPIToken(ctx context.Context, id string, revokedAt time.Time) error
}

// TokenHandler serves user-attributed token management. Every operation
// requires a user principal (session or db token); the static operator token
// is rejected with 403 because it owns no user.
type TokenHandler struct {
	store TokenAdminStore
	auth  *auth.Authenticator
}

// NewTokenHandler builds the token CRUD handler over the data layer and the
// authenticator.
func NewTokenHandler(store TokenAdminStore, authn *auth.Authenticator) *TokenHandler {
	return &TokenHandler{store: store, auth: authn}
}

// Register wires the token operations onto a huma API.
func (h *TokenHandler) Register(api huma.API) {
	huma.Register(api, huma.Operation{
		OperationID: "create-token", Summary: "Mint an API token",
		Method: http.MethodPost, Path: "/api/tokens", DefaultStatus: http.StatusCreated,
	}, h.create)
	huma.Register(api, huma.Operation{
		OperationID: "list-tokens", Summary: "List the caller's API tokens",
		Method: http.MethodGet, Path: "/api/tokens",
	}, h.list)
	huma.Register(api, huma.Operation{
		OperationID: "delete-token", Summary: "Revoke one of the caller's API tokens",
		Method: http.MethodDelete, Path: "/api/tokens/{id}", DefaultStatus: http.StatusNoContent,
	}, h.delete)
}

// principal authorizes the request and requires a user identity. No credential
// -> 401; a non-user credential (static operator token) -> 403.
func (h *TokenHandler) principal(ctx context.Context, authHeader, session string) (auth.Principal, error) {
	p, err := h.auth.ResolvePrincipal(ctx, authHeader, session)
	if err != nil {
		return auth.Principal{}, huma.Error401Unauthorized("authentication required")
	}
	if !p.IsUser() {
		return auth.Principal{}, huma.Error403Forbidden("user-attributed authentication required")
	}
	return p, nil
}

type tokenView struct {
	ID         string     `json:"id"`
	Name       string     `json:"name"`
	Prefix     string     `json:"prefix"`
	CreatedAt  time.Time  `json:"created_at"`
	LastUsedAt *time.Time `json:"last_used_at,omitempty"`
	RevokedAt  *time.Time `json:"revoked_at,omitempty"`
}

func viewOf(r storage.APIToken) tokenView {
	return tokenView{
		ID: r.ID, Name: r.Name, Prefix: r.TokenPrefix, CreatedAt: r.CreatedAt,
		LastUsedAt: r.LastUsedAt, RevokedAt: r.RevokedAt,
	}
}

type createTokenInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
	Body          struct {
		Name string `json:"name"`
	}
}

type createTokenOutput struct {
	Body struct {
		ID        string    `json:"id"`
		Name      string    `json:"name"`
		Token     string    `json:"token" doc:"The plaintext secret. Shown once; store it now."`
		Prefix    string    `json:"prefix"`
		CreatedAt time.Time `json:"created_at"`
	}
}

func (h *TokenHandler) create(ctx context.Context, in *createTokenInput) (*createTokenOutput, error) {
	p, err := h.principal(ctx, in.Authorization, in.Session)
	if err != nil {
		return nil, err
	}
	if in.Body.Name == "" {
		return nil, huma.Error422UnprocessableEntity("name is required")
	}
	tok, err := auth.GenerateToken()
	if err != nil {
		return nil, err
	}
	now := time.Now().UTC()
	id, err := h.store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: p.UserID, Name: in.Body.Name, TokenHash: tok.Hash, TokenPrefix: tok.Prefix, CreatedAt: now,
	})
	if err != nil {
		return nil, err
	}
	out := &createTokenOutput{}
	out.Body.ID, out.Body.Name, out.Body.Token = id, in.Body.Name, tok.Plaintext
	out.Body.Prefix, out.Body.CreatedAt = tok.Prefix, now
	return out, nil
}

type listTokensInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
}

type listTokensOutput struct {
	Body struct {
		Tokens []tokenView `json:"tokens"`
	}
}

func (h *TokenHandler) list(ctx context.Context, in *listTokensInput) (*listTokensOutput, error) {
	p, err := h.principal(ctx, in.Authorization, in.Session)
	if err != nil {
		return nil, err
	}
	rows, err := h.store.ListAPITokensByUser(ctx, p.UserID)
	if err != nil {
		return nil, err
	}
	out := &listTokensOutput{}
	out.Body.Tokens = make([]tokenView, 0, len(rows))
	for _, r := range rows {
		out.Body.Tokens = append(out.Body.Tokens, viewOf(r))
	}
	return out, nil
}

type deleteTokenInput struct {
	Authorization string `header:"Authorization" doc:"Bearer token."`
	Session       string `cookie:"conbench_session"`
	ID            string `path:"id"`
}

func (h *TokenHandler) delete(ctx context.Context, in *deleteTokenInput) (*struct{}, error) {
	p, err := h.principal(ctx, in.Authorization, in.Session)
	if err != nil {
		return nil, err
	}
	row, err := h.store.GetAPITokenByID(ctx, in.ID)
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return nil, huma.Error404NotFound("token not found")
		}
		return nil, err
	}
	// Ownership is never revealed: another user's token is a 404, identical to
	// an unknown id.
	if row.UserID != p.UserID {
		return nil, huma.Error404NotFound("token not found")
	}
	if err := h.store.RevokeAPIToken(ctx, in.ID, time.Now().UTC()); err != nil {
		// A concurrent hard-delete in the race window is the only path here,
		// since GetAPITokenByID just saw the row; treat it as success so an
		// owner re-deleting an already-revoked token stays idempotent (204).
		if errors.Is(err, storage.ErrNotFound) {
			return nil, nil
		}
		return nil, err
	}
	return nil, nil
}
