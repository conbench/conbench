package api

import (
	"context"
	"encoding/json"

	"github.com/conbench/conbench/internal/auth"
)

// SignPendingForTest signs a pending-login cookie value so tests in other
// packages can drive the callback directly. It lives in a _test.go file so it
// is compiled only into test binaries, never the production package API.
func SignPendingForTest(secret, state, nonce, verifier string) string {
	blob, _ := json.Marshal(pendingLogin{State: state, Nonce: nonce, Verifier: verifier})
	return auth.NewSigner(secret).Sign(blob)
}

// SignPendingCLIForTest builds a signed pending cookie carrying CLI loopback
// context, for callback tests.
func SignPendingCLIForTest(secret, state, nonce, verifier, cliRedirect, cliState string) string {
	blob, _ := json.Marshal(pendingLogin{
		State: state, Nonce: nonce, Verifier: verifier, CLIRedirect: cliRedirect, CLIState: cliState,
	})
	return auth.NewSigner(secret).Sign(blob)
}

// IssueCLICodeForTest issues a one-time CLI code for a user.
func (h *AuthHandler) IssueCLICodeForTest(userID string) string {
	code, err := h.codes.Issue(context.Background(), userID)
	if err != nil {
		panic(err)
	}
	return code
}
