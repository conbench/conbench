// Package oidcauth wraps go-oidc and x/oauth2 into the small surface the auth
// handlers need: build an authorization-request URL (state, nonce, PKCE), and
// exchange an authorization code for a verified caller identity. ID-token
// verification (issuer, audience, expiry, signature) is delegated to go-oidc;
// nonce is returned for the caller to compare against the pending-login value.
package oidcauth

import (
	"context"
	"errors"
	"fmt"

	"github.com/coreos/go-oidc/v3/oidc"
	"golang.org/x/oauth2"
)

// Config is the operator-supplied OIDC configuration.
type Config struct {
	IssuerURL    string
	ClientID     string
	ClientSecret string
	RedirectURL  string
}

// Client is a configured OIDC relying party.
type Client struct {
	oauth2   *oauth2.Config
	verifier *oidc.IDTokenVerifier
}

// New performs OIDC discovery against the issuer and returns a Client. It makes
// a network call and is meant to run once at startup.
func New(ctx context.Context, cfg Config) (*Client, error) {
	provider, err := oidc.NewProvider(ctx, cfg.IssuerURL)
	if err != nil {
		return nil, fmt.Errorf("oidc discovery for %q: %w", cfg.IssuerURL, err)
	}
	return &Client{
		oauth2: &oauth2.Config{
			ClientID:     cfg.ClientID,
			ClientSecret: cfg.ClientSecret,
			Endpoint:     provider.Endpoint(),
			RedirectURL:  cfg.RedirectURL,
			Scopes:       []string{oidc.ScopeOpenID, "email", "profile"},
		},
		verifier: provider.Verifier(&oidc.Config{ClientID: cfg.ClientID}),
	}, nil
}

// AuthCodeURL builds the authorization-request URL carrying state, nonce, and
// the S256 PKCE challenge derived from verifier.
func (c *Client) AuthCodeURL(state, nonce, verifier string) string {
	return c.oauth2.AuthCodeURL(state, oidc.Nonce(nonce), oauth2.S256ChallengeOption(verifier))
}

// Identity is the verified caller identity extracted from the ID token.
type Identity struct {
	Email         string
	EmailVerified bool
	Name          string
	Nonce         string
}

// Exchange swaps an authorization code (with its PKCE verifier) for a verified
// Identity: it exchanges at the token endpoint, then verifies the ID token's
// issuer, audience, expiry, and signature. The caller must still compare Nonce
// against the value it issued and enforce EmailVerified.
func (c *Client) Exchange(ctx context.Context, code, verifier string) (Identity, error) {
	tok, err := c.oauth2.Exchange(ctx, code, oauth2.VerifierOption(verifier))
	if err != nil {
		return Identity{}, fmt.Errorf("oidc token exchange: %w", err)
	}
	rawID, ok := tok.Extra("id_token").(string)
	if !ok || rawID == "" {
		return Identity{}, errors.New("oidc token response had no id_token")
	}
	idToken, err := c.verifier.Verify(ctx, rawID)
	if err != nil {
		return Identity{}, fmt.Errorf("verify id token: %w", err)
	}
	var claims struct {
		Email         string `json:"email"`
		EmailVerified bool   `json:"email_verified"`
		Name          string `json:"name"`
	}
	if err := idToken.Claims(&claims); err != nil {
		return Identity{}, fmt.Errorf("parse id token claims: %w", err)
	}
	return Identity{
		Email:         claims.Email,
		EmailVerified: claims.EmailVerified,
		Name:          claims.Name,
		Nonce:         idToken.Nonce,
	}, nil
}
